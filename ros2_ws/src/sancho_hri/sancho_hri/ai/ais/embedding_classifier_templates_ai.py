from .base import ModularAI
from .intent_classifiers import EmbeddingClassifier
from .intent_executors import IntentExecutor
from .response_generators import TemplatesGenerator

from ..engines import HRIEngine, EmbeddingEngine


class EmbeddingClassifierTemplatesAI(ModularAI):

    def __init__(self):
        node = HRIEngine.create_client_node()
        hri_engine = HRIEngine(node)
        embedding_engine = EmbeddingEngine(node)

        llm_classifier = EmbeddingClassifier(embedding_engine)
        intent_executor = IntentExecutor(hri_engine)
        templates_generator = TemplatesGenerator()

        super().__init__(llm_classifier, intent_executor, templates_generator)
