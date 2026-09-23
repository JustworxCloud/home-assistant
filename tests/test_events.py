"""Unit tests for applying one real-time EventItem to the device snapshot. Stdlib only; no HA runtime.

Replaces test_sse.py -- the SSE stream (GET /events/stream) was withdrawn 2026-08-30. The
WebSocket/long-poll pair that replaced it delivers the same EventItem shape as GET
/devices/{serial}/log: {cursor, ts, type, event, serial, message, actor, channel, data}.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "justworx"))
import events  # noqa: E402


class TestApplyEvent(unittest.TestCase):
    def _devices(self):
        return {
            "ABCD1234": {
                "serial": "ABCD1234", "online": True,
                "ids": [{"idNumber": 10, "type": "digitalOutput", "value": "low",
                          "capability": {"type": "Switch", "names": ["Pump"], "secure": False}}],
            },
        }

    def test_value_reported_updates_the_matching_id(self):
        devices = self._devices()
        serial = events.apply_event(devices, {
            "serial": "ABCD1234", "event": "value_reported", "ts": "2026-09-22T00:00:00.000Z",
            "data": {"id": 10, "value": "high"},
        })
        self.assertEqual(serial, "ABCD1234")
        entry = devices["ABCD1234"]["ids"][0]
        self.assertEqual(entry["value"], "high")
        self.assertEqual(entry["at"], "2026-09-22T00:00:00.000Z")

    def test_value_reported_for_an_unknown_id_on_a_known_device_is_a_no_op(self):
        devices = self._devices()
        serial = events.apply_event(devices, {
            "serial": "ABCD1234", "event": "value_reported", "data": {"id": 99, "value": "high"},
        })
        self.assertEqual(serial, "ABCD1234")  # device known; just no matching ID to update
        self.assertEqual(devices["ABCD1234"]["ids"][0]["value"], "low")  # unchanged

    def test_device_online_offline_sets_availability(self):
        devices = self._devices()
        events.apply_event(devices, {"serial": "ABCD1234", "event": "device_offline"})
        self.assertFalse(devices["ABCD1234"]["online"])
        events.apply_event(devices, {"serial": "ABCD1234", "event": "device_online"})
        self.assertTrue(devices["ABCD1234"]["online"])

    def test_unknown_device_is_ignored(self):
        devices = self._devices()
        result = events.apply_event(devices, {
            "serial": "ZZZZ9999", "event": "value_reported", "data": {"id": 10, "value": "high"},
        })
        self.assertIsNone(result)

    def test_an_event_type_this_integration_does_not_act_on_is_ignored_not_errored(self):
        devices = self._devices()
        result = events.apply_event(devices, {"serial": "ABCD1234", "event": "rule_fired", "data": {}})
        self.assertIsNone(result)

    def test_loads_is_tolerant(self):
        self.assertEqual(events.loads(""), {})
        self.assertEqual(events.loads("not json"), {})
        self.assertEqual(events.loads('{"x":1}'), {"x": 1})


if __name__ == "__main__":
    unittest.main()
