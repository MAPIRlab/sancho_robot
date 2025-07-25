import gc
import ast
import rclpy
import importlib
from rclpy.node import Node

from speech_msgs.msg import LoadUnloadResult, ModelItem
from speech_msgs.srv import STT, STTGetActiveModel, STTGetModels, STTSetActiveModel, LoadModel, UnloadModel

from .stt.stt_model import STTModel
from .utils import SileroVAD
from .models import STT_MODELS, STT_NEEDS_API_KEY


class STTNode(Node):
    
    MODELS_CLASS_MAP = {
        STT_MODELS.WHISPER: ("speech_tools.stt.whisper_stt", "WhisperSTT"),
        STT_MODELS.GOOGLE: ("speech_tools.stt.google_stt", "GoogleSTT"),
    }

    def __init__(self):
        super().__init__("stt")
        
        self.model_map = {}
        self.active_model = None

        self.vad = SileroVAD()

        self.get_all_srv = self.create_service(STTGetModels, 'speech_tools/stt/get_all_models', self.handle_get_all_models)
        self.get_active_srv = self.create_service(STTGetActiveModel, 'speech_tools/stt/get_active_model', self.handle_get_active_model)
        self.get_available_srv = self.create_service(STTGetModels, 'speech_tools/stt/get_available_models', self.handle_get_available_models)
        self.stt_srv = self.create_service(STT, 'speech_tools/stt', self.handle_stt)
        self.load_model_srv = self.create_service(LoadModel, 'speech_tools/stt/load_model', self.handle_load_model)
        self.unload_model_srv = self.create_service(UnloadModel, 'speech_tools/stt/unload_model', self.handle_unload_model)
        self.set_active_model_srv = self.create_service(STTSetActiveModel, 'speech_tools/stt/set_active_model', self.handle_set_active_model)

        self._init_from_parameters()

        self.get_logger().info('STT Node inicializado correctamente')

    def handle_get_all_models(self, request, response):
        models_names = set(request.models)
        if not models_names:
            models_names = list(STT_MODELS)

        self.get_logger().info(f"📖 Get All Models service for models: {models_names}")

        response.models = []
        for model_name in models_names:
            if hasattr(STT_MODELS, model_name.upper()):
                response.models.append(ModelItem(model=model_name, needs_api_key=(model_name in STT_NEEDS_API_KEY)))

        return response

    def handle_get_active_model(self, request, response):
        self.get_logger().info(f"📖 Get Active Model service")

        if self.active_model:
            response.model = self.active_model

        return response

    def handle_get_available_models(self, request, response):
        models_names = set(request.models)
        if not models_names:
            models_names = list(STT_MODELS)

        self.get_logger().info(f"📖 Get Available Models service for models: {models_names}")
 
        response.models = []
        for model_name in models_names:
            if model_name in self.model_map:
                response.models.append(ModelItem(model=model_name, needs_api_key=(model_name in STT_NEEDS_API_KEY)))

        return response

    def handle_stt(self, request, response):
        try:
            model_name = self._get_or_active(request.model)
            model = self._get_model(model_name)

            if self.vad.has_human_voice(request.audio, request.sample_rate):
                text = model.transcribe(
                    audio=request.audio, 
                    sample_rate=request.sample_rate
                )

                self._fill_response(response, "OK", True, model_name, text)
                self.get_logger().info(f"✅ STT done using model {model_name}")
            else:
                self._fill_response(response, "OK", True, self.vad.__class__.__name__, "")
                self.get_logger().info(f"✅ STT done using model but VAD indicated that THERE IS NO HUMAN VOICE")
        except Exception as e:
            self._fill_response(response, str(e), False)
            self.get_logger().error(f"❌ STT service failed: {str(e)}")

        return response

    def handle_load_model(self, request, response):
        self.get_logger().info(f"📖 Load model service")

        response.results = []
        for item in request.items:
            result = LoadUnloadResult(model=item.model)
            try:
                model = self._try_load_model(item.model, item.api_key) # Con crearse ya esta cargado

                result.success, result.message = True, "Model loaded successfully"
                self.get_logger().info(f"✅ Model {item.model} loaded")
            except Exception as e:
                result.success, result.message = False, f"Error loading model: {str(e)}"
                self.get_logger().error(f"❌ Error loading model {item.model}: {str(e)}")

            response.results.append(result)

        return response

    def handle_unload_model(self, request, response):
        self.get_logger().info(f"📖 Unload model service")
        
        response.results = []
        for model_name in request.models:
            result = LoadUnloadResult(model=model_name)

            if self.active_model == model_name:
                result.success, result.message = False, f"Cannot unload model '{model_name}' because it is currently active"
                self.get_logger().warn(f"❌ Cannot unload active model '{model_name}'")
                response.results.append(result)
            elif model_name in self.model_map:
                try:
                    self.model_map[model_name].unload()
                    del self.model_map[model_name]
                    gc.collect()

                    result.success, result.message = True, "Model unloaded successfully"
                    self.get_logger().info(f"✅ Model {model_name} unloaded")
                except Exception as e:
                    result.success, result.message = False, f"Error unloading model: {str(e)}"
                    self.get_logger().error(f"❌ Error unloading model {model_name}: {str(e)}")
            else:
                result.success, result.message = False, "Model not found"
                self.get_logger().warn(f"❌ Model {model_name} not found in map")

            response.results.append(result)

        return response

    def handle_set_active_model(self, request, response):
        self.get_logger().info(f"📖 Set Active Model service. Model: {request.model}")
        response.success, response.message = self._set_active_model(request.model)

        return response

    def _init_from_parameters(self):
        models_to_load = self.parse_string_list(self.declare_parameter("load_models", "[]").get_parameter_value().string_value)
        active_model = self.declare_parameter("active_model", "").get_parameter_value().string_value

        for [model_name, api_key] in models_to_load:
            try:
                self._try_load_model(model_name, api_key)
                self.get_logger().info(f"🔄 Model '{model_name}' loaded from parameter")
            except Exception as e:
                self.get_logger().error(f"❌ Could not load model '{model_name}' from parameter: {e}")

        if active_model:
            success, message = self._set_active_model(active_model)
            if success:
                self.get_logger().info(f"✅ {message} from parameter")
            else:
                self.get_logger().warn(f"❌ {message}")

    def _set_active_model(self, model):
        if not model:
            return False, "Model must be specified"
        if model not in list(STT_MODELS):
            return False, f"Invalid model: {model}"
        if model not in self.model_map:
            return False, f"Model '{model}' is not loaded. You must load it first."

        self.active_model = model
        
        return True, f"Active model set to '{model}'"

    def _try_load_model(self, model_name, api_key=""):
        if model_name not in self.model_map:
            if model_name not in self.MODELS_CLASS_MAP:
                raise ValueError(f"Model '{model_name}' is not supported.")
            
            module_path, class_name = self.MODELS_CLASS_MAP[model_name]
            try:
                module = importlib.import_module(module_path)
                model_class = getattr(module, class_name)
            except Exception as e:
                raise ImportError(f"Could not load model '{model_name}': {e}")
            
            self.model_map[model_name] = model_class(api_key=api_key) if api_key else model_class()

        return self.model_map[model_name]

    def _get_or_active(self, model_name):
        if not model_name:
            if self.active_model:
                return self.active_model
            else:
                raise ValueError(f"No model specified and no active model")
        
        return model_name

    def _get_model(self, model_name) -> STTModel:
        if model_name not in self.model_map:
            raise ValueError(f"Model '{model_name}' is not loaded.")
        return self.model_map[model_name]

    def _fill_response(self, response, message, success, model_used="", text=""):
        response.model_used = model_used
        response.text = text
        response.message = message
        response.success = success

    def parse_string_list(self, raw_string) -> list[list[str]]:
        try:
            return ast.literal_eval(raw_string)
        except Exception:
            return []

def main(args=None):
    rclpy.init(args=args)

    node = STTNode()
    rclpy.spin(node)

    rclpy.shutdown()
