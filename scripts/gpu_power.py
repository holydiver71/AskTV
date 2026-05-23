"""GPU power management helpers using `nvidia-smi`.

This module provides two helpers:
- `set_gpu_power_limit(watts: int)`: enables persistence mode and sets a power limit
- `reset_gpu_power_limit()`: disables persistence mode to restore factory defaults

These functions assume the invoking process has the required privileges to
modify GPU settings (run with `sudo` or as root). They deliberately call
`nvidia-smi` directly (no embedded `sudo`) so callers control privilege
escalation and error handling.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional


class NvidiaSMIError(RuntimeError):
    pass


def _ensure_nvidia_smi_available() -> None:
    if shutil.which("nvidia-smi") is None:
        raise NvidiaSMIError("nvidia-smi not found in PATH — NVIDIA utilities are required")


def set_gpu_power_limit(watts: int) -> None:
    """Enable persistence mode and set the GPU power limit to `watts`.

    Raises `NvidiaSMIError` on failure; callers can decide whether to abort.
    """
    _ensure_nvidia_smi_available()
    try:
        subprocess.run(["nvidia-smi", "-pm", "1"], check=True, capture_output=True)
        subprocess.run(["nvidia-smi", "-pl", str(int(watts))], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode().strip() if exc.stderr else str(exc)
        raise NvidiaSMIError(f"Failed to set GPU power limit: {stderr}") from exc


def reset_gpu_power_limit() -> None:
    """Restore factory behaviour by disabling persistence mode.

    This removes any programmatically enforced static power limit and returns
    the driver to its normal dynamic power management.
    """
    try:
        _ensure_nvidia_smi_available()
        subprocess.run(["nvidia-smi", "-pm", "0"], check=True, capture_output=True)
    except NvidiaSMIError:
        # propagate the clearer message
        raise
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode().strip() if exc.stderr else str(exc)
        # Don't raise here — resetting on exit should try best-effort and
        # otherwise warn the user.
        print(f"Warning: Failed to reset GPU power limit: {stderr}", file=sys.stderr)
