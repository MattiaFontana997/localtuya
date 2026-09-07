from pathlib import Path

path = Path("custom_components/localtuya/light.py")
text = path.read_text()
old_read = '''            return color_util.value_to_brightness(
                (self._lower_brightness, self._upper_brightness), numeric
            )
'''
new_read = '''            return round(
                map_range(
                    numeric,
                    self._lower_brightness,
                    self._upper_brightness,
                    1,
                    255,
                )
            )
'''
assert text.count(old_read) == 1
text = text.replace(old_read, new_read, 1)

old_write = '''            raw_value = round(
                color_util.brightness_to_value(
                    (self._lower_brightness, self._upper_brightness), target
                )
            )
'''
new_write = '''            raw_value = round(
                map_range(
                    target,
                    1,
                    255,
                    self._lower_brightness,
                    self._upper_brightness,
                )
            )
'''
assert text.count(old_write) == 1
text = text.replace(old_write, new_write, 1)
path.write_text(text)
