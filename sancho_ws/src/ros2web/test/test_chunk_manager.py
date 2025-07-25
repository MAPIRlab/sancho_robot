from ros2web.chunk_manager import ChunkManager


# Test: Fragmentation of message into chunks
def test_msg_to_chunks_basic():
    # Arrange
    manager = ChunkManager(max_chunk_size=4)

    # Act
    chunks = manager.msg_to_chunks("abcdef")

    # Assert
    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].final is False
    assert chunks[0].data == "abcd"
    assert chunks[1].chunk_index == 1
    assert chunks[1].final is True
    assert chunks[1].data == "ef"

# Test: Reassembly of chunks into full message
def test_chunk_to_msg_reassembles():
    # Arrange
    manager = ChunkManager(max_chunk_size=3)
    msg_id = "1"

    # Act
    part = manager.chunk_to_msg(msg_id, 0, False, "abc")
    final = manager.chunk_to_msg(msg_id, 1, True, "def")

    # Assert
    assert part is None
    assert final == "abcdef"
    assert msg_id not in manager.buffers

# Test: Out-of-order chunks are reassembled correctly
def test_chunk_to_msg_out_of_order():
    # Arrange
    manager = ChunkManager()
    msg_id = "42"

    # Act
    manager.chunk_to_msg(msg_id, 1, False, "DEF")
    result = manager.chunk_to_msg(msg_id, 0, False, "ABC")
    final = manager.chunk_to_msg(msg_id, 2, True, "GHI")

    # Assert
    assert result is None
    assert final == "ABCDEFGHI"
    assert msg_id not in manager.buffers

# Test: Multiple messages are handled independently
def test_chunk_to_msg_multiple_ids():
    # Arrange
    manager = ChunkManager()

    # Act
    manager.chunk_to_msg("a", 0, False, "Hello ")
    manager.chunk_to_msg("b", 0, False, "Goodbye ")
    manager.chunk_to_msg("a", 1, True, "World")
    result_b = manager.chunk_to_msg("b", 1, True, "Moon")

    # Assert
    assert result_b == "Goodbye Moon"
    assert "a" not in manager.buffers
    assert "b" not in manager.buffers
