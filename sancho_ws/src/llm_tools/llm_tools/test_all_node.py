import os
import json

import rclpy
from rclpy.node import Node

from dotenv import load_dotenv

from llm_msgs.srv import Prompt, Embedding, LoadModel, UnloadModel
from llm_msgs.msg import LoadModel as LoadModelMsg, ProviderModel
from llm_tools.models import PROVIDER, MODELS, NEEDS_API_KEY


class TestAllModelsNode(Node):

    def __init__(self):
        super().__init__("test_all_models")
        load_dotenv()

        self.cli_prompt = self.create_client(Prompt, 'llm_tools/prompt')
        self.cli_embedding = self.create_client(Embedding, 'llm_tools/embedding')
        self.cli_load = self.create_client(LoadModel, 'llm_tools/load_model')
        self.cli_unload = self.create_client(UnloadModel, 'llm_tools/unload_model')

        self.successful_tests = []
        self.failed_tests = []

    def wait_for_service(self, client):
        if not client.wait_for_service(timeout_sec=3.0):
            self.get_logger().error(f"Service {client.srv_name} not available.")
            return False
        return True

    def call_sync(self, client, request):
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def get_api_key_for(self, provider):
        if provider not in NEEDS_API_KEY:
            return ""
        if provider == PROVIDER.OPENAI:
            return os.environ.get("OPENAI_API_KEY", "")
        elif provider == PROVIDER.GEMINI:
            return os.environ.get("GEMINI_API_KEY", "")
        elif provider in {PROVIDER.MISTRAL, PROVIDER.GEMMA, PROVIDER.LLAMA}:
            return os.environ.get("HUGGING_FACE_API_KEY", "")
        return ""

    def get_models_from_enum(self, model_enum_group, provider):
        try:
            enum_class = getattr(model_enum_group, provider.name.upper())
            return [str(m) for m in enum_class]
        except AttributeError:
            return []

    def load_model(self, provider, model, api_key=""):
        if not self.wait_for_service(self.cli_load):
            return False
        req = LoadModel.Request()
        item = LoadModelMsg(provider=provider, models=[model], api_key=api_key)
        req.items = [item]
        res = self.call_sync(self.cli_load, req)
        for r in res.results:
            self.get_logger().info(f"📦 Cargado {provider}/{model}: {r.message}")
            return r.success
        return False

    def unload_model(self, provider, model):
        if not self.wait_for_service(self.cli_unload):
            return
        req = UnloadModel.Request()
        item = ProviderModel(provider=provider, models=[model])
        req.items = [item]
        res = self.call_sync(self.cli_unload, req)
        for r in res.results:
            self.get_logger().info(f"🧹 Descargado {provider}/{model}: {r.message}")

    def test_prompt(self, provider, model):
        if not self.wait_for_service(self.cli_prompt):
            return False, "Servicio no disponible"
        req = Prompt.Request()
        req.provider = provider
        req.model = model
        req.prompt_system = "You are a test bot."
        req.messages_json = ""
        req.user_input = "Hello!"
        req.parameters_json = json.dumps({"temperature": 0.0, "max_tokens": 60})
        res = self.call_sync(self.cli_prompt, req)
        if res.success:
            self.get_logger().info(f"✅ Prompt [{provider}/{model}] → {res.response}")
            return True, ""
        else:
            self.get_logger().error(f"❌ Prompt [{provider}/{model}] → {res.message}")
            return False, res.message

    def test_embedding(self, provider, model):
        if not self.wait_for_service(self.cli_embedding):
            return False, "Servicio no disponible"
        req = Embedding.Request()
        req.provider = provider
        req.model = model
        req.user_input = "This is a test embedding input."
        res = self.call_sync(self.cli_embedding, req)
        if res.success:
            self.get_logger().info(f"✅ Embedding [{provider}/{model}] → dim={len(res.embedding)}")
            return True, ""
        else:
            self.get_logger().error(f"❌ Embedding [{provider}/{model}] → {res.message}")
            return False, res.message

    def run_all_tests(self):
        self.get_logger().info("🧪 Iniciando pruebas individuales por modelo...")

        for provider in PROVIDER:
            llm_models = self.get_models_from_enum(MODELS.LLM, provider)
            emb_models = self.get_models_from_enum(MODELS.EMBEDDING, provider)

            if not llm_models and not emb_models:
                self.get_logger().info(f"⏭️  {provider} no tiene modelos definidos.")
                continue

            api_key = self.get_api_key_for(provider)

            for model in llm_models:
                self.get_logger().info(f"\n🚀 Probando LLM {provider}/{model}")
                if self.load_model(provider, model, api_key):
                    success, error = self.test_prompt(provider, model)
                    self.unload_model(provider, model)
                    if success:
                        self.successful_tests.append(f"{provider}/{model}")
                    else:
                        self.failed_tests.append((f"{provider}/{model}", error))
                else:
                    self.failed_tests.append((f"{provider}/{model}", "Error al cargar"))

            for model in emb_models:
                self.get_logger().info(f"\n🚀 Probando embedding {provider}/{model}")
                if self.load_model(provider, model, api_key):
                    success, error = self.test_embedding(provider, model)
                    self.unload_model(provider, model)
                    if success:
                        self.successful_tests.append(f"{provider}/{model}")
                    else:
                        self.failed_tests.append((f"{provider}/{model}", error))
                else:
                    self.failed_tests.append((f"{provider}/{model}", "Error al cargar"))

        self.print_summary()

    def print_summary(self):
        self.get_logger().info("\n📋 RESUMEN FINAL")
        self.get_logger().info("✅ Modelos exitosos:")
        for name in self.successful_tests:
            self.get_logger().info(f"   - {name}")

        self.get_logger().info("\n❌ Modelos fallidos:")
        for name, error in self.failed_tests:
            self.get_logger().info(f"   - {name}: {error}")

        self.get_logger().info("\n🔚 Pruebas completadas.")


def main(args=None):
    rclpy.init(args=args)
    node = TestAllModelsNode()
    node.run_all_tests()
    node.destroy_node()
    rclpy.shutdown()
