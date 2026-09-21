"""Classification of exported pattern variables."""

from __future__ import annotations

from typing import Any

from .const import COUNTER_VAR_PREFIX, READONLY_VARS


def is_counter_var(name: str) -> bool:
    """cL, cRot, cDrop... edge-trigger counters used by game controllers."""
    return (
        len(name) >= 2
        and name.startswith(COUNTER_VAR_PREFIX)
        and name[1].isupper()
    )


def is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify_vars(variables: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Split exported vars into (writable numbers, read-only sensors)."""
    numbers: set[str] = set()
    sensors: set[str] = set()
    for name, value in variables.items():
        if is_counter_var(name) or not is_numeric(value):
            continue
        if name.lower() in READONLY_VARS:
            sensors.add(name)
        else:
            numbers.add(name)
    return numbers, sensors
