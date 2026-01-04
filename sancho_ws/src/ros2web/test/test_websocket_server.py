import pytest
from unittest.mock import AsyncMock, MagicMock
from ros2web.websocket_server import WebSocketServer


class DummyWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.remote_address = ("127.0.0.1", 1234)

    async def send(self, msg):
        self.sent.append(msg)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        raise StopAsyncIteration()
    
    async def close(self):
        pass


@pytest.mark.asyncio
async def test_handler_processes_messages():
    # Arrange
    events = []
    server = WebSocketServer(
        on_message=lambda key, msg: events.append(("msg", key, msg)),
        on_user_connect=lambda key: events.append(("connect", key)),
        on_user_disconnect=lambda key: events.append(("disconnect", key)),
    )
    ws = DummyWebSocket(["hello"])

    # Act
    await server._handler(ws)

    # Assert
    assert events == [
        ("connect", "127.0.0.1:1234"),
        ("msg", "127.0.0.1:1234", "hello"),
        ("disconnect", "127.0.0.1:1234"),
    ]
    assert server.get_connection_count() == 0

@pytest.mark.asyncio
async def test_send_message():
    # Arrange
    server = WebSocketServer(None, None, None)
    client = AsyncMock()

    # Act
    await server._send_message(client, "data")

    # Assert
    client.send.assert_called_once_with("data")

def test_send_message_sync():
    # Arrange
    server = WebSocketServer(None, None, None)
    client = AsyncMock()
    server._send_message = AsyncMock()

    # Act
    server.send_message(client, "hello")

    # Assert
    server._send_message.assert_called_once_with(client, "hello")

def test_broadcast_message_sync():
    # Arrange
    server = WebSocketServer(None, None, None)
    client1 = AsyncMock()
    client2 = AsyncMock()
    server.clients = {"1": client1, "2": client2}
    server._send_to_all = AsyncMock()

    # Act
    server.broadcast_message("notice")

    # Assert
    server._send_to_all.assert_called_once_with("notice")

def test_get_client_and_connection_count():
    # Arrange
    server = WebSocketServer(None, None, None)
    mock_ws = MagicMock()
    server.clients["abc"] = mock_ws

    # Act
    client = server.get_client("abc")
    count = server.get_connection_count()

    # Assert
    assert client == mock_ws
    assert count == 1
