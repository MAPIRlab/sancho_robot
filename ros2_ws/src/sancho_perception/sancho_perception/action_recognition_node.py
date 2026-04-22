#!/usr/bin/env python3

import cv2
import json
import time
import re
import os
import rclpy
import numpy as np

from ollama import chat
from ollama import Client
from ollama import list as list_models
from cv_bridge import CvBridge
from rclpy.node import Node 
from sensor_msgs.msg import Image
from std_msgs.msg import String
from sancho_interfaces.msg import FaceDetectionArray
from rclpy.executors import MultiThreadedExecutor
from collections import Counter
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from .prompts import PROMPT_SCENE_DESCRIPTION, PROMPT_ACTION_PREDICTION, PROMPT_VOTING



class ActionRecognitionNode(Node):

    def __init__(self):
        super().__init__("action_recognition_node") 
        self.bridge = CvBridge()

       # --- Params read from .yaml ---
        
        # Routes and predictions for models
        self.frames_route = self.declare_parameter('frames_route', '/home/cayecaji/image_frames').value #CHECK AT LAB
        self.nPrediccionesLVLM = self.declare_parameter('n_predicciones_lvlm', 3).value
        self.nPrediccionesLLM = self.declare_parameter('n_predicciones_llm', 5).value

        # Model selection and return format
        self.LVLM_MODEL = self.declare_parameter('lvlm_model', 'qwen2.5vl:7b').value
        self.LLM_MODEL  = self.declare_parameter('llm_model', 'llama3.2:3b').value
        self.FORMAT     = self.declare_parameter('format', 'json').value

        #LVLM configuration
        self.LVLM_TEMPERATURE = self.declare_parameter('lvlm_temperature', 0.1).value
        self.LVLM_TOP_P       = self.declare_parameter('lvlm_top_p', 0.75).value
        self.LVLM_NUM_PREDICT = self.declare_parameter('lvlm_num_predict', 175).value

        #LLM configuration (Action prediction)
        self.LLM_ACTION_TEMP        = self.declare_parameter('llm_action_temperature', 0.4).value
        self.LLM_ACTION_TOP_P       = self.declare_parameter('llm_action_top_p', 0.5).value
        self.LLM_ACTION_NUM_PREDICT = self.declare_parameter('llm_action_num_predict', 175).value

        #LLM configuration (Voting)
        self.LLM_VOTING_TEMP        = self.declare_parameter('llm_voting_temperature', 0.1).value
        self.LLM_VOTING_TOP_P       = self.declare_parameter('llm_voting_top_p', 0.5).value
        self.LLM_VOTING_NUM_PREDICT = self.declare_parameter('llm_voting_num_predict', 175).value

        # --- MultiThread config ---
        self.sensor_cb_group = ReentrantCallbackGroup()
        self.ai_cb_group = MutuallyExclusiveCallbackGroup()

        # --- Debug mode ---
        self.DEBUG_MODE = self.declare_parameter('debugging', False).value

        # --- Prompts for models ---
        self.promptLVLM = PROMPT_SCENE_DESCRIPTION
        self.promptLLM_SD = PROMPT_ACTION_PREDICTION
        self.promptLLM_Voting = PROMPT_VOTING

        # --- Utils ---
        self.idle_timeout = self.declare_parameter('idle_timeout', 3.0).value
        self.LOCAL_TESTING = self.declare_parameter('local_testing', True).value
        self.predict_frames_list = []
        self.id_match_list = []
        self.image_route_list = []
        self.json_files    = []
        self.final_actions = []
        self.id_count = 1
        self.frame_id = 1
        self.ai_busy = False
        self.timeout_timer = None
        self.current_id = "No ID"
        self.frame_counter = 0
        self.process_frame_every_n = 7 #CHECK AT LAB / CHANGE SO NOT HARDCODED
        

        # --- Subcriptions and publishers ---
        self.tracking_subscriber =   self.create_subscription(FaceDetectionArray, '/sancho_perception/human_tracking', self.tracking_callback, 1, callback_group=self.sensor_cb_group)
        self.action_publisher    =   self.create_publisher(String, 'sancho_perception/action_prediction', 1) 


        # --- Create route depending on the test we doing --- 
        if self.LOCAL_TESTING: 
            self.EDGE_ROUTE = 'http://localhost:11434' 
        else:
            self.EDGE_ROUTE = 'http://10.1.26.67:11434'

        # --- Create Ollama client to connect with edge ---
        self.client = Client(host = self.EDGE_ROUTE)

        # --- Check if Ollama is available ---
        if not self.check_ollama_connection():
            self.get_logger().fatal("Ollama server is not currently working. Shutting down node...")
            raise RuntimeError("Ollama Service Unavailable")
        
        else: self.get_logger().info("Connection with Ollama and Edge was succesfully made.")
        

        # --- Running node info ---
        self.get_logger().info("Action recognition node running...")


    def tracking_callback(self, msg):

        if self.ai_busy:
            return

        self.frame_counter += 1
        
        if self.frame_counter == self.process_frame_every_n:

            self.frame_counter = 0
            if not msg.detections:
                return

            #Extract image and first person id 
            image = msg.image 
            person_id = msg.detections[0].tid
            
            self.recognition_core(image, person_id)


    def recognition_core(self,img_msg, id_msg):
        
        #We want to predict the action of the first person captured by camera.
        if len(self.predict_frames_list) == 0:
            self.target_id = id_msg

        #Check if we have enough frame and if person id of frame is valid
        if(len(self.predict_frames_list) < 5 and id_msg == self.target_id ):
            try:
                    frame = self.bridge.imgmsg_to_cv2(img_msg, "bgr8")
                    self.predict_frames_list.append(frame)
                    self.id_match_list.append("Frame " + str(self.id_count) + ": " + id_msg)
                    self.get_logger().info("    Image recieved...")
                    self.reset_idle_timer()
                    self.id_count +=1

            except Exception as e:
                    self.get_logger().error(f"Error reading image: {e}")
                    return
            
        

        if(len(self.predict_frames_list) == 5):


            primary_id, id_consistency = self.validate_id_consistency()

            if not id_consistency:
                self.get_logger().error("Couldn't predict action due to ID inconsistency.")
                self.reset_utils()
                return
            
            if self.timeout_timer is not None:
                self.timeout_timer.cancel()
                if self.DEBUG_MODE: self.get_logger().info("Starting predictions, timer canceled.")


            if self.DEBUG_MODE: self.get_logger().info("Predicting action of person with id["+ str(primary_id) + "].")

            self.ai_busy = True #Block incoming images
            self.id_count = 1
            if(self.DEBUG_MODE): print(self.id_match_list)
            for image in self.predict_frames_list:
                    
                    image_name = f"frame{self.frame_id}.jpg"
                    path = os.path.join(self.frames_route, image_name)
                    self.image_route_list.append(path)
                    cv2.imwrite(path, image)
                    self.frame_id +=1

            #Reset counter for future predictions
            self.frame_id = 1


            #Update prompt adding the ids info extracted from YOLO
            frame_id_info = get_frame_id_info(self.id_match_list)
            updatedLVLMprompt = self.promptLVLM.replace("INPUT_LVLM", frame_id_info)

            if(self.DEBUG_MODE): print(updatedLVLMprompt)
            print("------------------------------------------")


            #LVLM predictions
            for n in range (self.nPrediccionesLVLM):
                
                print("(LVLM): Prediction", n+1, "in course...")
                responseQwen = self.client.chat(
                    model= self.LVLM_MODEL,
                    messages=[{
                        'role': 'user',
                        'content': updatedLVLMprompt,
                        'images': [self.image_route_list[0], self.image_route_list[1], self.image_route_list[2], self.image_route_list[3], self.image_route_list[4]]
                    }],
                    format = self.FORMAT,
                    options={
                        'temperature': self.LVLM_TEMPERATURE,       
                        'top_p':  self.LVLM_TOP_P,                         
                        'num_predict': self.LVLM_NUM_PREDICT,     
                    },
                )
                
                #In case direct parse to JSON doesnt work
                """descripcion = re.findall(r'"descripcion_secuencia":\s*"([^"]+)"', responseQwen.message.content)
                acciones = re.findall(r'"accion":\s*"([^"]+)"', responseQwen.message.content)
                confianza = re.findall(r'"confianza":\s*"([^"]+)"', responseQwen.message.content)
                resultados = list(zip(descripcion,acciones, confianza))
                key = "Predicción " + str(v+1)
                results.update({key : resultados})"""


                #String to JSON parser
                try:
                    data = json.loads(responseQwen.message.content)
                    self.json_files.append(data)
                except:

                    if responseQwen.message.content == None:
                        self.error_empty_output(self.LLM_MODEL)
                    self.get_logger().info("Model didn't return clean JSON file:")
                    
                #Prediction end
                print(" Prediction" ,n+1 , "ended.")



        #********OUT OF LOOP**********

            lvlm_predictions = get_scene_descriptions(self.json_files)
            promptLLM = self.promptLLM_SD.replace("INPUT_LLM", lvlm_predictions)


            print("------------------------------------------")
            if(self.DEBUG_MODE): print(promptLLM)

            for n in range(self.nPrediccionesLLM):

                print("(LLM): Prediction" ,n+1, "in course...")
                responseLlava = self.client.chat(
                model=self.LLM_MODEL,
                messages=[{'role': 'user', 'content': promptLLM}],

                format=self.FORMAT,  

                options={
                    'temperature': self.LLM_ACTION_TEMP,  
                    'top_p': self.LLM_ACTION_TOP_P,
                    'num_predict': self.LLM_ACTION_NUM_PREDICT,
                },
            )
                

                #String to JSON parser
                try:
                    data = json.loads(responseLlava.message.content)
                    self.final_actions.append(data)
                except:
                    if responseLlava.message.content == None:
                        self.error_empty_output(self.LVLM_MODEL)
                    self.get_logger().info("Model didn't return clean JSON file:")
                    
                #Prediction end
                print(" Prediction", n+1 , "ended.")

            #Get final predictions
            actions_predictions = get_action_predictions(self.final_actions)
            promptVote = self.promptLLM_Voting.replace("INPUT_VOTING", actions_predictions)

            print("------------------------------------------")
            if(self.DEBUG_MODE): print(promptVote)

            print("(Voting Model): Predicting final decision...")
            responseVoting = self.client.chat(
            model=self.LLM_MODEL,
            messages=[{'role': 'user', 'content': promptVote}],

            format=self.FORMAT,  

            options={
                    'temperature': self.LLM_VOTING_TEMP,  
                    'top_p': self.LLM_VOTING_TOP_P,
                    'num_predict': self.LLM_VOTING_NUM_PREDICT,
            },
            )



            """#String to JSON parser
            try:
                    data = json.loads(responseVoting.message.content)
            except:
                    self.get_logger().info("Model didn't return clean JSON file:")"""
            

            if responseVoting.message.content == None:
                        self.error_empty_output(self.LLM_MODEL)

            print("------------------------------------------")
            print("Final prediction:")
           

            final_prediction = self.confidence_filter(responseVoting.message.content)
            print(final_prediction)
            
            #Publish final prediction
            msg = String()
            msg.data = final_prediction
            self.action_publisher.publish(msg)

            #Clear the lists and reset vars for other predictions
            self.reset_utils()


    # ---- Some useful functions ----

    def confidence_filter(self,llm_voting_pred):
        try:
            data = json.loads(llm_voting_pred)
            votos_raw = str(data.get("conteo_votos", "0"))
            match = re.search(r'\d+', votos_raw)
            conteo_mayoritario = int(match.group()) if match else 0
            
            if conteo_mayoritario <= 2:
                self.get_logger().info(f"Mayoritary decision was not reached ("+ str(conteo_mayoritario) +"/5). Unknown action.")
                data["accion_final"] = "unknown"

            return json.dumps(data, ensure_ascii=False)

        except Exception as e:
            self.get_logger().error(f"Error processing JSON : {e}")
            return json.dumps({"accion_final": "unknown", "error": "fallo_en_parseo"})
        
    def check_ollama_connection(self):
        self.get_logger().info(f"Connecting to Ollama in URL: {self.EDGE_ROUTE}...")
        
        try:
            response = self.client.list()
            model_names = [m.model for m in response.models]
            
            if self.DEBUG_MODE : self.get_logger().info(f"Models available for use: {model_names}")
            required_models = [self.LVLM_MODEL, self.LLM_MODEL]
            for model in required_models:
                if model not in model_names:
                    self.get_logger().warning(f"Warning: Model {model} is not downloaded in edge.")
                else:
                    if self.DEBUG_MODE : self.get_logger().info(f"Model correctly running: {model}")

            return True

        except Exception as e:
            self.get_logger().fatal(f"Connection error due to edge: {e}")
            return False
        

    def validate_id_consistency(self):
        if not self.id_match_list:
            return None, False

        ids = [msg.split(": ")[1] for msg in self.id_match_list]
        
        conteo = Counter(ids)
        id_dominante, num_apariciones = conteo.most_common(1)[0]
        
        if num_apariciones >= 4:
            if self.DEBUG_MODE: self.get_logger().info(f"At least 4 IDs where equal: " + str(id_dominante) + " (" + str(num_apariciones) +"/5)")
            return id_dominante, True
        else:
            self.get_logger().warn(f"There where not enough equal IDs: {conteo}. Aborting prediction.")
            return None, False
        
    def reset_idle_timer(self):
        
        #Check if predicting
        if self.ai_busy:
            return
        
        #Check an existing timer
        if self.timeout_timer is not None:
            self.timeout_timer.cancel()
        
        self.timeout_timer = self.create_timer(self.idle_timeout, self.reset_utils)
        if self.DEBUG_MODE: self.get_logger().info("Inactivity timer iniciated:"+ str(self.idle_timeout) +  ".")

    def  error_empty_output(self,model):
        self.get_logger.info("The model " + model + " returned an empty message, aborting prediction...")
        self.reset_utils()
        return

        
    def reset_utils(self):
        
        if self.DEBUG_MODE:  self.get_logger().info("Clearing all lists an resetting utils...")
        self.get_logger().info("Resetting images due to INACTIVITY...")
        

        self.ai_busy = False
        self.predict_frames_list.clear()
        self.image_route_list.clear()
        self.json_files.clear()
        self.final_actions.clear()
        self.id_match_list.clear()


# ---- Some getters ----

def get_frame_id_info(id_info):
    frame_info_index = 1
    result = ""
    for frame_info in id_info:
        result += str(frame_info_index) + ". " + frame_info + "\n"
        frame_info_index +=1

    return result

def get_scene_descriptions(lvlm_outputs):
    prediction_index = 1
    result = ""
    for file in lvlm_outputs:
        result += "Predicción " + str(prediction_index) + ":\n"
        result += str(file) + "\n"
        prediction_index += 1

    return result


def get_action_predictions(action_predictions):
    pred_string = ""
    i=1
    for action in action_predictions:
        pred_string += str(i) + ". " + action['accion_final'] + ".\n"
        i+=1
    return pred_string


def main():
    rclpy.init()
    node = ActionRecognitionNode()
    
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
