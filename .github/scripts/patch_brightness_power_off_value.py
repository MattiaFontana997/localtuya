from pathlib import Path


def replace_method(text: str, name: str, replacement: str) -> str:
    start = text.index(f"    def {name}(")
    next_def = text.index("\n    def ", start + 5)
    return text[:start] + replacement.rstrip() + "\n" + text[next_def:]


# const.py
path = Path("custom_components/localtuya/const.py")
text = path.read_text()
anchor = 'CONF_BRIGHTNESS_AS_POWER = "brightness_as_power"\n'
assert text.count(anchor) == 1
text = text.replace(
    anchor,
    anchor + 'CONF_BRIGHTNESS_POWER_OFF_VALUE = "brightness_power_off_value"\n',
    1,
)
path.write_text(text)


# light.py
path = Path("custom_components/localtuya/light.py")
text = path.read_text()
anchor = "    CONF_BRIGHTNESS_AS_POWER,\n"
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + "    CONF_BRIGHTNESS_POWER_OFF_VALUE,\n", 1)

anchor = "        vol.Optional(CONF_BRIGHTNESS_AS_POWER, default=False): bool,\n"
assert text.count(anchor) == 1
text = text.replace(
    anchor,
    anchor + "        vol.Optional(CONF_BRIGHTNESS_POWER_OFF_VALUE): _light_power_scalar,\n",
    1,
)

anchor = """        self._brightness_as_power = bool(
            self._config.get(CONF_BRIGHTNESS_AS_POWER, False)
        )
"""
assert text.count(anchor) == 1
text = text.replace(
    anchor,
    anchor
    + """        self._brightness_power_off_configured = (
            CONF_BRIGHTNESS_POWER_OFF_VALUE in self._config
        )
        self._brightness_power_off_value = self._config.get(
            CONF_BRIGHTNESS_POWER_OFF_VALUE
        )
""",
    1,
)

text = replace_method(
    text,
    "_raw_brightness_to_ha",
    '''    def _raw_brightness_to_ha(self, value) -> int | None:
        """Convert a Tuya brightness value to HA's 0..255 range."""
        if value is None:
            config = getattr(self, "_config", {})
            if isinstance(config, dict):
                value = config.get(CONF_BRIGHTNESS_NULL_VALUE)
            if value is None:
                return None

        mapped = getattr(self, "_brightness_values", [])
        if mapped:
            for brightness, raw_value in mapped:
                if _same_raw_value(value, raw_value):
                    return brightness
            return None

        if (
            getattr(self, "_brightness_as_power", False)
            and getattr(self, "_brightness_power_off_configured", False)
        ):
            if _same_raw_value(
                value, getattr(self, "_brightness_power_off_value", None)
            ):
                return 0
            if isinstance(value, bool):
                return None
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return None
            if not self._lower_brightness <= numeric <= self._upper_brightness:
                return None
            return color_util.value_to_brightness(
                (self._lower_brightness, self._upper_brightness), numeric
            )

        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return map_range(
            numeric,
            self._lower_brightness,
            self._upper_brightness,
            0,
            255,
        )''',
)

text = replace_method(
    text,
    "_ha_brightness_to_raw",
    '''    def _ha_brightness_to_raw(self, value):
        """Convert HA brightness to the exact Tuya brightness representation."""
        mapped = getattr(self, "_brightness_values", [])
        if mapped:
            target = min(max(int(value), 0), 255)
            best_raw = mapped[0][1]
            best_distance = abs(mapped[0][0] - target)
            for brightness, raw_value in mapped[1:]:
                distance = abs(brightness - target)
                if distance < best_distance:
                    best_raw = raw_value
                    best_distance = distance
            return best_raw

        if (
            getattr(self, "_brightness_as_power", False)
            and getattr(self, "_brightness_power_off_configured", False)
        ):
            target = min(max(int(value), 0), 255)
            if target == 0:
                return getattr(self, "_brightness_power_off_value", 0)
            raw_value = round(
                color_util.brightness_to_value(
                    (self._lower_brightness, self._upper_brightness), target
                )
            )
        else:
            raw_value = map_range(
                int(value),
                0,
                255,
                self._lower_brightness,
                self._upper_brightness,
            )

        brightness_step = getattr(self, "_brightness_step", 1)
        if brightness_step != 1:
            raw_value = brightness_step * round(float(raw_value) / brightness_step)
        return min(max(raw_value, self._lower_brightness), self._upper_brightness)''',
)
path.write_text(text)


# device_catalog.py
path = Path("custom_components/localtuya/device_catalog.py")
text = path.read_text()
anchor = "from .const import (\n"
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + "    CONF_BRIGHTNESS_POWER_OFF_VALUE,\n", 1)

anchor = '    if "sensor_value_mapping" in config:\n'
assert text.count(anchor) == 1
validation = '''    if CONF_BRIGHTNESS_POWER_OFF_VALUE in config:
        off_value = config[CONF_BRIGHTNESS_POWER_OFF_VALUE]
        lower = config.get("brightness_lower")
        upper = config.get("brightness_upper")
        if (
            platform != "light"
            or config.get("brightness_as_power") is not True
            or config.get("id") != config.get("brightness")
            or "brightness_values" in config
            or isinstance(off_value, bool)
            or not isinstance(off_value, int)
            or isinstance(lower, bool)
            or isinstance(upper, bool)
            or not isinstance(lower, int)
            or not isinstance(upper, int)
            or lower < 0
            or upper <= lower
            or lower <= off_value <= upper
        ):
            return None

'''
text = text.replace(anchor, validation + anchor, 1)
path.write_text(text)


# tests/test_light_residual_runtime.py
path = Path("tests/test_light_residual_runtime.py")
text = path.read_text()
anchor = "        light._brightness_step = 1\n"
assert text.count(anchor) == 1
text = text.replace(
    anchor,
    anchor
    + '''        light._brightness_as_power = bool(light._config.get("brightness_as_power", False))
        light._brightness_power_off_configured = "brightness_power_off_value" in light._config
        light._brightness_power_off_value = light._config.get("brightness_power_off_value")
''',
    1,
)
marker = "    def test_discrete_color_temperature_mapping(self):\n"
assert text.count(marker) == 1
case = '''    def test_brightness_power_off_value_keeps_nonzero_range_on(self):
        light = self._light({
            "brightness_as_power": True,
            "brightness_power_off_value": 0,
        })
        light._lower_brightness = 1
        light._upper_brightness = 3
        self.assertEqual(light._raw_brightness_to_ha(0), 0)
        self.assertEqual(light._raw_brightness_to_ha(1), 1)
        self.assertEqual(light._raw_brightness_to_ha(2), 128)
        self.assertEqual(light._raw_brightness_to_ha(3), 255)
        self.assertIsNone(light._raw_brightness_to_ha(4))
        self.assertEqual(light._ha_brightness_to_raw(0), 0)
        self.assertEqual(light._ha_brightness_to_raw(1), 1)
        self.assertEqual(light._ha_brightness_to_raw(128), 2)
        self.assertEqual(light._ha_brightness_to_raw(255), 3)

'''
text = text.replace(marker, case + marker, 1)
path.write_text(text)


# tests/test_device_catalog.py
path = Path("tests/test_device_catalog.py")
text = path.read_text()
old = '''from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)
'''
new = '''from custom_components.localtuya.device_catalog import (
    _validate_entity,
    match_catalog_mapping,
    validate_catalog,
)
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
text += '''

class BrightnessPowerOffCatalogTests(unittest.TestCase):
    def test_exact_out_of_range_brightness_off_value_is_accepted(self):
        entity = {"platform": "light", "config": {
            "platform": "light", "id": 102, "brightness": 102,
            "brightness_as_power": True, "brightness_lower": 1,
            "brightness_upper": 3, "brightness_power_off_value": 0,
        }}
        self.assertIsNotNone(_validate_entity(entity))

    def test_in_range_brightness_off_value_is_rejected(self):
        entity = {"platform": "light", "config": {
            "platform": "light", "id": 102, "brightness": 102,
            "brightness_as_power": True, "brightness_lower": 1,
            "brightness_upper": 3, "brightness_power_off_value": 1,
        }}
        self.assertIsNone(_validate_entity(entity))
'''
path.write_text(text)
