"""In-memory server inventory (cleared on process restart)."""

from __future__ import annotations

import threading
import uuid
from typing import Any

_lock = threading.Lock()
_servers: dict[str, dict[str, Any]] = {}


def list_servers() -> list[dict[str, Any]]:
    with _lock:
        return [dict(s) for s in _servers.values()]


def get_server(server_id: str) -> dict[str, Any] | None:
    with _lock:
        server = _servers.get(server_id)
        return dict(server) if server else None


def add_server(
    name: str,
    host: str,
    port: int,
    ssh_user: str,
    ssh_password: str,
) -> dict[str, Any]:
    server = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "host": host.strip(),
        "port": int(port),
        "ssh_user": ssh_user.strip(),
        "ssh_password": ssh_password,
    }
    with _lock:
        _servers[server["id"]] = server
    return dict(server)


def remove_server(server_id: str) -> bool:
    with _lock:
        return _servers.pop(server_id, None) is not None
