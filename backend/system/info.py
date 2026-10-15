from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import psutil


def get_system_stats() -> Dict[str, Any]:
    """Gather real-time CPU, RAM, disk, battery, and process stats safely."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_count(logical=True) or 1
    cpu_physical = psutil.cpu_count(logical=False) or cpu_cores

    # Memory
    mem = psutil.virtual_memory()
    total_gb = round(mem.total / (1024 ** 3), 1)
    used_gb = round(mem.used / (1024 ** 3), 1)
    avail_gb = round(mem.available / (1024 ** 3), 1)
    mem_percent = mem.percent

    # Disk
    drive = "C:\\" if os.name == "nt" else "/"
    try:
        disk = psutil.disk_usage(drive)
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_free_gb = round(disk.free / (1024 ** 3), 1)
        disk_percent = disk.percent
    except Exception:
        disk_total_gb, disk_free_gb, disk_percent = 0.0, 0.0, 0.0

    # Battery
    battery_info: Optional[Dict[str, Any]] = None
    try:
        bat = psutil.sensors_battery()
        if bat is not None:
            battery_info = {
                "percent": bat.percent,
                "plugged": bat.power_plugged,
            }
    except Exception:
        battery_info = None

    # Top processes by memory
    top_procs: List[Dict[str, Any]] = []
    try:
        for p in sorted(
            psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]),
            key=lambda x: (x.info.get("memory_percent") or 0),
            reverse=True,
        )[:5]:
            info = p.info
            top_procs.append({
                "pid": info.get("pid"),
                "name": info.get("name"),
                "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
            })
    except Exception:
        top_procs = []

    return {
        "cpu": {
            "percent": cpu_percent,
            "logical_cores": cpu_cores,
            "physical_cores": cpu_physical,
        },
        "memory": {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": avail_gb,
            "percent": mem_percent,
        },
        "disk": {
            "drive": drive,
            "total_gb": disk_total_gb,
            "free_gb": disk_free_gb,
            "percent": disk_percent,
        },
        "battery": battery_info,
        "top_processes": top_procs,
    }


def get_system_summary() -> str:
    """Return a concise one-line text summary for AI reasoning and prompt injection."""
    stats = get_system_stats()
    cpu = stats["cpu"]
    mem = stats["memory"]
    disk = stats["disk"]
    bat = stats["battery"]

    parts = [
        f"CPU: {cpu['percent']}% ({cpu['logical_cores']} cores)",
        f"RAM: {mem['used_gb']}/{mem['total_gb']} GB ({mem['percent']}%)",
        f"Disk {disk['drive']}: {disk['percent']}% used ({disk['free_gb']} GB free)",
    ]
    if bat is not None:
        status = "plugged in" if bat["plugged"] else "on battery"
        parts.append(f"Battery: {bat['percent']}% ({status})")

    return " | ".join(parts)
