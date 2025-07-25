from hri_vision.database.faceprints_database import FaceprintsDatabase


# Test: Add and get faceprint
def test_add_and_get_faceprint():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")

    # Act
    entry = db.add("Alice", [1.0], "img", 0.9)

    # Assert
    assert db.get_by_id(entry["id"]) == entry
    assert entry["name"] == "Alice"

# Test: Update modifies stored data
def test_update_faceprint():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")
    entry = db.add("Bob", [1.0], "img", 0.9)

    # Act
    db.update(entry["id"], {"name": "Robert"})

    # Assert
    assert db.get_by_id(entry["id"])["name"] == "Robert"

# Test: Remove deletes entry
def test_remove_faceprint():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")
    entry = db.add("Carol", [1.0], "img", 0.9)

    # Act
    db.remove(entry["id"])

    # Assert
    assert db.get_by_id(entry["id"]) is None

# Test: Filter get_all by name
def test_get_all_by_name():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")
    db.add("Dave", [1.0], "img", 0.9)
    db.add("Eve", [2.0], "img", 0.8)

    # Act
    results = db.get_all("Eve")

    # Assert
    assert len(results) == 1
    assert results[0]["name"] == "Eve"

# Test: get_all_ids returns correct ids
def test_get_all_ids():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")
    a = db.add("Anna", [1.0], "img", 0.9)
    b = db.add("Ben", [2.0], "img", 0.8)

    # Act
    ids = db.get_all_ids()

    # Assert
    assert set(ids) == {a["id"], b["id"]}

# Test: update non-existent entry returns None
def test_update_nonexistent():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")

    # Act
    result = db.update("999", {"name": "Ghost"})

    # Assert
    assert result is None

# Test: features and size are lists of lists and integers
def test_add_feature_structure():
    # Arrange
    db = FaceprintsDatabase(db_mode="no_save")

    # Act
    entry = db.add("Frank", [0.1, 0.2], "img", 0.5)

    # Assert
    assert isinstance(entry["features"], list)
    assert isinstance(entry["features"][0], list)
    assert isinstance(entry["size"], list)
    assert entry["size"] == [1]
