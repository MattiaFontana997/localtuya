from pathlib import Path

p = Path('custom_components/localtuya/device_catalog.py')
s = p.read_text(encoding='utf-8')

# Accept optional compatibility evidence as a bounded, declarative mapping.
needle = '        confidence = mapping.get("confidence", "experimental")\n'
if needle not in s:
    raise SystemExit('catalog mapping confidence marker not found')
insert = '''        compatibility = mapping.get("compatibility")
        if compatibility is not None:
            if not isinstance(compatibility, dict):
                continue
            allowed_compatibility_keys = {
                "hardware_tested",
                "protocols",
                "transport",
                "home_assistant",
                "localtuya",
                "tested_at",
            }
            if set(compatibility) - allowed_compatibility_keys:
                continue
            if not isinstance(compatibility.get("hardware_tested", False), bool):
                continue
            protocols = compatibility.get("protocols", [])
            if isinstance(protocols, str):
                protocols = [protocols]
            if not isinstance(protocols, list) or len(protocols) > 5:
                continue
            valid_protocols = {"3.1", "3.2", "3.3", "3.4", "3.5", "unknown"}
            if any(str(protocol) not in valid_protocols for protocol in protocols):
                continue
            transport = compatibility.get("transport", "direct")
            if transport not in {"direct", "gateway_child"}:
                continue
            for text_key in ("home_assistant", "localtuya", "tested_at"):
                value = compatibility.get(text_key)
                if value is not None and (not isinstance(value, str) or len(value) > 64):
                    continue

'''
s = s.replace(needle, insert + needle, 1)

p.write_text(s, encoding='utf-8')
