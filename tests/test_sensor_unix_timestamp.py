"""Explicit Unix timestamp sensor conversion regressions."""

import unittest
from datetime import UTC, datetime

from custom_components.localtuya.device_catalog import _validate_entity
from custom_components.localtuya.sensor import LocaltuyaSensor


class SensorUnixTimestampTests(unittest.TestCase):
    def make_sensor(self, raw, *, enabled=True):
        sensor = object.__new__(LocaltuyaSensor)
        sensor._dp_id = 1
        sensor._config = {"sensor_unix_timestamp": True} if enabled else {}
        sensor._value_mapping = None
        sensor._mapping_icon = None
        sensor.dps = lambda dp: raw
        return sensor

    def test_explicit_unix_seconds_become_utc_datetime(self):
        raw = 1_700_000_000
        sensor = self.make_sensor(raw)
        sensor.status_updated()
        self.assertEqual(sensor.native_value, datetime.fromtimestamp(raw, UTC))
        self.assertIs(sensor.native_value.tzinfo, UTC)

    def test_unix_flag_rejects_non_numeric_and_boolean_values(self):
        for raw in (True, "1700000000", None):
            with self.subTest(raw=raw):
                sensor = self.make_sensor(raw)
                sensor.status_updated()
                self.assertIsNone(sensor.native_value)

    def test_numeric_sensor_without_flag_stays_numeric(self):
        sensor = self.make_sensor(1_700_000_000, enabled=False)
        sensor.status_updated()
        self.assertEqual(sensor.native_value, 1_700_000_000)

    def test_catalog_accepts_only_explicit_timestamp_sensor_shape(self):
        good = {
            "platform": "sensor",
            "config": {
                "platform": "sensor",
                "id": 1,
                "device_class": "timestamp",
                "sensor_unix_timestamp": True,
            },
        }
        self.assertIsNotNone(_validate_entity(good))
        bad_configs = [
            {**good["config"], "device_class": "temperature"},
            {**good["config"], "sensor_unix_timestamp": False},
            {**good["config"], "scaling": 0.1},
            {**good["config"], "sensor_value_mapping": {"raw_type": "integer", "rules": [{"scale": 10}]}},
        ]
        for config in bad_configs:
            with self.subTest(config=config):
                self.assertIsNone(_validate_entity({"platform": "sensor", "config": config}))
        self.assertIsNone(
            _validate_entity(
                {
                    "platform": "number",
                    "config": {
                        "platform": "number",
                        "id": 1,
                        "sensor_unix_timestamp": True,
                    },
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
