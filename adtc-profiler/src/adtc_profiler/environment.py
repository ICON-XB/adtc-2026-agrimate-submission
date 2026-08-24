"""Capture environment block: cpu_model, ram_gb, gpu, os."""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Literal

import psutil


def cpu_model() -> str:
    """Best-effort CPU model string. Linux reads /proc/cpuinfo; macOS uses sysctl."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    elif system == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            )
            return out.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return platform.processor() or "unknown"


def ram_gb() -> float:
    """Total RAM in GiB, rounded to nearest 0.1."""
    return round(psutil.virtual_memory().total / (1024**3), 1)


def gpu_description() -> str:
    """Best-effort GPU string. Returns "none" if no GPU detected."""
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                text=True,
                timeout=5,
            )
            names = [line.strip() for line in out.splitlines() if line.strip()]
            if names:
                return ", ".join(names)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    # macOS Apple Silicon has integrated GPU but no nvidia-smi
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "integrated only"
    return "none"


def os_description() -> str:
    """Best-effort OS description matching expected examples like 'Ubuntu 22.04.4 LTS'."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                fields = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        fields[k] = v.strip('"')
            pretty = fields.get("PRETTY_NAME")
            if pretty:
                return pretty
        except OSError:
            pass
    return platform.platform()


def capture(measured_on: Literal["participant_laptop", "audit_cloud_vm"]) -> dict:
    """Build the `environment` block of the report."""
    return {
        "measured_on": measured_on,
        "cpu_model": cpu_model(),
        "ram_gb": ram_gb(),
        "gpu": gpu_description(),
        "os": os_description(),
    }
