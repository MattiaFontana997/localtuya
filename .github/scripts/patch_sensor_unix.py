from pathlib import Path

const = Path("custom_components/localtuya/const.py")
text = const.read_text()
old = '# sensor\nCONF_SCALING = "scaling"\n'
new = '# sensor\nCONF_SCALING = "scaling"\nCONF_SENSOR_UNIX_TIMESTAMP = "sensor_unix_timestamp"\n'
if text.count(old) != 1:
    raise SystemExit(f"const sensor anchor count={text.count(old)}")
const.write_text(text.replace(old, new, 1))

sensor = Path("custom_components/localtuya/sensor.py")
text = sensor.read_text()
old = "import logging\nfrom functools import partial\n"
new = "import logging\nfrom datetime import UTC, datetime\nfrom functools import partial\n"
if text.count(old) != 1:
    raise SystemExit(f"sensor import anchor count={text.count(old)}")
text = text.replace(old, new, 1)
old = "from .const import CONF_SCALING\n"
new = "from .const import CONF_SCALING, CONF_SENSOR_UNIX_TIMESTAMP\n"
if text.count(old) != 1:
    raise SystemExit(f"sensor const import count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''        vol.Optional(CONF_SCALING): vol.All(
            vol.Coerce(float),
            vol.Range(min=-1000000.0, max=1000000.0),
        ),
'''
new = old + '        vol.Optional(CONF_SENSOR_UNIX_TIMESTAMP, default=False): bool,\n'
if text.count(old) != 1:
    raise SystemExit(f"sensor flow schema anchor count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''        if self._value_mapping is not None:
            self._state, self._mapping_icon = evaluate_sensor_value_mapping(state, self._value_mapping)
            return

        scale_factor = self._config.get(CONF_SCALING)
'''
new = '''        if self._value_mapping is not None:
            self._state, self._mapping_icon = evaluate_sensor_value_mapping(state, self._value_mapping)
            return

        if self._config.get(CONF_SENSOR_UNIX_TIMESTAMP):
            if isinstance(state, bool) or not isinstance(state, (int, float)):
                self._state = None
                return
            try:
                self._state = datetime.fromtimestamp(state, UTC)
            except (OverflowError, OSError, ValueError):
                self._state = None
            return

        scale_factor = self._config.get(CONF_SCALING)
'''
if text.count(old) != 1:
    raise SystemExit(f"sensor status anchor count={text.count(old)}")
sensor.write_text(text.replace(old, new, 1))

catalog = Path("custom_components/localtuya/device_catalog.py")
text = catalog.read_text()
old = '''    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,
    PLATFORMS,
)'''
new = '''    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,
    CONF_SENSOR_UNIX_TIMESTAMP,
    PLATFORMS,
)'''
if text.count(old) != 1:
    raise SystemExit(f"catalog const import anchor count={text.count(old)}")
text = text.replace(old, new, 1)
anchor = '''    if "sensor_value_mapping" in config:
        from .sensor_mapping import validate_sensor_value_mapping

        mapping = validate_sensor_value_mapping(config["sensor_value_mapping"])
        if platform != "sensor" or mapping is None or any(
            key in config for key in ("scaling", CONF_ADVANCED_MAPPING, CONF_ADVANCED_MAPPING_BY_DP)
        ):
            return None
        config["sensor_value_mapping"] = mapping
'''
addition = anchor + '''    unix_timestamp = config.get(CONF_SENSOR_UNIX_TIMESTAMP)
    if unix_timestamp is not None:
        if (
            unix_timestamp is not True
            or platform != "sensor"
            or config.get("device_class") != "timestamp"
            or any(
                key in config
                for key in (
                    "scaling",
                    "sensor_value_mapping",
                    "unit_of_measurement",
                    "state_class",
                    CONF_ADVANCED_MAPPING,
                    CONF_ADVANCED_MAPPING_BY_DP,
                )
            )
        ):
            return None
'''
if text.count(anchor) != 1:
    raise SystemExit(f"catalog sensor validation anchor count={text.count(anchor)}")
catalog.write_text(text.replace(anchor, addition, 1))

Path("tests/test_sensor_unix_timestamp.py").write_text('''"""Explicit Unix timestamp sensor conversion regressions."""\n\nimport unittest\nfrom datetime import UTC, datetime\n\nfrom custom_components.localtuya.device_catalog import _validate_entity\nfrom custom_components.localtuya.sensor import LocaltuyaSensor\n\n\nclass SensorUnixTimestampTests(unittest.TestCase):\n    def make_sensor(self, raw, *, enabled=True):\n        sensor = object.__new__(LocaltuyaSensor)\n        sensor._dp_id = 1\n        sensor._config = {"sensor_unix_timestamp": True} if enabled else {}\n        sensor._value_mapping = None\n        sensor._mapping_icon = None\n        sensor.dps = lambda dp: raw\n        return sensor\n\n    def test_explicit_unix_seconds_become_utc_datetime(self):\n        raw = 1_700_000_000\n        sensor = self.make_sensor(raw)\n        sensor.status_updated()\n        self.assertEqual(sensor.native_value, datetime.fromtimestamp(raw, UTC))\n        self.assertIs(sensor.native_value.tzinfo, UTC)\n\n    def test_unix_flag_rejects_non_numeric_and_boolean_values(self):\n        for raw in (True, "1700000000", None):\n            with self.subTest(raw=raw):\n                sensor = self.make_sensor(raw)\n                sensor.status_updated()\n                self.assertIsNone(sensor.native_value)\n\n    def test_numeric_sensor_without_flag_stays_numeric(self):\n        sensor = self.make_sensor(1_700_000_000, enabled=False)\n        sensor.status_updated()\n        self.assertEqual(sensor.native_value, 1_700_000_000)\n\n    def test_catalog_accepts_only_explicit_timestamp_sensor_shape(self):\n        good = {\n            "platform": "sensor",\n            "config": {\n                "platform": "sensor",\n                "id": 1,\n                "device_class": "timestamp",\n                "sensor_unix_timestamp": True,\n            },\n        }\n        self.assertIsNotNone(_validate_entity(good))\n        bad_configs = [\n            {**good["config"], "device_class": "temperature"},\n            {**good["config"], "sensor_unix_timestamp": False},\n            {**good["config"], "scaling": 0.1},\n            {**good["config"], "sensor_value_mapping": {"raw_type": "integer", "rules": [{"scale": 10}]}},\n        ]\n        for config in bad_configs:\n            with self.subTest(config=config):\n                self.assertIsNone(_validate_entity({"platform": "sensor", "config": config}))\n        self.assertIsNone(\n            _validate_entity(\n                {\n                    "platform": "number",\n                    "config": {\n                        "platform": "number",\n                        "id": 1,\n                        "sensor_unix_timestamp": True,\n                    },\n                }\n            )\n        )\n\n\nif __name__ == "__main__":\n    unittest.main()\n''')
