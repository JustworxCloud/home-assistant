"""The Justworx capability taxonomy -> Home Assistant mapping.

This module is the heart of the adapter and deliberately has **no Home Assistant imports**,
so it can be unit-tested with plain Python. It implements the Home Assistant column of the
Justworx capability taxonomy, plus the small amount of state/command interpretation each entity
platform needs.

A "capability" here is `id_entry["capability"]` -- the semantic-type sub-object /api/v2 returns
on an ID (`{"type", "names", "secure"}`), *not* a separate list with its own controlId the way the
retired /api/dev/v1 gateway had it. Every function below takes the whole `id_entry` dict as it
appears in `device["ids"]` (idNumber, type, value, capability, stateKeywords, name, ...), because
state interpretation needs the ID's raw `value` alongside its `capability`.
"""

from __future__ import annotations

# capability type -> HA platform (the entity domain the capability becomes)
PLATFORM: dict[str, str] = {
    "Switch": "switch",
    "Light": "light",
    "Lock": "lock",
    "GarageDoor": "cover",
    "Cover": "cover",
    "ContactSensor": "binary_sensor",
    "MotionSensor": "binary_sensor",
    "TemperatureSensor": "sensor",
    "AnalogGauge": "sensor",
    "Thermostat": "climate",
    "Dimmer": "light",
    "FanSpeed": "fan",
}

# capability type -> HA device_class (where one applies)
DEVICE_CLASS: dict[str, str] = {
    "GarageDoor": "garage",
    "MotionSensor": "motion",
    "ContactSensor": "door",
    "TemperatureSensor": "temperature",
}

# The capability types this MVP actually instantiates as entities. Thermostat / Dimmer / FanSpeed
# are in the taxonomy but deferred (climate/fan platforms are a later pass), so they're excluded
# here rather than surfaced half-built.
SUPPORTED: frozenset[str] = frozenset(
    {"Switch", "Light", "Lock", "GarageDoor", "Cover", "ContactSensor", "MotionSensor",
     "TemperatureSensor", "AnalogGauge"}
)

# The HA platforms this integration sets up (derived from SUPPORTED via PLATFORM).
PLATFORMS: list[str] = sorted({PLATFORM[t] for t in SUPPORTED})

# DEFAULT CONVENTION, used only when `stateKeywords` does not say otherwise for this specific
# device: `high` is the "active" state (on/open/unlocked/detected), `low` is the "inactive" state
# (off/closed/locked). This is the same high/low vocabulary the raw digital ID write and read
# already use everywhere else in this API. It is NOT verified against real hardware wiring for
# Lock/GarageDoor specifically -- the retired /api/dev/v1 gateway resolved this server-side per
# capability and that resolution was never exposed, so this is a best-effort default. Confirm
# before treating a Lock entity's locked/unlocked state as ground truth on a device that has not
# set `stateKeywords` to say otherwise.
_ON_VALUES = {"on", "true", "1", "open", "opened", "unlocked", "detected", "motion", "high"}
_CLOSED_VALUES = {"closed", "close", "shut", "down", "low"}
_LOCKED_VALUES = {"locked", "lock", "low"}


def _capability(id_entry: dict) -> dict | None:
    return id_entry.get("capability")


def _semantic(id_entry: dict) -> str | None:
    """The human-readable word for this ID's current raw value, e.g. `high` -> `Open`.

    Prefers `stateKeywords` (author-set, authoritative for this specific piece of hardware --
    e.g. an active-low relay's `high` can mean "Closed"). Tries the raw value itself as a key
    first (`high`/`low`), then the numeric-level spelling (`1`/`0`) some `stateKeywords` are
    authored with instead. Falls back to the raw value itself, lowercased, when neither matches --
    which is what makes the DEFAULT high/low convention above apply.
    """
    value = id_entry.get("value")
    if value is None:
        return None
    v = str(value).lower()
    kw = id_entry.get("stateKeywords") or {}
    if v in kw:
        return str(kw[v]).lower()
    level = "1" if v == "high" else "0" if v == "low" else None
    if level is not None and level in kw:
        return str(kw[level]).lower()
    return v


def platform_for(cap_type: str) -> str | None:
    return PLATFORM.get(cap_type)


def device_class_for(cap_type: str) -> str | None:
    return DEVICE_CLASS.get(cap_type)


def is_supported(id_entry: dict) -> bool:
    cap = _capability(id_entry)
    return bool(cap) and cap.get("type") in SUPPORTED


def display_name(id_entry: dict) -> str:
    cap = _capability(id_entry) or {}
    names = cap.get("names") or []
    if names:
        return names[0]
    return id_entry.get("name") or cap.get("type") or "Justworx"


# ---- state interpretation (per entity family) ----

def switch_is_on(id_entry: dict) -> bool | None:
    """switch / light: on when the semantic value reads truthy/'on'."""
    v = _semantic(id_entry)
    if v is None:
        return None
    return v in _ON_VALUES


def lock_is_locked(id_entry: dict) -> bool | None:
    v = _semantic(id_entry)
    return v in _LOCKED_VALUES if v is not None else None


def cover_is_closed(id_entry: dict) -> bool | None:
    """cover / garage: closed when value reads closed; open when it reads the active state;
    unknown (e.g. "moving") -> None (HA shows unknown)."""
    v = _semantic(id_entry)
    if v is None:
        return None
    if v in _CLOSED_VALUES:
        return True
    if v in _ON_VALUES:  # open/opened/up
        return False
    return None


def binary_is_on(id_entry: dict) -> bool | None:
    """binary_sensor: on = active (motion detected / contact open)."""
    v = _semantic(id_entry)
    return v in _ON_VALUES if v is not None else None


def sensor_value(id_entry: dict):
    """sensor: pass the raw value through (usually a number)."""
    return id_entry.get("value")


# ---- actuation (HA service -> a raw write on the ID) ----

# HA-service intent -> the raw value to write. There is no abstract capability-command endpoint
# on /api/v2 and no per-capability `commands[]` list to consult any more -- POST
# /devices/{serial}/commands is gone and nothing replaced it -- so this is a fixed convention
# rather than a lookup against something the server advertises. See the high/low convention note
# above; the same caveat applies here in the write direction.
_INTENT_VALUE = {
    "on": "high", "off": "low",
    "open": "high", "close": "low",
    "unlock": "high", "lock": "low",
}


def resolve_write_value(id_entry: dict, intent: str) -> str | None:
    """The raw value to write for an HA action intent, or None if this ID is not a capability
    this integration supports (or actuation makes no sense here, e.g. a sensor).

    Momentary/delayed outputs ignore the value actually sent and fire their configured pulse
    regardless of it, so this is safe to call for those too -- 'open' and 'close' both just
    trigger the same relay pulse on that ID type, which matches how a real single-button garage
    remote behaves.
    """
    if not is_supported(id_entry):
        return None
    return _INTENT_VALUE.get(intent)
