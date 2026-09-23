"""End-to-end: run the real capability_map against a live Justworx API.

Verifies the adapter's mapping produces the right HA entities from the actual /api/v2 contract,
and that a raw ID write actuates + reflects in state. Requires a real account with at least one
device carrying an authored `capability` on some of its IDs. Set:
    JWX_TEST_BASE=https://api.justworx.com/api/v2
    JWX_TEST_KEY=<jwx_live_... key>
Skips cleanly if JWX_TEST_BASE is unset.
"""
import json
import os
import sys
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "justworx"))
import capability_map as cm  # noqa: E402

BASE = os.environ.get("JWX_TEST_BASE")
KEY = os.environ.get("JWX_TEST_KEY", "")


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


@unittest.skipUnless(BASE, "JWX_TEST_BASE not set — no live account to test against")
class TestAgainstLiveApi(unittest.TestCase):
    def _all_id_entries(self):
        entries = []
        for summary in _req("GET", "/devices")["items"]:
            device = _req("GET", f"/devices/{summary['serial']}")
            for entry in device.get("ids", []):
                if entry.get("capability"):
                    entries.append((summary["serial"], entry))
        return entries

    def test_capabilities_map_to_expected_entities(self):
        entries = self._all_id_entries()
        by_type = {e["capability"]["type"]: e for _, e in entries}
        # This account's test fleet is expected to carry at least these five, authored in Studio.
        for t in ["GarageDoor", "Light", "Lock", "TemperatureSensor", "Switch"]:
            self.assertIn(t, by_type, f"no ID with capability.type={t} found on this account")

        self.assertEqual(cm.platform_for("GarageDoor"), "cover")
        self.assertEqual(cm.device_class_for("GarageDoor"), "garage")
        self.assertEqual(cm.platform_for("Switch"), "switch")
        self.assertEqual(cm.platform_for("TemperatureSensor"), "sensor")

        # Every capability we support must resolve to a platform.
        for _, entry in entries:
            if cm.is_supported(entry):
                self.assertIsNotNone(cm.platform_for(entry["capability"]["type"]))

    def test_actuating_a_garage_door_id_reflects_in_state(self):
        gate_serial = gate_entry = None
        for serial, entry in self._all_id_entries():
            if entry["capability"]["type"] == "GarageDoor":
                gate_serial, gate_entry = serial, entry
                break
        self.assertIsNotNone(gate_entry, "no GarageDoor capability to actuate")

        value = cm.resolve_write_value(gate_entry, "open")
        res = _req("PUT", f"/devices/{gate_serial}/ids/{gate_entry['idNumber']}/value",
                   {"value": value, "timeoutMs": 5000})
        self.assertEqual(res["status"], "confirmed")

        # Re-read: the cover should now report not-closed.
        device = _req("GET", f"/devices/{gate_serial}")
        entry = next(e for e in device["ids"] if e["idNumber"] == gate_entry["idNumber"])
        self.assertIs(cm.cover_is_closed(entry), False)


if __name__ == "__main__":
    unittest.main()
