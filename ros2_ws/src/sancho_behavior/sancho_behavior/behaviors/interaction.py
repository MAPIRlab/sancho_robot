import py_trees
import py_trees_ros
import json
import random

from std_msgs.msg import String
from ollama import Client
from sancho_interfaces.srv import GetCentralFaceCluster, SanchoPrompt, SocialState, SetAudioSession
from sancho_interfaces.action import PlayTTS, ListenVoice

class GreetUser(py_trees_ros.action_clients.FromCallback):
    """
    Reads user information and plays a random greeting message
    """
    def __init__(self, name="GreetUser"):
        super().__init__(
            name=name,
            action_type=PlayTTS,
            action_name="/play_tts",
            wait_for_server_timeout_sec=0.0
        )
        
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)

        #Get the action prediction
        self.blackboard.register_key("predicted_action", access=py_trees.common.Access.READ)

    def get_goal(self):
        # Read user name
        try:
            raw_json = self.blackboard.speaker_info_json if self.blackboard.exists("speaker_info_json") else "{}"
            speaker_data = json.loads(raw_json)
            speaker_name = speaker_data.get("name", "amigo")
            speaker_id = str(speaker_data.get("id", "0"))
        except (TypeError, json.JSONDecodeError):
            speaker_name = "amigo"
            speaker_id = "0"


        action = self.blackboard.predicted_action if self.blackboard.exists("predicted_action") else ""

        # Check if the person is truly unknown
        if action:
            user = f" {speaker_name}" if speaker_name != "Unknown" and speaker_name != "amigo" else ""
            greetings = [
                f"¡Hola {user}! Veo que estás realizando la acción de {action}. ¿En qué te puedo ayudar?",
                f"¿Qué tal {user}? Parece que andas haciendo la acción de {action}.",
                f"¡Hola! Me he fijado en que estás realizando la acción de {action}, ¿Verdad {user}?"
            ]
        else:
            greetings = [
                "¡Hola! ¿En qué puedo ayudarte?",
                "¡Hola! Creo que no nos conocemos. Soy Sancho.",
                "¿Qué tal? ¡Dime!"
            ]

        action_goal = PlayTTS.Goal()    
        action_goal.text = random.choice(greetings)
        return action_goal


class IdentifyCentralTarget(py_trees_ros.service_clients.FromConstant):
    """
    Sends a service request to select a target and make its information available in the blackboard
    """
    def __init__(self, name="IdentifyCentralTarget", eps=0.0, min_samples=0):
        request = GetCentralFaceCluster.Request()
        request.eps = float(eps)
        request.min_samples = int(min_samples)

        super().__init__(
            name=name,
            service_type=GetCentralFaceCluster,
            service_name='/central_faces_cluster_node/get_central_cluster',
            service_request=request,
            wait_for_server_timeout_sec=0.0
        )

        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("target_names", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("target_ids", access=py_trees.common.Access.WRITE)

    def update(self):
        status = super().update()

        if status == py_trees.common.Status.SUCCESS:
            if self.response and self.response.ids and len(self.response.ids) > 0:
                speaker_data = {
                    "id": self.response.ids[0],
                    "name": self.response.names[0],
                }
                self.blackboard.speaker_info_json = json.dumps(speaker_data)
                # Keep these keys for backwards compatibility with older BT branches.
                self.blackboard.target_ids = list(self.response.ids)
                self.blackboard.target_names = list(self.response.names)
            else:
                return py_trees.common.Status.FAILURE

        return status


class WaitForSocialInteraction(py_trees.behaviour.Behaviour):
    """
    Hosts /social_state and waits until interaction manager reports completion.
    """

    def __init__(self, name="WaitForSocialInteraction", timeout_sec=60.0):
        super().__init__(name)
        self.timeout_sec = timeout_sec
        self.social_state_type = SocialState
        self.STATE_READY = 0
        self.STATE_FINISHED = 1
        self.STATE_ERROR = 2
        self.state = self.STATE_READY
        self.start_time = None

    def setup(self, **kwargs):
        self.node = kwargs["node"]
        self.srv = self.node.create_service(
            self.social_state_type,
            "/social_state",
            self._service_callback,
        )
        self.state = self.STATE_READY
        self.start_time = None

    def _service_callback(self, request, response):
        self.state = request.state
        return response

    def initialise(self):
        self.state = self.STATE_READY
        self.start_time = self.node.get_clock().now()

    def update(self):
        if self.state == self.STATE_FINISHED:
            return py_trees.common.Status.SUCCESS
        if self.state == self.STATE_ERROR:
            return py_trees.common.Status.FAILURE

        elapsed = (self.node.get_clock().now() - self.start_time).nanoseconds / 1e9
        if elapsed > self.timeout_sec:
            self.node.get_logger().warn(f"{self.name}: Timeout exceeded")
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING

class SetFaceMode(py_trees.behaviour.Behaviour):
    """Publishes a string to /face/mode to update the UI (idle, listening, thinking, speaking)"""
    def __init__(self, mode: str, name="SetFaceMode"):
        super().__init__(name=f"SetFace_{mode}")
        self.mode = mode
        self.publisher = None

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.publisher = self.node.create_publisher(String, "/face/mode", 10)

    def update(self):
        msg = String()
        msg.data = self.mode
        self.publisher.publish(msg)
        return py_trees.common.Status.SUCCESS

class ListenToUser(py_trees_ros.action_clients.FromConstant):
    """Action Client that triggers the VAD Transcriptor and writes text to blackboard"""
    def __init__(self, name="ListenToUser", timeout_sec=10.0):
        goal = ListenVoice.Goal()
        goal.timeout_sec = float(timeout_sec)

        super().__init__(
            name=name,
            action_type=ListenVoice,
            action_name="/listen_voice",
            action_goal=goal,
            wait_for_server_timeout_sec=0.0
        )
        
        # The parent class creates self.blackboard automatically
        self.blackboard.register_key("user_transcription", access=py_trees.common.Access.WRITE)

    def update(self):
        # 1. Let the parent class tick the ROS 2 Action Client
        status = super().update()
        
        # 2. Intercept the SUCCESS state to read the result
        if status == py_trees.common.Status.SUCCESS:
            self.logger.info("ListenVoice Action SUCCESS. Extracting result...")
            
            # Debug: What do we actually have here?
            if hasattr(self, 'result_message'):
                self.logger.info(f"Result message type: {type(self.result_message)}")
                # In ROS2, the result is usually in .result
                action_result = self.result_message.result
                self.logger.info(f"Action result: {action_result}")
            else:
                self.logger.error("No result_message found in node!")
                return py_trees.common.Status.FAILURE
            
            if action_result:
                # Store it and move on
                self.blackboard.user_transcription = getattr(action_result, 'text', "")
                self.logger.info(f"Blackboard updated with text: '{self.blackboard.user_transcription}'")
                return py_trees.common.Status.SUCCESS
            else:
                self.logger.info("Listening failed or timed out (action_result is None).")
                return py_trees.common.Status.FAILURE
                
        return status

class GenerateLLMResponse(py_trees_ros.service_clients.FromCallback):
    """Native PyTrees ROS 2 Service Client that dynamically builds its request"""
    def __init__(self, name="GenerateLLMResponse"):
        super().__init__(
            name=name,
            service_type=SanchoPrompt,
            service_name="sancho_hri/ai/prompt",
            wait_for_server_timeout_sec=0.0
        )
        
        # Register keys on the automatically created self.blackboard
        self.blackboard.register_key("user_transcription", access=py_trees.common.Access.READ)
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)
        self.blackboard.register_key("predicted_action", access=py_trees.common.Access.READ)

        self.blackboard.register_key("ai_response_text", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("ai_emotion", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("interaction_finished", access=py_trees.common.Access.WRITE)

    def get_request(self):
        """Called automatically by the parent's initialise() method"""
        text = self.blackboard.user_transcription if self.blackboard.exists("user_transcription") else ""
        current_action = self.blackboard.predicted_action if self.blackboard.exists("predicted_action") else "desconocida"
        raw_speaker_data = self.blackboard.speaker_info_json if self.blackboard.exists("speaker_info_json") else "{}"
        try:
            speaker_data = json.loads(raw_speaker_data)
            user_id = str(speaker_data.get("id", "Unknown"))
            user_name = str(speaker_data.get("name", "Unknown"))
        except (TypeError, json.JSONDecodeError):
            user_id = "Unknown"
            user_name = "Unknown"

        # Build and return the fresh request
        req = SanchoPrompt.Request()
        req.chat_id = "0"
        req.text = text
        req.args_json = json.dumps({"user_id": user_id, "user_name": user_name, "current_user_action": current_action})
        req.mode = "normal"
        
        self.logger.info(f"Generating LLM response for: '{text}'")
        return req

    def update(self):
        # Let the parent class check the ROS 2 future
        status = super().update()

        if status == py_trees.common.Status.SUCCESS:
            try:
                value = json.loads(self.response.value_json)
                
                # Use .get("text") with a fallback to .get("response") just in case
                response_text = value.get("text", value.get("response", "Ha habido un fallo al pensar."))
                
                is_finished = value.get("finished", False)
                self.blackboard.ai_response_text = response_text
                self.blackboard.ai_emotion = value.get("emotion", "neutral")
                self.blackboard.interaction_finished = is_finished
                
                if is_finished:
                    self.logger.info("LLM signaled end of conversation.")
                
                self.logger.info(f"LLM Response: {self.blackboard.ai_response_text} (Finished: {is_finished})")
                
            except Exception as e:
                self.logger.error(f"Error parsing SanchoPrompt response: {e}")
                self.blackboard.ai_response_text = "Me he liado un poco, perdona."
                self.blackboard.ai_emotion = "sad"
                
        elif status == py_trees.common.Status.FAILURE:
            self.logger.error("LLM Service call failed or wasn't ready.")
            self.blackboard.ai_response_text = "Perdona, no he podido conectar con mi cerebro."
            self.blackboard.ai_emotion = "sad"
            
        # Return the actual status (RUNNING, SUCCESS, or FAILURE)
        return status
    

import py_trees
from py_trees_ros import action_clients
from py_trees.common import Status
from py_trees.blackboard import Blackboard
from ollama import Client

class GenerateResponseAction(py_trees.behaviour.Behaviour):
    """
    Genera una respuesta contextualizada usando Gemma3:4b basada en el 
    historial de chat, la acción predicha y el input del usuario.
    """
    def __init__(self, name="GenerateResponseAction"):
        super().__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.client = Client(host='http://10.2.26.241:11434')

        # Claves de LECTURA
        self.blackboard.register_key(key="predicted_action", access=py_trees.common.Access.READ)
        # Asumo que el nodo ListenToUser guarda lo que dice el usuario en esta clave:
        self.blackboard.register_key(key="user_transcription", access=py_trees.common.Access.READ)
        
        # Clave de LECTURA/ESCRITURA (para mantener la memoria viva)
        self.blackboard.register_key(key="chat_history", access=py_trees.common.Access.WRITE)

        # Clave de ESCRITURA (la que leerá el nodo RespondUser)
        self.blackboard.register_key(key="ai_response_text", access=py_trees.common.Access.WRITE)

    def setup(self, **kwargs):
        """Inicializa el historial vacío la primera vez que se monta el árbol."""
        if not self.blackboard.exists("chat_history"):
            self.blackboard.chat_history = ""

    def update(self):
        try:
            #Recuperar los datos del contexto
            accion = self.blackboard.predicted_action if self.blackboard.exists("predicted_action") else "desconocida"
            mensaje_usuario = self.blackboard.user_transcription if self.blackboard.exists("user_transcription") else ""
            historial = self.blackboard.chat_history if self.blackboard.exists("chat_history") else ""

            # Si no hemos escuchado nada del usuario, fallamos para que el árbol lo gestione
            if not mensaje_usuario:
                self.logger.warning("No hay mensaje del usuario en 'user_transcription'.")
                return Status.FAILURE

            #Construir prompt
            prompt_llm = f"""
### ROL
Eres Sancho, un robot asistente inteligente, curioso y muy amable. Tu voz debe sonar natural y cercana, como la de un compañero que está en la misma habitación que el usuario.

### INSTRUCCIONES DE CONTEXTO
Para generar tu respuesta, debes realizar este proceso mental:
1. **Analiza el HISTORIAL**: Identifica de qué estáis hablando para no repetir saludos y mantener el hilo.
2. **Observa las ACCIONES RECIENTES**: Úsalas como contexto visual. Si el usuario cambia de actividad, puedes comentarlo de forma natural.
3. **Responde al MENSAJE DEL USUARIO**: Es tu prioridad actual, pero debe estar influenciada por los dos puntos anteriores.

### DATOS DE ENTRADA
- [HISTORIAL DE CHAT (Memoria)]: 
{historial}

- [ACCIONES QUE VEO AHORA]: 
{accion}

- [MENSAJE DEL USUARIO A RESPONDER]: 
{mensaje_usuario}

### REGLAS DE ORO (SALIDA ESTRICTA)
- Genera EXCLUSIVAMENTE el texto que dirás en voz alta.
- Máximo 2 frases cortas.
- NO uses etiquetas como "Sancho:", "Robot:" ni "[ROBOT]".
- NO expliques por qué respondes eso ni des introducciones.
- Si el historial está vacío, preséntate brevemente; si ya hay charla, ve directo al grano.

RESPUESTA DE SANCHO:
"""

          
            self.logger.info("Generando respuesta contextual con Gemma3:4b...")
            respuesta = self.client.chat(
                model='gemma3:4b',
                messages=[{'role': 'user', 'content': prompt_llm}], 
                options={
                    'temperature': 0.6,  
                    'top_p': 0.8,
                    'num_predict': 175,
                },
            )

            # Extraer y limpiar la respuesta
            respuesta_sancho = respuesta.message.content.strip()

            #Guardar la respuesta para que el nodo de TTS (RespondUser) hable
            self.blackboard.ai_response_text = respuesta_sancho
            self.logger.info(f"Respuesta de Sancho: {respuesta_sancho}")

            # Actualizar el historial para el siguiente turno
            nuevo_intercambio = f"Usuario: {mensaje_usuario}\nSancho: {respuesta_sancho}\n---\n"
            self.blackboard.chat_history += nuevo_intercambio

            return Status.SUCCESS

        except KeyError as e:
            self.logger.error(f"Falta una clave en la Blackboard: {str(e)}")
            return Status.FAILURE
        except Exception as e:
            self.logger.error(f"Error de conexión con Ollama o fallo interno: {str(e)}")
            return Status.FAILURE

    
class RespondUser(py_trees_ros.action_clients.AttributesFromBlackboard):
    """Reads AI text from blackboard and sends to PlayTTS Action Server"""
    def __init__(self, name="RespondUser", text_bb_key="ai_response_text"):
        super().__init__(
            name=name,
            action_type=PlayTTS,
            action_name="/play_tts",
            goal_fields={'text': text_bb_key}, # {Goal Field: BB Key}
            wait_for_server_timeout_sec=0.0
        )


class FormatActionMessage(py_trees.behaviour.Behaviour):
    """Convierte la etiqueta de la acción cruda en una frase natural para el TTS."""
    def __init__(self, name="FormatActionMessage"):
        super().__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.client = Client(host = 'http://10.2.26.241:11434')

        # Leemos la predicción de la acción 
        self.blackboard.register_key(key="predicted_action", access=py_trees.common.Access.READ)

        # Escribimos el mensaje final
        self.blackboard.register_key(key="speech_message", access=py_trees.common.Access.WRITE)

        #Empezamos a escribir el chat_history
        self.blackboard.register_key(key="chat_history", access=py_trees.common.Access.WRITE)

    def update(self):
        try:
            accion = self.blackboard.predicted_action
            prompt_saludo = f"Eres Sancho, un robot social simpático. El usuario que tienes enfrente está realizando la acción: '{accion}'. Genera una frase natural y amigable en español para saludarle o iniciar una conversación relacionada con lo que está haciendo el usuario. No uses comillas."

            respuesta_saludo = self.client.chat(
            model='gemma3:4b',
            messages=[{'role': 'user', 'content': prompt_saludo}], 
            options={
                    'temperature':0.6,  
                    'top_p': 0.8,
                    'num_predict': 175,
            },
            )

            # Guardamos la frase en la Blackboard
            saludoSancho = respuesta_saludo.message.content.strip()
            self.blackboard.speech_message = saludoSancho
            self.blackboard.chat_history = f"Sancho: {saludoSancho}\n---\n"
            self.logger.info(f"Mensaje generado: {saludoSancho}")
            
            return py_trees.common.Status.SUCCESS
            
        except KeyError:
            self.logger.error("No se encontró 'predicted_action' en la Blackboard.")
            return py_trees.common.Status.FAILURE

class SetAudioSessionBehavior(py_trees_ros.service_clients.FromConstant):
    """
    Enables or disables the audio gateway stream (OWW and ROS publishing).
    """
    def __init__(self, active: bool, name="SetAudioSession"):
        request = SetAudioSession.Request()
        request.active = active

        super().__init__(
            name=f"{name}_{'Active' if active else 'Inactive'}",
            service_type=SetAudioSession,
            service_name='/sancho_audio/set_audio_session',
            service_request=request,
            wait_for_server_timeout_sec=0.0
        )

class CheckSilence(py_trees.behaviour.Behaviour):
    """
    Reads the user transcription. If it is empty or whitespace, 
    it ends the interaction and aborts the current sequence.
    """
    def __init__(self, name="CheckSilence"):
        super().__init__(name)
        self.blackboard = py_trees.blackboard.Client(name=name)
        self.blackboard.register_key("user_transcription", access=py_trees.common.Access.READ)
        self.blackboard.register_key("interaction_finished", access=py_trees.common.Access.WRITE)

    def update(self):
        text = self.blackboard.get("user_transcription")
        
        # If text is None, empty, or just spaces
        if not text or text.strip() == "":
            self.logger.info("Silence detected. Aborting conversation turn.")
            self.blackboard.set("interaction_finished", True)
            return py_trees.common.Status.FAILURE 
            
        return py_trees.common.Status.SUCCESS