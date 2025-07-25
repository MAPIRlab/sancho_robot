import datetime
from unittest.mock import Mock, patch

from rumi_web.database.session_manager import SessionManager


def test_process_detection_time_filter():
    # Arrange
    db = Mock()
    times = iter([2, 2.5, 4])

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return datetime.datetime.fromtimestamp(next(times))

    manager = SessionManager(db, timeout_seconds=5, time_between_detections=1)

    # Act
    with patch('rumi_web.database.session_manager.datetime', FakeDatetime):
        manager.process_detection('1', 0.8, 0.9)  # t=2 → se guarda
        manager.process_detection('1', 0.8, 0.9)  # t=2.5 → ignorada
        manager.process_detection('1', 0.8, 0.9)  # t=4 → se guarda

    # Assert
    session = manager.active_sessions['1']
    assert len(session['detections']) == 2


def test_session_closes_after_timeout():
    # Arrange
    db = Mock()
    times = iter([0, 1.5, 7])  # detecciones en 0 y 1.5, timeout en 7 (>5s)

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return datetime.datetime.fromtimestamp(next(times))

    manager = SessionManager(db, timeout_seconds=5)

    # Act
    with patch('rumi_web.database.session_manager.datetime', FakeDatetime):
        manager.process_detection('1', 0.9, 0.8)
        manager.process_detection('1', 0.9, 0.8)
        manager.check_timeouts()

    # Assert
    assert '1' not in manager.active_sessions
    db.create_session_with_detections.assert_called_once()


def test_get_last_seen_and_all_last_seen():
    # Arrange
    db = Mock()
    times = iter([0, 2, 2.1])  # llamadas a now(): 0 (detection), 2 (last_seen), 2.1 (all_last_seen)

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return datetime.datetime.fromtimestamp(next(times))

    manager = SessionManager(db)

    # Act
    with patch('rumi_web.database.session_manager.datetime', FakeDatetime):
        manager.process_detection('abc', 0.95, 0.9)
        last_seen = manager.get_last_seen('abc')
        all_last_seen = manager.get_all_last_seen()

    # Assert
    assert 1.9 < last_seen < 2.1
    assert 'abc' in all_last_seen
    assert 1.9 < all_last_seen['abc'] < 2.3


def test_detection_ignored_if_too_soon():
    # Arrange
    db = Mock()
    times = iter([10, 10.5])  # Solo 0.5s entre detecciones

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return datetime.datetime.fromtimestamp(next(times))

    manager = SessionManager(db, time_between_detections=1)

    # Act
    with patch('rumi_web.database.session_manager.datetime', FakeDatetime):
        manager.process_detection('2', 0.7, 0.8)
        manager.process_detection('2', 0.7, 0.8)

    # Assert
    session = manager.active_sessions['2']
    assert len(session['detections']) == 1  # La segunda fue ignorada
