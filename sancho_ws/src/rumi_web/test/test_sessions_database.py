import pytest
from rumi_web.database.sessions_database import SessionsDatabase


@pytest.fixture
def db():
    # Usamos un archivo temporal en /tmp (más real que ':memory:')
    def _create(tmp_path):
        return SessionsDatabase(db_path=str(tmp_path / "test_sessions.db"))
    return _create


def test_create_and_retrieve_session(db, tmp_path):
    # Arrange
    database = db(tmp_path)
    session_data = {
        'faceprint_id': 123,
        'start_time': "2024-01-01T12:00:00",
        'end_time': "2024-01-01T12:05:00",
        'detections': [
            ["2024-01-01T12:01:00", 0.9, 0.8, ""],
            ["2024-01-01T12:03:00", 0.85, 0.75, "image_base64_data"]
        ]
    }

    # Act
    database.create_session_with_detections(session_data)
    all_sessions = database.get_all_sessions()

    # Assert
    assert len(all_sessions) == 1
    session = all_sessions[0]
    assert session['faceprint_id'] == 123
    assert session['start_time'] == "2024-01-01T12:00:00"
    assert session['end_time'] == "2024-01-01T12:05:00"
    assert len(session['detections']) == 2
    assert session['detections'][0][3] == ""
    assert session['detections'][1][3] == "image_base64_data"


def test_get_session_by_id_and_faceprint_id(db, tmp_path):
    # Arrange
    database = db(tmp_path)
    session_data = {
        'faceprint_id': 999,
        'start_time': "2024-06-01T00:00:00",
        'end_time': "2024-06-01T00:05:00",
        'detections': [["2024-06-01T00:01:00", 0.95, 0.85, ""]]
    }

    # Act
    database.create_session_with_detections(session_data)
    all_sessions = database.get_all_sessions()
    session_id = all_sessions[0]['id']

    by_id = database.get_session_by_id(session_id)
    by_faceprint = database.get_sessions_by_faceprint_id(999)

    # Assert
    assert by_id['faceprint_id'] == 999
    assert len(by_faceprint) == 1
    assert by_faceprint[0]['start_time'] == "2024-06-01T00:00:00"


def test_get_detections_by_session(db, tmp_path):
    # Arrange
    database = db(tmp_path)
    session_data = {
        'faceprint_id': 1,
        'start_time': "2024-01-01T00:00:00",
        'end_time': "2024-01-01T00:10:00",
        'detections': [
            ["2024-01-01T00:01:00", 0.99, 0.88, "det1"],
            ["2024-01-01T00:02:00", 0.95, 0.80, "det2"]
        ]
    }

    # Act
    database.create_session_with_detections(session_data)
    session_id = database.get_all_sessions()[0]['id']
    detections = database.get_detections_by_session(session_id)

    # Assert
    assert len(detections) == 2
    assert detections[0][3] == "det1"
    assert detections[1][1] == 0.95
