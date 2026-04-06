# Copyright 2025 Niklas Kaaf <nkaaf@protonmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Output Sender: WebsocketClient."""

import warnings

import websockets
from websockets.sync import client

from whisper_streaming import OutputSender, Word

__all__ = ["WebsocketClientSender"]


# TODO: Implement custom protocol strcture
# TODO: Implement handling of self signed certs for wss
class WebsocketClientSender(OutputSender):
    """Class implementing a WebSocket client, that sends the output to a server."""

    def __init__(
        self, host: str, port: int, path: str = "", protocol: str = "ws"
    ) -> None:
        """Initialize the WebSocket client sender.

        Args:
            host: Host of the WebSocket server.
            port: Port of the WebSocket server.
            path: Subdirectory to the WebSocket server (automatic '/' prefix).
            protocol: Protocol that the WebSocket server uses, current "ws" and "wss"
            are supported.

        Raises:
            ValueError: If ``protocol`` is not supported.
        """
        super().__init__()
        self.host = host
        self.port = port
        self.path = path if path.startswith("/") else f"/{path}"
        self.protocol = protocol
        if self.protocol not in ["ws", "wss"]:
            msg = f"Invalid protocol: {self.protocol}"
            raise ValueError(msg)

    def _do_output(self, data: Word) -> None:
        """Sending the output to the configured WebSocket server.

        Args:
            data: Output of STT.

        Returns:
            None

        Raises:
            OSError: If the TCP connection fails.
            :py:class:`websockets.exceptions.InvalidHandshake`: If the opening
                handshake fails.
            TimeoutError: If the opening handshake times out.
            :py:class:`websockets.exceptions.ConnectionClosed`: When the connection
                is closed.
        """
        try:
            with client.connect(
                f"{self.protocol}://{self.host}:{self.port}{self.path}"
            ) as websocket:
                websocket.send(f"RESULT {data.word}")
        except (
            websockets.exceptions.InvalidURI,
            websockets.exceptions.ConcurrencyError,
            TypeError,
        ):
            warnings.warn(
                "This exception should not be thrown because its cause should be "
                "caught earlier. Please report this.",
                stacklevel=1,
            )
            raise

    def _do_close(self) -> None:
        pass
