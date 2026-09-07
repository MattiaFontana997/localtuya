from pathlib import Path

path = Path("custom_components/localtuya/light.py")
text = path.read_text()
old_read = '''            return round(
                map_range(
                    numeric,
                    self._lower_brightness,
                    self._upper_brightness,
                    1,
                    255,
                )
            )
'''
new_read = '''            return color_util.value_to_brightness(
                (self._lower_brightness, self._upper_brightness), numeric
            )
'''
assert text.count(old_read) == 1
text = text.replace(old_read, new_read, 1)

old_write = '''            raw_value = round(
                map_range(
                    target,
                    1,
                    255,
                    self._lower_brightness,
                    self._upper_brightness,
                )
            )
'''
new_write = '''            if target == 1 and self._lower_brightness != 0:
                raw_value = self._lower_brightness
            else:
                raw_value = round(
                    color_util.brightness_to_value(
                        (self._lower_brightness, self._upper_brightness), target
                    )
                )
'''
assert text.count(old_write) == 1
text = text.replace(old_write, new_write, 1)
path.write_text(text)

path = Path("tests/test_light_residual_runtime.py")
text = path.read_text()
old = '''        self.assertEqual(light._raw_brightness_to_ha(1), 1)
        self.assertEqual(light._raw_brightness_to_ha(2), 128)
        self.assertEqual(light._raw_brightness_to_ha(3), 255)
'''
new = '''        self.assertEqual(light._raw_brightness_to_ha(1), 85)
        self.assertEqual(light._raw_brightness_to_ha(2), 170)
        self.assertEqual(light._raw_brightness_to_ha(3), 255)
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
path.write_text(text)
