import pytest
from sancho_web_assistant.database.system_database import SystemDatabase, CONSTANTS


@pytest.fixture
def db():
    def _create(tmp_path):
        return SystemDatabase(db_path=str(tmp_path / "test_system.db"))
    return _create


def test_create_and_retrieve_log(db, tmp_path):
    # Arrange
    database = db(tmp_path)
    
    # Act
    database.create_log(
        level=CONSTANTS.LEVEL.INFO,
        origin=CONSTANTS.ORIGIN.ROS,
        action=CONSTANTS.ACTION.ADD_CLASS,
        actor="sancho",
        target="class_001",
        message="Clase añadida correctamente",
        metadata_json='{"foo": "bar"}'
    )

    logs = database.get_all_logs()

    # Assert
    assert len(logs) == 1
    log = logs[0]
    assert log['level'] == "INFO"
    assert log['origin'] == "ROS"
    assert log['action'] == "add_class"
    assert log['actor'] == "sancho"
    assert log['target'] == "class_001"
    assert log['message'] == "Clase añadida correctamente"
    assert log['metadata'] == '{"foo": "bar"}'


def test_get_log_by_id(db, tmp_path):
    # Arrange
    database = db(tmp_path)
    database.create_log(
        level=CONSTANTS.LEVEL.WARNING,
        origin=CONSTANTS.ORIGIN.WEB,
        action=CONSTANTS.ACTION.LOAD_TTS_MODEL,
        actor="frontend",
        message="Modelo cargado parcialmente",
        metadata_json=None
    )
    all_logs = database.get_all_logs()
    log_id = all_logs[0]['id']

    # Act
    log = database.get_log_by_id(log_id)

    # Assert
    assert log['id'] == log_id
    assert log['level'] == "WARNING"
    assert log['origin'] == "WEB"
    assert log['action'] == "load_tts_model"
    assert log['actor'] == "frontend"
    assert log['metadata'] is None


@pytest.mark.parametrize("level", ["INVALID", "", None])
def test_invalid_level_raises_error(db, tmp_path, level):
    database = db(tmp_path)
    with pytest.raises(ValueError):
        database.create_log(
            level=level,
            origin=CONSTANTS.ORIGIN.ROS,
            action=CONSTANTS.ACTION.ADD_CLASS
        )


@pytest.mark.parametrize("origin", ["DEVICE", "APP", None])
def test_invalid_origin_raises_error(db, tmp_path, origin):
    database = db(tmp_path)
    with pytest.raises(ValueError):
        database.create_log(
            level=CONSTANTS.LEVEL.DEBUG,
            origin=origin,
            action=CONSTANTS.ACTION.ADD_CLASS
        )


@pytest.mark.parametrize("action", ["DO_SOMETHING", "", None])
def test_invalid_action_raises_error(db, tmp_path, action):
    database = db(tmp_path)
    with pytest.raises(ValueError):
        database.create_log(
            level=CONSTANTS.LEVEL.INFO,
            origin=CONSTANTS.ORIGIN.ROS,
            action=action
        )
