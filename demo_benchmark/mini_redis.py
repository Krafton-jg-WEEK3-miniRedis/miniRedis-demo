from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Any

from .metrics import MetricsCollector


class RedisProtocolError(RuntimeError):
    pass


class RedisCommandError(RuntimeError):
    pass


@dataclass(slots=True)
class RedisResponse:
    value: Any
    bytes_sent: int
    bytes_received: int


class MiniRedisTCPClient:
    def __init__(self, host: str, port: int, timeout: float, metrics: MetricsCollector | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.metrics = metrics

    def execute(self, *parts: str) -> Any:
        payload = self._encode(parts)
        response = self._send(payload)
        return response.value

    def send_raw(self, payload: bytes) -> Any:
        response = self._send(payload)
        return response.value

    def ping(self) -> Any:
        return self.execute("PING")

    def set(self, key: str, value: str) -> Any:
        return self.execute("SET", key, value)

    def get(self, key: str) -> Any:
        return self.execute("GET", key)

    def delete(self, *keys: str) -> Any:
        return self.execute("DEL", *keys)

    def expire(self, key: str, seconds: int) -> Any:
        return self.execute("EXPIRE", key, str(seconds))

    def quit(self) -> Any:
        return self.execute("QUIT")

    def exit(self) -> Any:
        return self.execute("EXIT")

    def _send(self, payload: bytes) -> RedisResponse:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if self.metrics:
            self.metrics.connection_opened()
        try:
            sock.settimeout(self.timeout)
            sock.sendall(payload)
            buffer = sock.recv(65536)
            if not buffer:
                raise RedisProtocolError("Received empty response from Mini Redis.")
            if self.metrics:
                self.metrics.record_network(len(payload), len(buffer))
            value, consumed = self._decode(buffer)
            if consumed < len(buffer):
                # Keep only the first RESP frame for simple request/response usage.
                buffer = buffer[:consumed]
            return RedisResponse(value=value, bytes_sent=len(payload), bytes_received=len(buffer))
        finally:
            sock.close()
            if self.metrics:
                self.metrics.connection_closed()

    def _encode(self, parts: tuple[str, ...]) -> bytes:
        encoded = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            piece = str(part).encode("utf-8")
            encoded.append(f"${len(piece)}\r\n".encode("utf-8"))
            encoded.append(piece + b"\r\n")
        return b"".join(encoded)

    def _decode(self, payload: bytes) -> tuple[Any, int]:
        if not payload:
            raise RedisProtocolError("Cannot decode an empty RESP payload.")
        marker = chr(payload[0])
        if marker == "+":
            line, consumed = self._read_line(payload)
            return line.decode("utf-8"), consumed
        if marker == "-":
            line, consumed = self._read_line(payload)
            raise RedisCommandError(line.decode("utf-8"))
        if marker == ":":
            line, consumed = self._read_line(payload)
            return int(line), consumed
        if marker == "$":
            line, consumed = self._read_line(payload)
            length = int(line)
            if length == -1:
                return None, consumed
            start = consumed
            end = start + length
            if payload[end:end + 2] != b"\r\n":
                raise RedisProtocolError("Invalid bulk string terminator.")
            return payload[start:end].decode("utf-8"), end + 2
        if marker == "*":
            line, consumed = self._read_line(payload)
            count = int(line)
            items: list[Any] = []
            cursor = consumed
            for _ in range(count):
                item, size = self._decode(payload[cursor:])
                items.append(item)
                cursor += size
            return items, cursor
        raise RedisProtocolError(f"Unsupported RESP marker: {marker}")

    def _read_line(self, payload: bytes) -> tuple[bytes, int]:
        end = payload.find(b"\r\n")
        if end == -1:
            raise RedisProtocolError("RESP line termination not found.")
        return payload[1:end], end + 2


class MiniRedisStubClient:
    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self.metrics = metrics
        self.data: dict[str, str] = {}
        self.expirations: dict[str, float] = {}

    def ping(self) -> str:
        return "PONG"

    def set(self, key: str, value: str) -> str:
        self.data[key] = value
        self.expirations.pop(key, None)
        return "OK"

    def get(self, key: str) -> str | None:
        self._purge_expired(key)
        return self.data.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            self._purge_expired(key)
            if key in self.data:
                self.data.pop(key, None)
                self.expirations.pop(key, None)
                count += 1
        return count

    def expire(self, key: str, seconds: int) -> int:
        if key not in self.data:
            return 0
        self.expirations[key] = time.time() + seconds
        return 1

    def quit(self) -> str:
        return "OK"

    def exit(self) -> str:
        return "OK"

    def execute(self, *parts: str) -> Any:
        if not parts:
            raise RedisCommandError("ERR empty command")
        command = parts[0].upper()
        if command == "PING":
            return self.ping()
        if command == "SET" and len(parts) == 3:
            return self.set(parts[1], parts[2])
        if command == "GET" and len(parts) == 2:
            return self.get(parts[1])
        if command == "DEL" and len(parts) >= 2:
            return self.delete(*parts[1:])
        if command == "EXPIRE" and len(parts) == 3:
            return self.expire(parts[1], int(parts[2]))
        if command == "QUIT":
            return self.quit()
        if command == "EXIT":
            return self.exit()
        raise RedisCommandError("ERR unknown command or wrong arity")

    def send_raw(self, payload: bytes) -> Any:
        if not payload.startswith(b"*"):
            raise RedisProtocolError("ERR malformed RESP payload")
        raise RedisCommandError("ERR raw RESP execution is not supported by the stub")

    def _purge_expired(self, key: str) -> None:
        expiration = self.expirations.get(key)
        if expiration is not None and time.time() >= expiration:
            self.data.pop(key, None)
            self.expirations.pop(key, None)
