from pathlib import Path
import json

path = Path("custom_components/localtuya/config_flow.py")
text = path.read_text()

old = '''CONTRIBUTION_JSON = "contribution_json"\n\nCUSTOM_DEVICE'''
new = '''CONTRIBUTION_JSON = "contribution_json"\nLINK_QR_ACCOUNT = "link_qr_account"\n\nCUSTOM_DEVICE'''
if old not in text:
    raise SystemExit("constant anchor not found")
text = text.replace(old, new, 1)

old = '''    CONF_SETUP_CLOUD:\n        "action_setup_cloud",\n}'''
new = '''    CONF_SETUP_CLOUD:\n        "action_setup_cloud",\n    LINK_QR_ACCOUNT:\n        "action_link_qr_account",\n}'''
if old not in text:
    raise SystemExit("translation-key anchor not found")
text = text.replace(old, new, 1)

old = '''    CONF_SETUP_CLOUD:\n        "Reconfigure Cloud API account",\n}'''
new = '''    CONF_SETUP_CLOUD:\n        "Reconfigure Cloud API account",\n    LINK_QR_ACCOUNT:\n        "Link Smart Life / Tuya account by QR",\n}'''
if old not in text:
    raise SystemExit("fallback anchor not found")
text = text.replace(old, new, 1)

old = '''            if user_input.get(CONF_ACTION) == CONF_ADD_DEVICE:\n                return await self.async_step_add_device()\n            if user_input.get(CONF_ACTION) == CONF_EDIT_DEVICE:'''
new = '''            if user_input.get(CONF_ACTION) == CONF_ADD_DEVICE:\n                return await self.async_step_add_device()\n            if user_input.get(CONF_ACTION) == LINK_QR_ACCOUNT:\n                return await self.async_step_qr_relink()\n            if user_input.get(CONF_ACTION) == CONF_EDIT_DEVICE:'''
if old not in text:
    raise SystemExit("dispatch anchor not found")
text = text.replace(old, new, 1)

old = '''        if not has_legacy_cloud:\n            action_labels.pop(\n                CONF_SETUP_CLOUD,\n                None,\n            )\n\n        return self.async_show_form('''
new = '''        if not has_legacy_cloud:\n            action_labels.pop(\n                CONF_SETUP_CLOUD,\n                None,\n            )\n\n        # Existing LocalTuya installations upgraded from 6.5.x must be able\n        # to adopt the new QR account link without deleting/recreating their\n        # config entry. Once linked, account management lives under Add device.\n        if self.config_entry.data.get(CONF_QR_AUTH):\n            action_labels.pop(LINK_QR_ACCOUNT, None)\n\n        return self.async_show_form('''
if old not in text:
    raise SystemExit("visibility anchor not found")
text = text.replace(old, new, 1)
path.write_text(text)

labels = {
    "en": "Link Smart Life / Tuya account by QR",
    "it": "Collega account Smart Life / Tuya tramite QR",
    "de": "Smart Life / Tuya-Konto per QR verknüpfen",
    "pt-BR": "Vincular conta Smart Life / Tuya por QR",
    "zh-Hans": "通过二维码关联 Smart Life / Tuya 账户",
}
for lang, label in labels.items():
    p = Path(f"custom_components/localtuya/translations/{lang}.json")
    data = json.loads(p.read_text())
    data.setdefault("common", {})["action_link_qr_account"] = label
    p.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n")
