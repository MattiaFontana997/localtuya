from pathlib import Path

climate_path = Path("custom_components/localtuya/climate.py")
text = climate_path.read_text(encoding="utf-8")

start_marker = '''    @property\n    def min_temp(self):\n        """Return the active mapped minimum target temperature."""\n'''
end_marker = '''    @property\n    def target_temperature_step(self):\n'''

start = text.find(start_marker)
if start < 0:
    raise SystemExit("early mapped min_temp block not found")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("target_temperature_step anchor not found")

text = text[:start] + text[end:]
if text.count("    def min_temp(self):") != 1:
    raise SystemExit("expected exactly one min_temp definition after cleanup")
if text.count("    def max_temp(self):") != 1:
    raise SystemExit("expected exactly one max_temp definition after cleanup")
climate_path.write_text(text, encoding="utf-8")


test_path = Path("tests/test_climate_advanced_metadata.py")
test = test_path.read_text(encoding="utf-8")
if "import inspect\n" not in test:
    test = test.replace("import unittest\n", "import inspect\nimport unittest\n", 1)

method = '''\n    def test_temperature_limit_properties_are_defined_once(self):\n        source = inspect.getsource(LocaltuyaClimate)\n        self.assertEqual(source.count("def min_temp(self):"), 1)\n        self.assertEqual(source.count("def max_temp(self):"), 1)\n'''
anchor = '''\n    def test_static_fallback_remains_unchanged(self):\n'''
if method.strip() not in test:
    idx = test.find(anchor)
    if idx < 0:
        raise SystemExit("test insertion anchor not found")
    test = test[:idx] + method + test[idx:]

test_path.write_text(test, encoding="utf-8")

common_path = Path("custom_components/localtuya/common.py")
common = common_path.read_text(encoding="utf-8")
old = '        for name, dp_id in self._mapped_extra_state_attribute_dps.items():\n'
new = '        for name, dp_id in getattr(self, "_mapped_extra_state_attribute_dps", {}).items():\n'
if old in common:
    common = common.replace(old, new, 1)
elif new not in common:
    raise SystemExit("mapped-extra attribute loop anchor not found")
common_path.write_text(common, encoding="utf-8")

print("Batch N climate range runtime cleanup applied")
