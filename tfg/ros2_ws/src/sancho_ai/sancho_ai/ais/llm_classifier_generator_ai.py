from .base import ModularAI
from .intent_classifiers import LLMClassifier
from .intent_executors import IntentExecutor
from .response_generators import LLMGenerator

from ..engines import HRIEngine, LLMEngine


class LLMClassifierGeneratorAI(ModularAI):

    def __init__(self):
        node = HRIEngine.create_client_node()
        hri_engine = HRIEngine(node)
        llm_engine = LLMEngine(node)

        llm_classifier = LLMClassifier(llm_engine)
        intent_executor = IntentExecutor(hri_engine)
        llm_generator = LLMGenerator(hri_engine, llm_engine)

        super().__init__(llm_classifier, intent_executor, llm_generator)
