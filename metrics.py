"""Agentless Linux metrics via SSH."""

from __future__ import annotations

import re
from typing import Any

import paramiko

import config


def _run(client: paramiko.SSHClient, command: str) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=config.SSH_CONNECT_TIMEOUT)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err and not out:
        raise RuntimeError(err.strip()[:300])
    return out


def _parse_cpu(stat1: str, stat2: str) -> float | None:
    def idle_total(text: str) -> tuple[int, int] | None:
        for line in text.splitlines():
            if line.startswith("cpu "):
                parts = [int(x) for x in line.split()[1:]]
                if len(parts) < 4:
                    return None
                idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
                return idle, sum(parts)
        return None

    a = idle_total(stat1)
    b = idle_total(stat2)
    if not a or not b:
        return None
    idle_delta = b[0] - a[0]
    total_delta = b[1] - a[1]
    if total_delta <= 0:
        return None
    usage = 100.0 * (1.0 - idle_delta / total_delta)
    return round(max(0.0, min(100.0, usage)), 1)


def _parse_memory(meminfo: str) -> dict[str, Any]:
    values: dict[str, int] = {}
    for line in meminfo.splitlines():
        match = re.match(r"^(\w+):\s+(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2))

    total_kb = values.get("MemTotal", 0)
    available_kb = values.get("MemAvailable")
    if available_kb is None:
        available_kb = values.get("MemFree", 0) + values.get("Buffers", 0) + values.get(
            "Cached", 0
        )
    used_kb = max(0, total_kb - available_kb)
    total_mb = round(total_kb / 1024, 1)
    used_mb = round(used_kb / 1024, 1)
    pct = round((used_kb / total_kb) * 100, 1) if total_kb else None
    return {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "available_mb": round(available_kb / 1024, 1),
        "percent": pct,
    }


def _parse_network(netdev: str) -> list[dict[str, Any]]:
    interfaces: list[dict[str, Any]] = []
    for line in netdev.splitlines()[2:]:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        cols = rest.split()
        if len(cols) < 16:
            continue
        rx = int(cols[0])
        tx = int(cols[8])
        interfaces.append(
            {
                "name": name,
                "rx_bytes": rx,
                "tx_bytes": tx,
                "rx_human": _human_bytes(rx),
                "tx_human": _human_bytes(tx),
            }
        )
    return interfaces


def _human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{n} B"


def _parse_ports(ss_out: str) -> list[dict[str, str]]:
    ports: list[dict[str, str]] = []
    for line in ss_out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        proto, state, local = parts[0], parts[1], parts[4]
        if state not in ("LISTEN", "UNCONN"):
            # Keep listening TCP/UDP; ss -tuln uses LISTEN / UNCONN
            if "LISTEN" not in state and proto not in ("udp", "udp6"):
                continue
        ports.append({"proto": proto, "state": state, "local": local})
    # Deduplicate while preserving order
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for p in ports:
        key = (p["proto"], p["state"], p["local"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:80]


def collect_metrics(server: dict[str, Any]) -> dict[str, Any]:
    """Fetch live metrics for one server. Never raises — returns status + error."""
    result: dict[str, Any] = {
        "ok": False,
        "error": None,
        "cpu_percent": None,
        "memory": None,
        "network": [],
        "ports": [],
    }
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=server["host"],
            port=int(server["port"]),
            username=server["ssh_user"],
            password=server["ssh_password"],
            timeout=config.SSH_CONNECT_TIMEOUT,
            allow_agent=False,
            look_for_keys=False,
        )
        stat1 = _run(client, "cat /proc/stat")
        _run(client, "sleep 0.4")
        stat2 = _run(client, "cat /proc/stat")
        meminfo = _run(client, "cat /proc/meminfo")
        netdev = _run(client, "cat /proc/net/dev")
        try:
            ss_out = _run(client, "ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null")
        except RuntimeError:
            ss_out = ""

        result["cpu_percent"] = _parse_cpu(stat1, stat2)
        result["memory"] = _parse_memory(meminfo)
        result["network"] = _parse_network(netdev)
        result["ports"] = _parse_ports(ss_out)
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001 — demo: surface any SSH/parse failure
        result["error"] = str(exc)[:400] or "unreachable"
    finally:
        client.close()
    return result


def collect_summary(server: dict[str, Any]) -> dict[str, Any]:
    metrics = collect_metrics(server)
    return {
        "id": server["id"],
        "name": server["name"],
        "host": server["host"],
        "port": server["port"],
        "ok": metrics["ok"],
        "error": metrics["error"],
        "cpu_percent": metrics["cpu_percent"],
        "memory_percent": (metrics["memory"] or {}).get("percent") if metrics["memory"] else None,
        "iface_count": len(metrics["network"]),
        "port_count": len(metrics["ports"]),
    }
