from pathlib import Path

path = Path("custom_components/localtuya/common.py")
text = path.read_text(encoding="utf-8")
method = text.index("    async def _make_connection(self):")
start = text.index("            self._interface = await pytuya.connect(", method)
end_marker = '                gateway_id=self._dev_config_entry.get("gateway_id"),\n            )\n'
end = text.index(end_marker, start) + len(end_marker)
replacement = '''            node_id = self._dev_config_entry.get("node_id")
            gateway_id = self._dev_config_entry.get("gateway_id")
            if node_id and gateway_id:
                from .gateway_transport import async_acquire_gateway_child

                self._interface = await async_acquire_gateway_child(
                    self._hass,
                    host=self._dev_config_entry[CONF_HOST],
                    gateway_id=gateway_id,
                    local_key=self._local_key,
                    protocol_version=float(self._dev_config_entry[CONF_PROTOCOL_VERSION]),
                    enable_debug=self._dev_config_entry.get(CONF_ENABLE_DEBUG, False),
                    device_id=self._dev_config_entry[CONF_DEVICE_ID],
                    cid=node_id,
                    listener=self,
                )
            else:
                self._interface = await pytuya.connect(
                    self._dev_config_entry[CONF_HOST],
                    self._dev_config_entry[CONF_DEVICE_ID],
                    self._local_key,
                    float(self._dev_config_entry[CONF_PROTOCOL_VERSION]),
                    self._dev_config_entry.get(CONF_ENABLE_DEBUG, False),
                    self,
                )
'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
