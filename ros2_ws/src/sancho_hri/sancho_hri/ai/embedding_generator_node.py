import os
import json
from pathlib import Path

import rclpy
from rclpy.node import Node
from dotenv import load_dotenv
import numpy as np

from .prompts.commands import IntentExamplesRegistry

from sancho_interfaces.srv import Embedding, LLMLoadModel, LLMUnloadModel
from sancho_interfaces.msg import LLMLoadModel as LoadModelMsg, ProviderModel
from llm_tools.models import PROVIDER, MODELS, NEEDS_API_KEY


class EmbeddingGeneratorNode(Node):

    def __init__(self):
        super().__init__('generate_embeddings_node')
        load_dotenv()

        self.cli_embedding = self.create_client(Embedding, 'llm_tools/embedding')
        self.cli_load = self.create_client(LLMLoadModel, 'llm_tools/load_model')
        self.cli_unload = self.create_client(LLMUnloadModel, 'llm_tools/unload_model')

        self.output_file = Path(__file__).parent / 'prompts/commands/intent_embeddings.json'
        self.examples = IntentExamplesRegistry.get_intent_examples()

        # Intentamos cargar resultados previos si existen
        if self.output_file.exists():
            with open(self.output_file, 'r') as f:
                self.output = json.load(f)
        else:
            self.output = {}

    def wait_for_service(self, client):
        if not client.wait_for_service(timeout_sec=5.0):
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
        return os.environ.get(f"{provider.name.upper()}_API_KEY", "")

    def load_model(self, provider, model_name):
        if not self.wait_for_service(self.cli_load):
            return False
        req = LLMLoadModel.Request()
        item = LoadModelMsg(provider=provider.value, models=[model_name], api_key=self.get_api_key_for(provider))
        req.items = [item]
        res = self.call_sync(self.cli_load, req)
        return res.results[0].success if res and res.results else False

    def unload_model(self, provider, model_name):
        if not self.wait_for_service(self.cli_unload):
            return
        req = LLMUnloadModel.Request()
        item = ProviderModel(provider=provider.value, models=[model_name])
        req.items = [item]
        self.call_sync(self.cli_unload, req)

    def save_output(self):
        with open(self.output_file, 'w') as f:
            json.dump(self.output, f, indent=2)

    def generate_embeddings(self):
        for provider in PROVIDER:
            model_enum = getattr(MODELS.EMBEDDING, provider.name.upper(), None)
            if model_enum is None:
                continue

            for model in model_enum:
                model_name = str(model)
                self.get_logger().info(f"🚀 Generando embeddings con {provider}/{model_name}")

                # Si ya están todos los embeddings de ese modelo, saltamos
                if all(
                    intent in self.output and
                    all(
                        phrase in self.output[intent] and model_name in self.output[intent][phrase]
                        for phrase in phrases
                    )
                    for intent, phrases in self.examples.items()
                ):
                    self.get_logger().info(f"⏭️  {provider}/{model_name} ya procesado. Saltando.")
                    continue

                if not self.load_model(provider, model_name):
                    self.get_logger().error(f"❌ No se pudo cargar {provider}/{model_name}")
                    continue

                for intent, phrases in self.examples.items():
                    if intent not in self.output:
                        self.output[intent] = {}
                    for phrase in phrases:
                        if phrase not in self.output[intent]:
                            self.output[intent][phrase] = {}

                        if model_name in self.output[intent][phrase]:
                            continue  # ya está hecho

                        embedding = self.get_embedding(provider.value, model_name, phrase)
                        if embedding is not None:
                            self.output[intent][phrase][model_name] = embedding.tolist()

                self.unload_model(provider, model_name)
                self.save_output()
                self.get_logger().info(f"💾 Guardado parcial tras {provider}/{model_name}")

        self.get_logger().info("✅ Embeddings generados correctamente.")

    def get_embedding(self, provider, model_name, text):
        if not self.wait_for_service(self.cli_embedding):
            return None
        req = Embedding.Request()
        req.provider = provider
        req.model = model_name
        req.user_input = text
        res = self.call_sync(self.cli_embedding, req)
        if res and res.success:
            return np.array(res.embedding)
        else:
            self.get_logger().error(f"⚠️ Fallo al generar embedding para '{text}' con {provider}/{model_name}")
            return None


def main(args=None):
    rclpy.init(args=args)

    node = EmbeddingGeneratorNode()
    node.generate_embeddings()
    node.destroy_node()

    rclpy.shutdown()
