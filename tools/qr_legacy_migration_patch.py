from pathlib import Path

path = Path("custom_components/localtuya/qr_onboarding.py")
text = path.read_text()
old = '''    def _persist_qr_auth(self, auth: dict[str, Any]) -> None:
        """Persist a refreshed sharing token after an explicit sync action."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        new_data[CONF_QR_AUTH] = copy.deepcopy(auth)
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
'''
new = '''    def _persist_qr_auth(self, auth: dict[str, Any]) -> None:
        """Persist QR authorization and migrate the entry to LAN-only runtime."""
        new_data = copy.deepcopy(dict(self.config_entry.data))
        new_data[CONF_QR_AUTH] = copy.deepcopy(auth)

        # Choosing the QR account link is an explicit migration away from the
        # legacy Tuya Developer Platform. Keep all configured LAN devices, but
        # remove credentials that could otherwise keep the old cloud runtime
        # active. The sharing authorization is used only on explicit provisioning
        # actions such as device sync/add.
        new_data[CONF_NO_CLOUD] = True
        new_data[CONF_CLIENT_ID] = ""
        new_data[CONF_CLIENT_SECRET] = ""
        new_data[CONF_USER_ID] = ""

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )
'''
if old not in text:
    raise SystemExit("persist QR auth anchor not found")
path.write_text(text.replace(old, new, 1))
