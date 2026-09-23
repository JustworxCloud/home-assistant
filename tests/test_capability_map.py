"""Unit tests for the capability -> Home Assistant mapping. Pure stdlib; no HA runtime needed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "justworx"))
import capability_map as cm  # noqa: E402


def id_entry(type_, value=None, names=None, secure=False, state_keywords=None):
    """An `ids[]` entry as /api/v2 returns it, carrying a `capability` sub-object."""
    return {
        "idNumber": 1,
        "type": "digitalOutput",
        "value": value,
        "stateKeywords": state_keywords,
        "capability": {"type": type_, "names": names or [type_], "secure": secure},
    }


class TestPlatformMapping(unittest.TestCase):
    def test_every_supported_type_maps_to_a_platform(self):
        for t in cm.SUPPORTED:
            self.assertIn(t, cm.PLATFORM, f"{t} has no platform")
            self.assertIsNotNone(cm.platform_for(t))

    def test_specific_mappings_match_the_taxonomy(self):
        self.assertEqual(cm.platform_for("Switch"), "switch")
        self.assertEqual(cm.platform_for("Light"), "light")
        self.assertEqual(cm.platform_for("Lock"), "lock")
        self.assertEqual(cm.platform_for("GarageDoor"), "cover")
        self.assertEqual(cm.device_class_for("GarageDoor"), "garage")
        self.assertEqual(cm.platform_for("ContactSensor"), "binary_sensor")
        self.assertEqual(cm.device_class_for("MotionSensor"), "motion")
        self.assertEqual(cm.platform_for("TemperatureSensor"), "sensor")
        self.assertEqual(cm.device_class_for("TemperatureSensor"), "temperature")
        self.assertEqual(cm.platform_for("AnalogGauge"), "sensor")
        self.assertIsNone(cm.device_class_for("AnalogGauge"))

    def test_platforms_list_is_derived(self):
        for p in ["switch", "light", "lock", "cover", "binary_sensor", "sensor"]:
            self.assertIn(p, cm.PLATFORMS)


class TestStateInterpretation(unittest.TestCase):
    """Semantic words (on/off/locked/closed/...) are read first from this specific device's
    stateKeywords when present, and otherwise fall back to the raw high/low convention."""

    def test_switch_from_semantic_value(self):
        self.assertTrue(cm.switch_is_on(id_entry("Switch", "on")))
        self.assertFalse(cm.switch_is_on(id_entry("Switch", "off")))

    def test_switch_from_default_high_low_convention(self):
        self.assertTrue(cm.switch_is_on(id_entry("Switch", "high")))
        self.assertFalse(cm.switch_is_on(id_entry("Switch", "low")))

    def test_lock(self):
        self.assertTrue(cm.lock_is_locked(id_entry("Lock", "locked")))
        self.assertFalse(cm.lock_is_locked(id_entry("Lock", "unlocked")))
        self.assertTrue(cm.lock_is_locked(id_entry("Lock", "low")))  # default convention
        self.assertFalse(cm.lock_is_locked(id_entry("Lock", "high")))

    def test_cover_closed_open_unknown(self):
        self.assertTrue(cm.cover_is_closed(id_entry("GarageDoor", "closed")))
        self.assertFalse(cm.cover_is_closed(id_entry("GarageDoor", "open")))
        self.assertIsNone(cm.cover_is_closed(id_entry("GarageDoor", "moving")))

    def test_binary_sensor(self):
        self.assertTrue(cm.binary_is_on(id_entry("MotionSensor", "motion")))
        self.assertFalse(cm.binary_is_on(id_entry("MotionSensor", "clear")))

    def test_sensor_value_passthrough(self):
        self.assertEqual(cm.sensor_value(id_entry("TemperatureSensor", 21.4)), 21.4)

    def test_stateKeywords_overrides_the_default_convention_by_raw_value_key(self):
        # This device's author wired it active-low: raw "high" means Closed.
        entry = id_entry("GarageDoor", "high", state_keywords={"high": "Closed", "low": "Open"})
        self.assertTrue(cm.cover_is_closed(entry))

    def test_stateKeywords_overrides_the_default_convention_by_numeric_key(self):
        # Some stateKeywords are authored with the numeric-level spelling instead.
        entry = id_entry("Lock", "high", state_keywords={"0": "Unlocked", "1": "Locked"})
        self.assertTrue(cm.lock_is_locked(entry))

    def test_no_value_is_unknown(self):
        self.assertIsNone(cm.switch_is_on(id_entry("Switch", None)))


class TestActuation(unittest.TestCase):
    def test_resolves_intents_to_raw_values(self):
        self.assertEqual(cm.resolve_write_value(id_entry("GarageDoor"), "open"), "high")
        self.assertEqual(cm.resolve_write_value(id_entry("GarageDoor"), "close"), "low")
        self.assertEqual(cm.resolve_write_value(id_entry("Switch"), "on"), "high")
        self.assertEqual(cm.resolve_write_value(id_entry("Switch"), "off"), "low")
        self.assertEqual(cm.resolve_write_value(id_entry("Lock"), "unlock"), "high")
        self.assertEqual(cm.resolve_write_value(id_entry("Lock"), "lock"), "low")

    def test_returns_none_for_an_unsupported_capability(self):
        self.assertIsNone(cm.resolve_write_value(id_entry("Thermostat"), "on"))  # deferred

    def test_returns_none_for_an_id_with_no_capability(self):
        bare = {"idNumber": 1, "type": "digitalOutput", "value": "low"}
        self.assertIsNone(cm.resolve_write_value(bare, "on"))


class TestHelpers(unittest.TestCase):
    def test_display_name_and_supported(self):
        self.assertEqual(cm.display_name(id_entry("Switch", names=["Pump", "Water"])), "Pump")
        self.assertTrue(cm.is_supported(id_entry("GarageDoor")))
        self.assertFalse(cm.is_supported(id_entry("Thermostat")))  # deferred
        self.assertFalse(cm.is_supported({"idNumber": 1, "type": "digitalOutput"}))  # no capability


if __name__ == "__main__":
    unittest.main()
