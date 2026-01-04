from unittest.mock import Mock
from sancho_ai.ais.base.modular_ai import ModularAI
from sancho_ai.prompts.commands.commands import COMMANDS


# Clase dummy concreta para instanciar ModularAI
class DummyModularAI(ModularAI):
    pass

# Test: pipeline completo cuando la intención es conocida
def test_modular_ai_pipeline_known_intent():
    # Arrange
    classifier = Mock()
    executor = Mock()
    generator = Mock()

    classifier.classify.return_value = (
        COMMANDS.TAKE_PICTURE, {"foo": 1}, "prov", "model"
    )
    executor.execute.return_value = (
        "details", "ok", {"data": 42}
    )
    generator.generate_response.return_value = (
        "done", "happy", "gprov", "gmodel"
    )

    ai = DummyModularAI(classifier, executor, generator)

    # Act
    value, intent, args, prov, model = ai.on_message("hi", ["h"])

    # Assert
    classifier.classify.assert_called_once_with("hi", ["h"])
    executor.execute.assert_called_once_with(COMMANDS.TAKE_PICTURE, {"foo": 1})
    generator.generate_response.assert_called_once_with(
        "details", "ok", COMMANDS.TAKE_PICTURE, {"foo": 1}, "hi", ["h"]
    )

    assert value == {
        "text": "done",
        "emotion": "happy",
        "data": {"data": 42}
    }
    assert intent == COMMANDS.TAKE_PICTURE
    assert args == {"foo": 1}
    assert prov == "gprov"
    assert model == "gmodel"

# Test: pipeline alternativo cuando la intención es UNKNOWN
def test_modular_ai_pipeline_unknown_intent():
    # Arrange
    classifier = Mock()
    executor = Mock()
    generator = Mock()

    classifier.classify.return_value = (
        COMMANDS.UNKNOWN, {}, "prov", "model"
    )
    generator.continue_conversation.return_value = (
        "ok", "neutral", "gprov", "gmodel"
    )

    ai = DummyModularAI(classifier, executor, generator)

    # Act
    value, intent, args, prov, model = ai.on_message("hello")

    # Assert
    classifier.classify.assert_called_once_with("hello", [])
    executor.execute.assert_not_called()
    generator.continue_conversation.assert_called_once_with("hello", [])

    assert value == {
        "text": "ok",
        "emotion": "neutral",
        "data": {}
    }
    assert intent == COMMANDS.UNKNOWN
    assert args == {}
    assert prov == "gprov"
    assert model == "gmodel"
