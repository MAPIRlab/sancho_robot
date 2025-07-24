import os
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from dotenv import load_dotenv

from llm_msgs.srv import LoadModel, UnloadModel
from llm_msgs.msg import LoadModel as LoadModelMsg, ProviderModel
from llm_tools.models import PROVIDER, MODELS, NEEDS_API_KEY

from .engines import LLMEngine
from .ais import LLMAskingAI


class TestAskingNode(Node):

    def __init__(self):
        super().__init__('asking_eval_llm_node')
        load_dotenv()

        self.cli_load = self.create_client(LoadModel, 'llm_tools/load_model')
        self.cli_unload = self.create_client(UnloadModel, 'llm_tools/unload_model')
        self.service_node = LLMEngine.create_client_node("tests_eval_node")

        self.base_dir = Path(__file__).parent
        self.tests_name_file = self.base_dir / 'prompts/tests/tests_name_dataset.json'
        self.tests_confirm_file = self.base_dir / 'prompts/tests/tests_confirm_dataset.json'
        self.results_name_file = self.base_dir / 'prompts/tests/results_name.json'
        self.results_confirm_file = self.base_dir / 'prompts/tests/results_confirm.json'

        self.results_name = self.load_results(self.results_name_file)
        self.results_confirm = self.load_results(self.results_confirm_file)

    def load_results(self, path):
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def save_results(self):
        with open(self.results_name_file, 'w') as f:
            json.dump(self.results_name, f, indent=2)
        with open(self.results_confirm_file, 'w') as f:
            json.dump(self.results_confirm, f, indent=2)

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

    def run_all_tests(self):
        with open(self.tests_name_file) as f:
            name_tests = json.load(f)
        with open(self.tests_confirm_file) as f:
            confirm_tests = json.load(f)

        for provider in PROVIDER:
            model_enum = getattr(MODELS.LLM, provider.name.upper(), None)
            if not model_enum:
                continue

            if provider.value not in self.results_name:
                self.results_name[provider.value] = {}
            if provider.value not in self.results_confirm:
                self.results_confirm[provider.value] = {}

            for model in model_enum:
                model_name = str(model)

                skip_name = model_name in self.results_name[provider.value]
                skip_confirm = model_name in self.results_confirm[provider.value]

                if skip_name and skip_confirm:
                    self.get_logger().info(f"⏭️  Saltando {provider}/{model_name} (ya evaluado)")
                    continue

                self.get_logger().info(f"🚀 Evaluando {provider}/{model_name}")

                if not self.load_model(provider, model_name):
                    self.get_logger().error(f"❌ No se pudo cargar el modelo {provider}/{model_name}")
                    if not skip_name:
                        self.results_name[provider.value][model_name] = {"error": "No se pudo cargar el modelo"}
                    if not skip_confirm:
                        self.results_confirm[provider.value][model_name] = {"error": "No se pudo cargar el modelo"}
                    self.save_results()
                    continue

                ai = LLMAskingAI(self.service_node, provider=provider.value, model=model_name)

                def metric_template():
                    return {
                        "total_tests": 0,
                        "correct": 0,
                        "valid_json": 0,
                        "present_field": 0,
                        "field_match": 0,
                        "field_present_but_wrong": 0,
                        "empty_response": 0,
                        "total_time_sec": 0.0,
                        #"test_results": []
                    }

                if not skip_name:
                    metrics_name = metric_template()
                    for idx, test in enumerate(name_tests):
                        user_input = test["user_input"]
                        expected = test["expected_output"]
                        self.get_logger().info(f"🧪 Name Test {idx+1}/{len(name_tests)}: '{user_input}'")
                        start = time.time()
                        result, _, _, meta = ai.get_name(user_input, testing=True)
                        elapsed = time.time() - start

                        correct = result == expected
                        present = meta.get("name_said_present", False)
                        valid = meta.get("valid_json", False)
                        empty = meta.get("empty_response", False)

                        metrics_name["total_tests"] += 1
                        metrics_name["total_time_sec"] += elapsed
                        metrics_name["valid_json"] += int(valid)
                        metrics_name["present_field"] += int(present)
                        metrics_name["field_match"] += int(correct and present)
                        metrics_name["field_present_but_wrong"] += int(present and not correct)
                        metrics_name["empty_response"] += int(empty)
                        metrics_name["correct"] += int(correct)

                        icon = "✅" if correct else "❌"
                        self.get_logger().info(f"    {icon} Result: {result} | Expected: {expected} | Time: {elapsed:.3f}s")
                        self.get_logger().info(f"       Real response: {meta['real_response']}")
                        #metrics_name["test_results"].append({"input": user_input, "result": result, "expected": expected, "success": correct})

                    self.results_name[provider.value][model_name] = metrics_name

                if not skip_confirm:
                    metrics_confirm = metric_template()
                    for idx, test in enumerate(confirm_tests):
                        user_input = test["user_input"]
                        expected = test["expected_output"]
                        self.get_logger().info(f"🧪 Confirm Test {idx+1}/{len(confirm_tests)}: '{user_input}'")
                        start = time.time()
                        result, _, _, meta = ai.confirm_name(user_input, testing=True)
                        elapsed = time.time() - start

                        correct = result == expected
                        present = meta.get("answer_said_present", False)
                        valid = meta.get("valid_json", False)
                        empty = meta.get("empty_response", False)

                        metrics_confirm["total_tests"] += 1
                        metrics_confirm["total_time_sec"] += elapsed
                        metrics_confirm["valid_json"] += int(valid)
                        metrics_confirm["present_field"] += int(present)
                        metrics_confirm["field_match"] += int(correct and present)
                        metrics_confirm["field_present_but_wrong"] += int(present and not correct)
                        metrics_confirm["empty_response"] += int(empty)
                        metrics_confirm["correct"] += int(correct)

                        icon = "✅" if correct else "❌"
                        self.get_logger().info(f"    {icon} Result: {result} | Expected: {expected} | Time: {elapsed:.3f}s")
                        self.get_logger().info(f"       Real response: {meta['real_response']}")
                        #metrics_confirm["test_results"].append({"input": user_input, "result": result, "expected": expected, "success": correct})

                    self.results_confirm[provider.value][model_name] = metrics_confirm

                self.save_results()
                self.unload_model(provider, model_name)

        self.get_logger().info("✅ Evaluación AskingAI finalizada.")

    def load_model(self, provider, model_name):
        if not self.wait_for_service(self.cli_load):
            return False
        req = LoadModel.Request()
        item = LoadModelMsg(provider=provider.value, models=[model_name], api_key=self.get_api_key_for(provider))
        req.items = [item]
        res = self.call_sync(self.cli_load, req)
        return res.results[0].success if res and res.results else False

    def unload_model(self, provider, model_name):
        if not self.wait_for_service(self.cli_unload):
            return False
        req = UnloadModel.Request()
        item = ProviderModel(provider=provider.value, models=[model_name])
        req.items = [item]
        self.call_sync(self.cli_unload, req)

def main(args=None):
    rclpy.init(args=args)

    node = TestAskingNode()
    node.run_all_tests()
    node.destroy_node()

    rclpy.shutdown()