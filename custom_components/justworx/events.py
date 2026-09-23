"""Pure logic for applying one real-time event item to the coordinator's device map.

No Home Assistant imports, so it unit-tests with plain Python. The runtime WebSocket/long-poll
glue lives in stream.py; this module only merges one EventItem into the device snapshot the
entities read.

An EventItem (identical shape whether it arrived over the WebSocket or a long-poll GET /events,
and identical to one row of GET /devices/{serial}/log): `{cursor, ts, type, event, serial,
message, actor, channel, data}`. This is NOT the old SSE shape (`{event, serialNumber,
controlId, value}`) -- there is no `controlId` any more, and a value update names the ID by
`data.id`, not by a capability's controlId.
"""

from __future__ import annotations

import json


def loads(data_str: str) -> dict:
    """Tolerant JSON parse of an event payload."""
    if not data_str:
        return {}
    try:
        return json.loads(data_str)
    except ValueError:
        return {}


def apply_event(devices: dict, item: dict) -> str | None:
    """Merge one EventItem into `devices` (serial -> device dict, as returned by GET
    /devices/{serial}). Returns the affected serial, or None if the event named a device this
    snapshot does not know about yet (the next full poll will pick it up).

    Merges (never wholesale-replaces) so real-time updates layer on top of the full device info
    from the initial poll (name, serial, ids[], rules, ...).
    """
    serial = item.get("serial")
    if not serial:
        return None
    dev = devices.get(serial)
    if dev is None:
        return None

    event = item.get("event")
    data = item.get("data") or {}

    if event in ("device_online", "device_offline"):
        dev["online"] = event == "device_online"
        return serial

    if event == "value_reported":
        id_number = data.get("id")
        if id_number is None:
            return None
        for entry in dev.get("ids", []):
            if entry.get("idNumber") == id_number:
                if "value" in data:
                    entry["value"] = data["value"]
                if item.get("ts"):
                    entry["at"] = item["ts"]
                break
        return serial

    # Every other event type (rule_fired, id_configured, telemetry_configured, ...) does not
    # change anything an entity here reads. Ignored rather than erroring -- a caller does not get
    # to assume the event vocabulary never grows.
    return None
