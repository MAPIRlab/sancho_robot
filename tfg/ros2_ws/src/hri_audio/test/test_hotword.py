import numpy as np
from unittest.mock import Mock, patch
from hri_audio.utils.stt_hotword import STTHotword


# Test: _check_hotword should return True if name is present
def test_check_hotword_positive():
    # Arrange
    hotword = STTHotword(stt_request_fn=Mock(), name="Sancho")

    # Act
    result = hotword._check_hotword("Hola Sancho")

    # Assert
    assert result is True

# Test: _check_hotword should return False if name is not present
def test_check_hotword_negative():
    # Arrange
    hotword = STTHotword(stt_request_fn=Mock(), name="Sancho")

    # Act
    result = hotword._check_hotword("Hello robot")

    # Assert
    assert result is False

# Test: _check_hotword should normalize accents and punctuation
def test_check_hotword_unicode_and_punctuation():
    # Arrange
    hotword = STTHotword(stt_request_fn=Mock(), name="Sancho")

    # Act
    result = hotword._check_hotword("¡Sánchø!")

    # Assert
    assert result is True

# Test: _check_hotword returns False for empty transcript
def test_check_hotword_empty():
    # Arrange
    hotword = STTHotword(stt_request_fn=Mock(), name="Sancho")

    # Act
    result = hotword._check_hotword("")

    # Assert
    assert result is False

# Test: _transcribe should return empty string on exception
def test_transcribe_handles_exception():
    # Arrange
    def failing_stt(audio, rate):
        raise RuntimeError("fail")

    hotword = STTHotword(stt_request_fn=failing_stt)

    # Act
    result = hotword._transcribe(np.array([1, 2], dtype=np.int16), 16000)

    # Assert
    assert result == ""

# Test: detect should call _transcribe and _check_hotword once if enough audio
def test_detect_calls_transcribe_and_check():
    # Arrange
    stt_fn = Mock(return_value="ignored")
    hotword = STTHotword(stt_request_fn=stt_fn, max_seconds=0.1)

    with patch.object(STTHotword, "_transcribe", return_value="test") as mock_trans, \
         patch.object(STTHotword, "_check_hotword", return_value=False) as mock_check:

        # Act
        hotword.detect([0] * 1600, 16000)

        # Assert
        mock_trans.assert_called_once()
        mock_check.assert_called_once_with("test")

# Test: detect returns True if hotword is found
def test_detect_returns_true_on_match():
    # Arrange
    def fake_stt(audio, rate):
        return "oye sancho ven"

    hotword = STTHotword(stt_request_fn=fake_stt, name="sancho", max_seconds=0.01)

    # Act
    detected = hotword.detect([1]*200, 16000)

    # Assert
    assert detected is True

# Test: detect returns False if hotword not present
def test_detect_returns_false_if_not_found():
    # Arrange
    def fake_stt(audio, rate):
        return "sin coincidencia"

    hotword = STTHotword(stt_request_fn=fake_stt, name="sancho", max_seconds=0.01)

    # Act
    detected = hotword.detect([1]*200, 16000)

    # Assert
    assert detected is False

# Test: detect returns False if buffer not yet full
def test_detect_returns_false_if_buffer_incomplete():
    # Arrange
    hotword = STTHotword(stt_request_fn=lambda a, r: "sancho", max_seconds=0.1)

    # Act
    result = hotword.detect([1]*800, 16000)  # 800 samples < 0.1s

    # Assert
    assert result is False

# Test: buffer resets after detection
def test_detect_resets_buffer_after_detection():
    # Arrange
    hotword = STTHotword(stt_request_fn=lambda a, r: "sancho", max_seconds=0.01)

    # Act
    hotword.detect([1]*200, 16000)  # Llama a detectar y llena buffer

    # Assert
    assert len(hotword.buffer) == 0
