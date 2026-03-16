from enum import Enum
from typing import Type

from .base.ai import AI

from .dummy_ai import DummyAI
from .simple_templates_ai import SimpleTemplatesAI
from .llm_classifier_templates_ai import LLMClassifierTemplatesAI
from .llm_classifier_generator_ai import LLMClassifierGeneratorAI
from .embedding_classifier_templates_ai import EmbeddingClassifierTemplatesAI


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value
    
class AIType(SmartStrEnum):
    DUMMY = "DUMMY"
    SIMPLE_TEMPLATES = "SIMPLE"
    LLM_CLASSIFIER_TEMPLATES = "LLM_CLASSIFIER_TEMPLATES"
    LLM_CLASSIFIER_GENERATOR = "LLM_CLASSIFIER_GENERATOR"
    EMBEDDING_CLASSIFIER_TEMPLATES = "EMBEDDING_CLASSIFIER_TEMPLATES"


AI_CLASSES: dict[AIType, Type[AI]] = {
    AIType.DUMMY: DummyAI,
    AIType.SIMPLE_TEMPLATES: SimpleTemplatesAI,
    AIType.LLM_CLASSIFIER_TEMPLATES: LLMClassifierTemplatesAI,
    AIType.LLM_CLASSIFIER_GENERATOR: LLMClassifierGeneratorAI,
    AIType.EMBEDDING_CLASSIFIER_TEMPLATES: EmbeddingClassifierTemplatesAI
}

def create_sancho_ai(ai_type: AIType) -> AI:
    AI_CLASS = AI_CLASSES.get(ai_type)
    if not AI_CLASS:
        raise ValueError(f"AI type '{ai_type}' is not registered.")
    
    return AI_CLASS()
