"""Environment block must always populate the schema-required fields."""
from __future__ import annotations

from adtc_profiler import environment


def test_capture_participant() -> None:
    block = environment.capture("participant_laptop")
    assert block["measured_on"] == "participant_laptop"
    assert isinstance(block["cpu_model"], str) and block["cpu_model"]
    assert isinstance(block["ram_gb"], (int, float)) and block["ram_gb"] >= 1
    assert isinstance(block["gpu"], str)
    assert isinstance(block["os"], str) and block["os"]


def test_capture_audit() -> None:
    block = environment.capture("audit_cloud_vm")
    assert block["measured_on"] == "audit_cloud_vm"
