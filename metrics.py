"""Agentless Linux metrics via SSH (local /proc for loopback demo hosts)."""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import paramiko

import config

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


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


def _parse_ports_ss(ss_out: str) -> list[dict[str, str]]:
    """Parse `ss -tuln` (preferred)."""
    ports: list[dict[str, str]] = []
    for line in ss_out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        proto, state, local = parts[0], parts[1], parts[4]
        if state not in ("LISTEN", "UNCONN"):
            continue
        ports.append({"proto": proto, "state": state, "local": local})
    return _dedupe_ports(ports)


def _parse_ports_netstat(ns_out: str) -> list[dict[str, str]]:
    """Parse `netstat -tuln` (Local Address is col 4, State is last)."""
    ports: list[dict[str, str]] = []
    for line in ns_out.splitlines()[2:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        proto = parts[0]
        local = parts[3]
        state = parts[-1] if len(parts) >= 6 else "LISTEN"
        if not any(ch.isdigit() for ch in local):
            continue
        if proto.startswith("tcp") and state != "LISTEN":
            continue
        ports.append({"proto": proto, "state": state, "local": local})
    return _dedupe_ports(ports)


def _dedupe_ports(ports: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for p in ports:
        key = (p["proto"], p["state"], p["local"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:80]


def _parse_ports(raw: str) -> list[dict[str, str]]:
    if not raw.strip():
        return []
    first = raw.splitlines()[0].lower() if raw.splitlines() else ""
    if "netid" in first or first.startswith("state"):
        return _parse_ports_ss(raw)
    if "proto" in first or "active internet" in first:
        return _parse_ports_netstat(raw)
    # Heuristic: ss-style if second token looks like LISTEN/UNCONN
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if len(lines) >= 2 and len(lines[1].split()) >= 5 and lines[1].split()[1] in (
        "LISTEN",
        "UNCONN",
    ):
        return _parse_ports_ss(raw)
    return _parse_ports_ss(raw) or _parse_ports_netstat(raw)


def _empty_result() -> dict[str, Any]:
    return {
        "ok": False,
        "error": None,
        "cpu_percent": None,
        "memory": None,
        "network": [],
        "ports": [],
        "source": None,
    }


def _fill_from_proc_texts(
    result: dict[str, Any],
    stat1: str,
    stat2: str,
    meminfo: str,
    netdev: str,
    ports_raw: str,
    source: str,
) -> dict[str, Any]:
    result["cpu_percent"] = _parse_cpu(stat1, stat2)
    result["memory"] = _parse_memory(meminfo)
    result["network"] = _parse_network(netdev)
    result["ports"] = _parse_ports(ports_raw)
    result["ok"] = True
    result["error"] = None
    result["source"] = source
    return result


def _collect_local() -> dict[str, Any]:
    """Read metrics from this machine's /proc (demo fallback for loopback hosts)."""
    result = _empty_result()
    try:
        stat1 = Path("/proc/stat").read_text(encoding="utf-8", errors="replace")
        time.sleep(0.4)
        stat2 = Path("/proc/stat").read_text(encoding="utf-8", errors="replace")
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")
        netdev = Path("/proc/net/dev").read_text(encoding="utf-8", errors="replace")
        ports_raw = ""
        try:
            import subprocess

            ports_raw = subprocess.check_output(
                ["ss", "-tuln"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=config.SSH_CONNECT_TIMEOUT,
            )
        except Exception:
            try:
                import subprocess

                ports_raw = subprocess.check_output(
                    ["netstat", "-tuln"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=config.SSH_CONNECT_TIMEOUT,
                )
            except Exception:
                ports_raw = ""
        return _fill_from_proc_texts(
            result, stat1, stat2, meminfo, netdev, ports_raw, "local"
        )
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"local metrics failed: {exc}"[:400]
        return result


def _is_loopback(host: str) -> bool:
    return host.strip().lower() in _LOOPBACK


def collect_metrics(server: dict[str, Any]) -> dict[str, Any]:
    """Fetch live metrics for one server. Never raises — returns status + error."""
    result = _empty_result()
    host = (server.get("host") or "").strip()
    port = int(server.get("port") or 22)

    # Loopback demo path: collect from this host without SSH.
    # Avoids password/key setup when students monitor "localhost".
    if _is_loopback(host):
        if port not in (22, 0):
            # Still try local metrics but note the unusual SSH port.
            local = _collect_local()
            if local["ok"]:
                local["error"] = None
                return local
            result["error"] = (
                f"SSH port {port} is not reachable on loopback; "
                f"local fallback also failed: {local.get('error')}"
            )
            return result
        return _collect_local()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=server["ssh_user"],
            password=server["ssh_password"],
            timeout=config.SSH_CONNECT_TIMEOUT,
            banner_timeout=config.SSH_CONNECT_TIMEOUT,
            auth_timeout=config.SSH_CONNECT_TIMEOUT,
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

        return _fill_from_proc_texts(
            result, stat1, stat2, meminfo, netdev, ss_out, "ssh"
        )
    except Exception as exc:  # noqa: BLE001 — demo: surface any SSH/parse failure
        result["error"] = str(exc)[:400] or "unreachable"
        return result
    finally:
        client.close()


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
        "memory_percent": (metrics["memory"] or {}).get("percent")
        if metrics["memory"]
        else None,
        "iface_count": len(metrics["network"]),
        "port_count": len(metrics["ports"]),
        "source": metrics.get("source"),
    }


def collect_summaries(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect summaries in parallel so one slow host does not block the dashboard."""
    if not servers:
        return []
    if len(servers) == 1:
        return [collect_summary(servers[0])]

    by_id: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(servers))) as pool:
        futures = {pool.submit(collect_summary, s): s["id"] for s in servers}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                by_id[sid] = fut.result()
            except Exception as exc:  # noqa: BLE001
                server = next(s for s in servers if s["id"] == sid)
                by_id[sid] = {
                    "id": sid,
                    "name": server["name"],
                    "host": server["host"],
                    "port": server["port"],
                    "ok": False,
                    "error": str(exc)[:400],
                    "cpu_percent": None,
                    "memory_percent": None,
                    "iface_count": 0,
                    "port_count": 0,
                    "source": None,
                }
    return [by_id[s["id"]] for s in servers]
