#!/usr/bin/env python3

import cv2
import json
import time
import re
import os
import base64
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
from sancho_interfaces.srv import GetActionPrediction



class ActionRecognitionNode(Node):

    def __init__(self):
        super().__init__("action_recognition_node") 
        self.bridge = CvBridge()
        
       # --- Params read from .yaml ---
        
        # Routes and predictions for models
        self.frames_route = self.declare_parameter('frames_route', '/home/mapir/ar_images').value
        self.nPrediccionesLVLM = self.declare_parameter('n_predicciones_lvlm', 3).value
        self.nPrediccionesLLM = self.declare_parameter('n_predicciones_llm', 5).value

        # Model selection and return format
        self.LVLM_MODEL = self.declare_parameter('lvlm_model', 'qwen2.5vl:7b').value
        self.LLM_MODEL  = self.declare_parameter('llm_model', 'llama3.2:3b').value
        self.FORMAT     = self.declare_parameter('format', 'json').value

        #LVLM configuration
        self.LVLM_TEMPERATURE = self.declare_parameter('lvlm_temperature', 0.7).value
        self.LVLM_TOP_P       = self.declare_parameter('lvlm_top_p', 0.85).value
        self.LVLM_NUM_PREDICT = self.declare_parameter('lvlm_num_predict', 175).value

        #LLM configuration (Action prediction)
        self.LLM_ACTION_TEMP        = self.declare_parameter('llm_action_temperature', 0.6).value
        self.LLM_ACTION_TOP_P       = self.declare_parameter('llm_action_top_p', 0.5).value
        self.LLM_ACTION_NUM_PREDICT = self.declare_parameter('llm_action_num_predict', 175).value

        #LLM configuration (Voting)
        self.LLM_VOTING_TEMP        = self.declare_parameter('llm_voting_temperature', 0.1).value
        self.LLM_VOTING_TOP_P       = self.declare_parameter('llm_voting_top_p', 0.5).value
        self.LLM_VOTING_NUM_PREDICT = self.declare_parameter('llm_voting_num_predict', 175).value

        # --- MultiThread config ---
        self.sensor_cb_group = ReentrantCallbackGroup()
        self.ai_cb_group = MutuallyExclusiveCallbackGroup()

        # --- Create service for BH ---
        self.srv = self.create_service(
        GetActionPrediction, 
        'recognize_human_action', 
        self.handle_recognition_request,
        callback_group=self.ai_cb_group
        )

        # --- Debug mode ---
        self.DEBUG_MODE = self.declare_parameter('debugging', False).value

        # --- Wait time between frames --- 
        self.process_frame_every_n = self.declare_parameter('process_frame_every_n', 15).value

        # --- Bounding box margin ---
        self.bbox_margin = self.declare_parameter('bbox_margin', 20).value

        # --- Cropp image flag ---
        self.cropp_image_flag = self.declare_parameter('cropp_image_flag', True).value

        # --- Read images from hard drive flag ---
        self.read_from_hard_drive = self.declare_parameter('read_from_hard_drive', True).value

        # --- Node as a service flag ---
        self.node_as_service = self.declare_parameter('node_as_service', True).value

        # --- Prompts for models ---
        self.promptLVLM = PROMPT_SCENE_DESCRIPTION
        self.promptLLM_SD = PROMPT_ACTION_PREDICTION
        self.promptLLM_Voting = PROMPT_VOTING

        

        # --- Utils ---
        self.idle_timeout = self.declare_parameter('idle_timeout', 3.0).value
        self.EXECUTION_ENVIROMENT = self.declare_parameter('execution_enviroment', "LOCAL").value
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
        self.active_interface = False
        self.last_action = ""
        self.service_promised = False
        

        # --- Subcriptions and publishers ---
        self.tracking_subscriber =   self.create_subscription(FaceDetectionArray, '/sancho_perception/human_tracking', self.tracking_callback, 1, callback_group=self.sensor_cb_group)
        self.action_publisher    =   self.create_publisher(String, 'sancho_perception/action_prediction', 1) 


        # --- Create route depending on the test we doing --- 
        if self.EXECUTION_ENVIROMENT == "LOCAL": 
            self.WS_ROUTE = 'http://localhost:11434' 
        elif self.EXECUTION_ENVIROMENT == "EDGE":
            self.WS_ROUTE = 'http://10.1.26.67:11434'
        else: 
            self.WS_ROUTE = 'http://10.2.26.241:11434'

        # --- Create Ollama client to connect with edge ---
        self.client = Client(host = self.WS_ROUTE)

        # --- Check if Ollama is available ---
        if not self.check_ollama_connection():
            self.get_logger().fatal("Ollama server is not currently working. Shutting down node...")
            raise RuntimeError("Ollama Service Unavailable")
        
        else: self.get_logger().info("Connection with Ollama and Edge was succesfully made.")
        

        # --- Running node info ---
        self.get_logger().info("Action recognition node running...")


    def tracking_callback(self, msg):

        if self.node_as_service:
            if not self.active_interface:
                return

        if self.ai_busy:
            return

        self.frame_counter += 1
        
        if self.frame_counter == self.process_frame_every_n:

            self.frame_counter = 0
            if not msg.detections:
                return

            #Extract image, first person id and bounding box coordinates to cropp image 
            image = msg.image 
            bounding_box = msg.detections[0]
            person_id = msg.detections[0].tid
            
            self.recognition_core(image, person_id,bounding_box)


    def recognition_core(self,img_msg, id_msg, bbox_msg):
        
        #We want to predict the action of the first person captured by camera.
        if len(self.predict_frames_list) == 0:
            self.target_id = id_msg

        #Check if we have enough frame and if person id of frame is valid
        if(len(self.predict_frames_list) < 5 and id_msg == self.target_id ):
            try:
                    frame = self.bridge.imgmsg_to_cv2(img_msg, "bgr8")

                    #Cropp image to reduce latency in prediction

                    if self.cropp_image_flag:
                        try:
                            frame = self.cropp_image(frame,bbox_msg)

                        except Exception as e:
                            self.get_logger().error("Error occured during image cropp process, ABORTING EXECUTION...")
                            return

                    self.predict_frames_list.append(frame)
                    self.id_match_list.append("Frame " + str(self.id_count) + ": " + str(id_msg))
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

            #Store images in variables instead of reading from drive
            if self.read_from_hard_drive:
                frame_list = self.image_route_list
            else:
                frame_list = [self.frame_to_base64(f) for f in self.predict_frames_list]

            #Check to store b64 images in drive and to read the full prompt
            if(self.DEBUG_MODE): self.debug_base64_image(frame_list)
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
                        'images': [frame_list]
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
            self.last_action = msg
            self.action_publisher.publish(msg)

            #Notice service that prediction has finished
            if self.node_as_service :self.service_promised = True 

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
        self.get_logger().info(f"Connecting to Ollama in URL: {self.WS_ROUTE}...")
        
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

    def cropp_image(self, frame, bbox):

        h, w, _ = frame.shape

        if bbox.width <= 0 or bbox.height <= 0:
            self.get_logger().warn("Even bounding box width or height was not valid.")
            return frame

        xmin = bbox.corner.x
        ymin = bbox.corner.y
        bw = bbox.width
        bh = bbox.height
        xmax = xmin + bw
        ymax = ymin + bh

        #Apply selected margin to bounding box
        x1_m = max(0, int(xmin - bw * self.bbox_margin))
        y1_m = max(0, int(ymin - bh * self.bbox_margin))
        x2_m = min(w, int(xmax + bw * self.bbox_margin))
        y2_m = min(h, int(ymax + bh * self.bbox_margin))
        cropped_frame = frame[y1_m:y2_m, x1_m:x2_m]

        if cropped_frame.size == 0:
            self.get_logger().warn("Cropped frame size was invalid")
            return frame

        return cropped_frame
    

    def frame_to_base64(self, frame):

        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
    

    def debug_base64_image(self, b64_list):


        self.get_logger().info(f"Saving {len(b64_list)} images in Base64 in hardrive...")
        
        for i, b64_string in enumerate(b64_list):
            try:
                img_data = base64.b64decode(b64_string)
                nparr = np.frombuffer(img_data, np.uint8)
                img_check = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img_check is not None:
                    debug_path = os.path.join(self.frames_route, f"debug_b64_frame_{i}.jpg")
                    cv2.imwrite(debug_path, img_check)
                else:
                    self.get_logger().error(f"Couldn't save image in base64 with index: {i}")
                    
            except Exception as e:
                self.get_logger().error(f"Error processing frame in base64 {i}: {e}")


    # --- All service request come here (empty request) ---
    def handle_recognition_request(self, request, response):

        self.get_logger().info("Petition from Sancho recieved. Waiting for frames and prediction...")
        self.reset_utils() 
        self.service_promised = False
        self.active_interface = True


        #Start a 60s timer to avoid blocking status
        start_time = self.get_clock().now()
        timeout_duration = 60.0

        while not self.service_promised:
            
            elapsed_time = (self.get_clock().now() - start_time).nanoseconds / 1e9

            if elapsed_time > timeout_duration:
                self.get_logger().error("TIMEOUT: 60s has passed since the service was launched.")
                response.action = "timeout_error"
                self.active_interface = False
                return response
            
            time.sleep(0.1)
        
        response.action = self.last_action.data if hasattr(self.last_action, 'data') else "unknown"
        self.active_interface = False
        return response


        
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
        result += str(frame_info_index) + ". " + str(frame_info) + "\n"
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
