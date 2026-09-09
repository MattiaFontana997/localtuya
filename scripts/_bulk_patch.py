from pathlib import Path

p = Path('custom_components/localtuya/qr_onboarding.py')
s = p.read_text(encoding='utf-8')

# Add selector import.
s = s.replace(
    '    QrErrorCorrectionLevel,\n    TextSelector,\n',
    '    QrErrorCorrectionLevel,\n    SelectSelector,\n    SelectSelectorConfig,\n    SelectSelectorMode,\n    TextSelector,\n',
    1,
)

# Add constants.
s = s.replace(
    'CONF_IMPORT_DEVICE_ID = "import_device_id"\n',
    'CONF_IMPORT_DEVICE_ID = "import_device_id"\nCONF_QR_BULK_DEVICE_IDS = "qr_bulk_device_ids"\nCONF_QR_BULK_MODE = "qr_bulk_mode"\n',
    1,
)

# Insert mixin helpers before first async_step_qr_choose_device occurrence.
marker = '    async def async_step_qr_choose_device(self, user_input=None):\n'
idx = s.find(marker)
if idx < 0:
    raise SystemExit('choose-device step not found')
helper = '''    def _bulk_eligible_devices(self):
        """Return QR devices not already configured in this LocalTuya entry."""
        devices = getattr(self, "_qr_devices", {})
        configured = set()
        entry = getattr(self, "config_entry", None)
        entry_data = getattr(entry, "data", {}) if entry is not None else {}
        current = entry_data.get(CONF_DEVICES, {}) if isinstance(entry_data, dict) else {}
        if isinstance(current, dict):
            configured = {str(device_id) for device_id in current}

        return {
            str(device_id): device
            for device_id, device in devices.items()
            if str(device_id) not in configured
        }

    async def _async_bulk_prepare_devices(self, device_ids):
        """Provision selected devices sequentially while isolating failures."""
        devices = getattr(self, "_qr_devices", {})
        cloud = getattr(self, "_qr_cloud", None)
        successes = []
        failures = []

        for raw_device_id in device_ids:
            device_id = str(raw_device_id)
            cloud_device = devices.get(device_id)
            if not isinstance(cloud_device, dict):
                failures.append({"device_id": device_id, "reason": "device_not_found"})
                continue

            try:
                device_data, candidates = await async_prepare_qr_device(
                    self.hass,
                    cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                failures.append({"device_id": device_id, "reason": exc.reason})
                continue
            except Exception as exc:  # noqa: BLE001 - isolate one device in bulk mode.
                _LOGGER.debug(
                    "Bulk QR provisioning failed for one device: %s",
                    type(exc).__name__,
                )
                failures.append({"device_id": device_id, "reason": "probe_error"})
                continue

            successes.append(
                {
                    "device_id": device_id,
                    "device_data": device_data,
                    "candidates": candidates,
                }
            )

        return {"successes": successes, "failures": failures}

    async def async_step_qr_bulk_choose_devices(self, user_input=None):
        """Select multiple QR devices for sequential onboarding."""
        eligible = self._bulk_eligible_devices()
        if not eligible:
            return self.async_abort(reason="no_new_devices")

        if user_input is not None:
            selected = [
                str(device_id)
                for device_id in user_input.get(CONF_QR_BULK_DEVICE_IDS, [])
                if str(device_id) in eligible
            ]
            if not selected:
                return self.async_show_form(
                    step_id="qr_bulk_choose_devices",
                    data_schema=self._qr_bulk_schema(eligible),
                    errors={"base": "select_at_least_one_device"},
                )
            self._qr_bulk_result = await self._async_bulk_prepare_devices(selected)
            return await self.async_step_qr_bulk_summary()

        return self.async_show_form(
            step_id="qr_bulk_choose_devices",
            data_schema=self._qr_bulk_schema(eligible),
        )

    @staticmethod
    def _qr_bulk_schema(eligible):
        """Build the translated multi-select schema for eligible devices."""
        options = [
            {
                "value": str(device_id),
                "label": str(device.get(CONF_NAME) or device_id),
            }
            for device_id, device in eligible.items()
        ]
        return vol.Schema(
            {
                vol.Required(CONF_QR_BULK_DEVICE_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_qr_bulk_summary(self, user_input=None):
        """Persist successful bulk devices and summarize per-device failures."""
        result = getattr(self, "_qr_bulk_result", {"successes": [], "failures": []})
        successes = result.get("successes", [])
        failures = result.get("failures", [])

        entry = getattr(self, "config_entry", None)
        entry_data = copy.deepcopy(dict(getattr(entry, "data", {}) or {}))
        devices = entry_data.setdefault(CONF_DEVICES, {})
        if not isinstance(devices, dict):
            devices = {}
            entry_data[CONF_DEVICES] = devices

        added = []
        review_required = []
        for item in successes:
            device_data = copy.deepcopy(item["device_data"])
            candidates = item.get("candidates", [])
            high = [candidate for candidate in candidates if getattr(candidate, "confidence", None) == MappingConfidence.HIGH]
            medium = [candidate for candidate in candidates if getattr(candidate, "confidence", None) == MappingConfidence.MEDIUM]
            entities = [copy.deepcopy(candidate.config) for candidate in high]
            if medium:
                review_required.append(str(item["device_id"]))
            if not entities and not medium:
                review_required.append(str(item["device_id"]))
            device_data[CONF_ENTITIES] = entities
            devices[str(item["device_id"])] = device_data
            added.append(str(item["device_id"]))

        if added and entry is not None and hasattr(self.hass, "config_entries"):
            entry_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
            self.hass.config_entries.async_update_entry(entry, data=entry_data)

        self._qr_bulk_summary = {
            "added": added,
            "review_required": review_required,
            "failures": failures,
        }

        return self.async_create_entry(
            title="",
            data={},
            description_placeholders={
                "added_count": str(len(added)),
                "failed_count": str(len(failures)),
                "review_count": str(len(review_required)),
            },
        )

'''
s = s[:idx] + helper + s[idx:]

# Ensure time is imported.
if 'import time\n' not in s.split('\n', 20):
    s = s.replace('import logging\n', 'import logging\nimport time\n', 1)

p.write_text(s, encoding='utf-8')
