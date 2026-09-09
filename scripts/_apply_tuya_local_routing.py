from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


qr_path = ROOT / "custom_components/localtuya/qr_onboarding.py"
qr = qr_path.read_text(encoding="utf-8")

qr = replace_once(
    qr,
    'TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"\nTUYA_SCHEMA = "haauthorize"\n',
    '''TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"\nTUYA_SCHEMA = "haauthorize"\n\n# Tuya hub categories mirrored from the proven tuya-local onboarding model.\n# These are transport/infrastructure devices, not entity platform guesses.\nTUYA_HUB_CATEGORIES = frozenset(\n    {\n        "wgsxj",\n        "lyqwg",\n        "bywg",\n        "zigbee",\n        "wg2",\n        "dgnzk",\n        "videohub",\n        "xnwg",\n        "qtyycp",\n        "alexa_yywg",\n        "gywg",\n        "cnwg",\n        "wnykq",\n        "wfcon",\n    }\n)\n''',
    "hub category constants",
)

qr = replace_once(
    qr,
    '''def _is_subdevice_flag(value: Any) -> bool:\n    """Normalize Tuya SDK/export sub-device flags without string truthiness."""\n    if isinstance(value, bool):\n        return value\n    if isinstance(value, (int, float)) and not isinstance(value, bool):\n        return value == 1\n    if isinstance(value, str):\n        return value.strip().lower() in {"1", "true", "yes"}\n    return False\n\n\nclass _TokenCapture''',
    '''def _is_subdevice_flag(value: Any) -> bool:\n    """Normalize Tuya SDK/export sub-device flags without string truthiness."""\n    if isinstance(value, bool):\n        return value\n    if isinstance(value, (int, float)) and not isinstance(value, bool):\n        return value == 1\n    if isinstance(value, str):\n        return value.strip().lower() in {"1", "true", "yes"}\n    return False\n\n\ndef _enrich_gateway_routes(\n    devices: dict[str, dict[str, Any]],\n) -> dict[str, dict[str, Any]]:\n    """Resolve Tuya child -> gateway transport metadata conservatively.\n\n    Device Sharing does not consistently expose gateway_id on BLE/Zigbee\n    children.  tuya-local works around that by treating known hub categories as\n    parent candidates and using the child node_id/uuid as the CID.  We follow\n    the same proven routing model while remaining fail-closed when more than one\n    possible hub exists.\n\n    Some Tuya accounts expose the *gateway* LAN key on the child record.  When\n    present, prefer it over the hub record key, matching tuya-local's behavior.\n    """\n    hubs = {\n        str(device_id): device\n        for device_id, device in devices.items()\n        if isinstance(device, dict) and device.get("is_hub")\n    }\n\n    for device in devices.values():\n        if not isinstance(device, dict) or not device.get("node_id"):\n            continue\n\n        gateway_id = str(device.get("gateway_id") or "").strip()\n        gateway = devices.get(gateway_id) if gateway_id else None\n\n        if not isinstance(gateway, dict) and len(hubs) == 1:\n            gateway_id, gateway = next(iter(hubs.items()))\n            device["gateway_id"] = gateway_id\n\n        if isinstance(gateway, dict):\n            child_key = str(device.get(CONF_LOCAL_KEY) or "").strip()\n            gateway_key = str(gateway.get(CONF_LOCAL_KEY) or "").strip()\n            device["gateway_local_key"] = child_key or gateway_key\n            device["gateway_ip"] = str(gateway.get("ip") or "").strip()\n            device["gateway_name"] = (\n                gateway.get(CONF_NAME) or gateway_id\n            )\n            device.pop("gateway_candidates", None)\n        elif len(hubs) > 1:\n            # Do not guess between multiple hubs.  Keep the candidates available\n            # for diagnostics/future UI selection, but do not mark the child as\n            # locally eligible until a parent is unambiguous.\n            device["gateway_candidates"] = sorted(hubs)\n\n    return devices\n\n\nclass _TokenCapture''',
    "gateway route enrichment helper",
)

qr = replace_once(
    qr,
    '''            local_key = str(getattr(device, "local_key", "") or "").strip()\n            product_id = str(getattr(device, "product_id", "") or "").strip()\n            node_id = str(getattr(device, "node_id", "") or "").strip()\n            gateway_id = str(\n                getattr(device, "gateway_id", "")\n                or getattr(device, "gatewayId", "")\n                or getattr(device, "parent_id", "")\n                or ""\n            ).strip()\n            is_subdevice = _is_subdevice_flag(getattr(device, "sub", False))\n            device_uuid = str(getattr(device, "uuid", "") or "").strip()\n            if not node_id and is_subdevice and gateway_id and device_uuid:\n                # Some Tuya subdevice records omit node_id. For an explicitly\n                # marked child with a known gateway, UUID is the local CID.\n                node_id = device_uuid\n            device_ip = str(getattr(device, "ip", "") or "").strip()\n\n            devices[device_id] = {\n                "id": device_id,\n                CONF_NAME: str(getattr(device, "name", "") or "").strip(),\n                CONF_LOCAL_KEY: local_key,\n                "product_id": product_id,\n                "product_name": str(\n                    getattr(device, "product_name", "") or ""\n                ).strip(),\n                "category": str(getattr(device, "category", "") or "").strip(),\n                "online": bool(getattr(device, "online", False)),\n                "support_local": bool(getattr(device, "support_local", False)),\n                "node_id": node_id,\n                "gateway_id": gateway_id,\n                "ip": device_ip,\n            }\n\n        for device in devices.values():\n            gateway_id = device.get("gateway_id")\n            if not device.get("node_id") or not gateway_id:\n                continue\n            gateway = devices.get(gateway_id)\n            if not isinstance(gateway, dict):\n                continue\n            device["gateway_local_key"] = gateway.get(CONF_LOCAL_KEY) or ""\n            device["gateway_ip"] = gateway.get("ip") or ""\n            device["gateway_name"] = gateway.get(CONF_NAME) or gateway_id\n\n        return devices\n''',
    '''            local_key = str(getattr(device, "local_key", "") or "").strip()\n            product_id = str(getattr(device, "product_id", "") or "").strip()\n            category = str(getattr(device, "category", "") or "").strip()\n            node_id = str(getattr(device, "node_id", "") or "").strip()\n            gateway_id = str(\n                getattr(device, "gateway_id", "")\n                or getattr(device, "gatewayId", "")\n                or getattr(device, "parent_id", "")\n                or ""\n            ).strip()\n            is_subdevice = _is_subdevice_flag(getattr(device, "sub", False))\n            device_uuid = str(getattr(device, "uuid", "") or "").strip()\n            if not node_id and is_subdevice and device_uuid:\n                # Tuya frequently omits gateway_id while still providing the\n                # child's UUID.  For an explicit sub-device, UUID is the CID.\n                node_id = device_uuid\n            device_ip = str(getattr(device, "ip", "") or "").strip()\n\n            devices[device_id] = {\n                "id": device_id,\n                CONF_NAME: str(getattr(device, "name", "") or "").strip(),\n                CONF_LOCAL_KEY: local_key,\n                "product_id": product_id,\n                "product_name": str(\n                    getattr(device, "product_name", "") or ""\n                ).strip(),\n                "category": category,\n                "online": bool(getattr(device, "online", False)),\n                "support_local": bool(getattr(device, "support_local", False)),\n                "sub": is_subdevice,\n                "uuid": device_uuid,\n                "node_id": node_id,\n                "gateway_id": gateway_id,\n                "is_hub": category in TUYA_HUB_CATEGORIES,\n                "ip": device_ip,\n            }\n\n        return _enrich_gateway_routes(devices)\n''',
    "SDK device normalization",
)

qr = replace_once(
    qr,
    '''def _qr_is_locally_eligible(device: dict[str, Any]) -> bool:\n    """Return whether Tuya supplied enough routing metadata for LAN validation."""\n    if not isinstance(device, dict):\n        return False\n    node_id = str(device.get("node_id") or "").strip()\n    if node_id:\n        return bool(\n            str(device.get("gateway_id") or "").strip()\n            and str(device.get("gateway_local_key") or "").strip()\n        )\n    return bool(str(device.get(CONF_LOCAL_KEY) or "").strip())\n''',
    '''def _qr_is_locally_eligible(device: dict[str, Any]) -> bool:\n    """Return whether Tuya supplied enough routing metadata for LAN validation."""\n    if not isinstance(device, dict):\n        return False\n    node_id = str(device.get("node_id") or "").strip()\n    if node_id:\n        return bool(\n            str(device.get("gateway_id") or "").strip()\n            and (\n                str(device.get("gateway_local_key") or "").strip()\n                or str(device.get(CONF_LOCAL_KEY) or "").strip()\n            )\n        )\n    return bool(str(device.get(CONF_LOCAL_KEY) or "").strip())\n''',
    "QR local eligibility",
)

qr = replace_once(
    qr,
    '''def _find_discovered_device(\n    devices: dict[str, dict[str, Any]],\n    device_id: str,\n) -> dict[str, Any] | None:\n    """Find one device by discovery dictionary key or gwId/id payload."""\n    direct = devices.get(device_id)\n    if isinstance(direct, dict):\n        return copy.deepcopy(direct)\n\n    for candidate in devices.values():\n        if not isinstance(candidate, dict):\n            continue\n        found_id = candidate.get("gwId") or candidate.get("id")\n        if found_id == device_id:\n            return copy.deepcopy(candidate)\n    return None\n\n\ndef _qr_host_schema''',
    '''def _find_discovered_device(\n    devices: dict[str, dict[str, Any]],\n    device_id: str,\n) -> dict[str, Any] | None:\n    """Find one device by discovery dictionary key or gwId/id payload."""\n    direct = devices.get(device_id)\n    if isinstance(direct, dict):\n        return copy.deepcopy(direct)\n\n    for candidate in devices.values():\n        if not isinstance(candidate, dict):\n            continue\n        found_id = candidate.get("gwId") or candidate.get("id")\n        if found_id == device_id:\n            return copy.deepcopy(candidate)\n    return None\n\n\nasync def _async_find_lan_device(\n    hass,\n    device_id: str,\n) -> dict[str, Any] | None:\n    """Find a specific Tuya device on LAN without trusting its cloud IP.\n\n    tuya-local deliberately scans for the real LAN address instead of using the\n    IP returned by Device Sharing.  Do the same here, with a few active 6699\n    discovery requests before a bounded one-shot listener fallback.\n    """\n    domain_data = hass.data.get(DOMAIN, {})\n    discovery = domain_data.get(DATA_DISCOVERY)\n\n    if discovery is not None:\n        for _attempt in range(3):\n            try:\n                await discovery.async_request_discovery()\n            except Exception as exc:\n                _LOGGER.debug("Targeted Tuya LAN discovery request failed: %s", exc)\n            await asyncio.sleep(1.25)\n            devices = getattr(discovery, "devices", {})\n            if isinstance(devices, dict):\n                found = _find_discovered_device(devices, device_id)\n                if found is not None:\n                    return found\n\n    from .discovery import discover\n\n    try:\n        devices = await discover(timeout=6.0, hass=hass)\n    except Exception as exc:\n        _LOGGER.debug("Targeted Tuya LAN discovery fallback failed: %s", exc)\n        return None\n\n    if not isinstance(devices, dict):\n        return None\n    return _find_discovered_device(devices, device_id)\n\n\ndef _qr_host_schema''',
    "targeted LAN discovery helper",
)

qr = replace_once(
    qr,
    '''    discovered_devices: dict[str, dict[str, Any]] = {}\n    discovered: dict[str, Any] = {}\n\n    if host_override is None:\n        try:\n            discovered_devices = await _async_discovery_snapshot(hass)\n        except QrProvisioningError as exc:\n            # Broadcast/multicast discovery is an optimization, not a hard\n            # requirement. Docker, VLANs and some APs can block it while direct\n            # LAN access still works perfectly.\n            _LOGGER.debug(\n                "QR discovery unavailable; manual LAN address fallback enabled (%s)",\n                exc.reason,\n            )\n            discovered_devices = {}\n\n        discovery_id = gateway_id if node_id else device_id\n        found = _find_discovered_device(discovered_devices, discovery_id)\n        if isinstance(found, dict):\n            discovered = found\n\n        host = str(\n            discovered.get("ip")\n            or (cloud_device.get("gateway_ip") if node_id else cloud_device.get("ip"))\n            or ""\n        ).strip()\n        if not host:\n            raise QrProvisioningError(\n                "qr_device_host_required",\n                "Automatic LAN discovery could not determine the device address",\n            )\n''',
    '''    discovered: dict[str, Any] = {}\n\n    if host_override is None:\n        discovery_id = gateway_id if node_id else device_id\n        found = await _async_find_lan_device(hass, discovery_id)\n        if isinstance(found, dict):\n            discovered = found\n\n        # Device Sharing may expose a WAN/cached IP.  Never accept that field as\n        # proof of the local endpoint: only LAN discovery or a user-supplied\n        # address that subsequently passes the full protocol probe is trusted.\n        host = str(discovered.get("ip") or "").strip()\n        if not host:\n            raise QrProvisioningError(\n                "qr_device_host_required",\n                "Automatic LAN discovery could not determine the device address",\n            )\n''',
    "LAN host selection",
)

qr_path.write_text(qr, encoding="utf-8")

probe_path = ROOT / "custom_components/localtuya/device_probe.py"
probe = probe_path.read_text(encoding="utf-8")
probe = replace_once(
    probe,
    '''            try:\n                detected_dps = await interface.detect_available_dps()\n            except Exception as ex:\n                if protocol_version == "3.3" and reset_ids:\n                    _LOGGER.debug(\n                        "Initial DPS detection failed using protocol %s (%s); "\n                        "trying reset IDs %s",\n                        protocol_version,\n                        type(ex).__name__,\n                        reset_ids,\n                    )\n                    await interface.reset(reset_ids)\n                    detected_dps = await interface.detect_available_dps()\n                else:\n                    raise\n\n            return detected_dps or {}\n''',
    '''            try:\n                # Match the proven tuya-local connection test: first ask for a\n                # normal device state.  Several real firmwares answer status()\n                # correctly but reject the broader DPS detection scan.\n                detected_dps = await interface.status()\n                if not detected_dps:\n                    detected_dps = await interface.detect_available_dps()\n            except Exception as ex:\n                if protocol_version == "3.3" and reset_ids:\n                    _LOGGER.debug(\n                        "Initial DPS detection failed using protocol %s (%s); "\n                        "trying reset IDs %s",\n                        protocol_version,\n                        type(ex).__name__,\n                        reset_ids,\n                    )\n                    await interface.reset(reset_ids)\n                    detected_dps = await interface.status()\n                    if not detected_dps:\n                        detected_dps = await interface.detect_available_dps()\n                else:\n                    raise\n\n            return detected_dps or {}\n''',
    "status-first protocol probe",
)
probe_path.write_text(probe, encoding="utf-8")

# Update existing gateway onboarding regressions for LAN-only address trust.
test_qr_path = ROOT / "tests/test_qr_gateway_onboarding.py"
test_qr = test_qr_path.read_text(encoding="utf-8")
test_qr = test_qr.replace(
    "from custom_components.localtuya.qr_onboarding import async_prepare_qr_device",
    "from custom_components.localtuya.qr_onboarding import (\n    QrProvisioningError,\n    async_prepare_qr_device,\n)",
)

start = test_qr.index("    async def test_sdk_ip_is_validated_when_udp_discovery_misses")
end = test_qr.index("    async def test_child_uses_gateway_transport_and_keeps_child_identity", start)
replacement = '''    async def test_sdk_ip_is_not_trusted_when_lan_discovery_misses(self):\n        """Cloud/SDK IP is only a hint; a missing LAN discovery asks for host."""\n        cloud_device = {\n            "id": "device-1",\n            "name": "Thermostat",\n            CONF_LOCAL_KEY: "local-secret",\n            "product_id": "product-1",\n            "category": "wk",\n            "node_id": "",\n            "ip": "198.51.100.55",\n        }\n        validate = AsyncMock()\n\n        with (\n            patch(\n                "custom_components.localtuya.qr_onboarding._async_find_lan_device",\n                new=AsyncMock(return_value=None),\n            ),\n            patch(\n                "custom_components.localtuya.config_flow.validate_input",\n                new=validate,\n            ),\n        ):\n            with self.assertRaises(QrProvisioningError) as context:\n                await async_prepare_qr_device(\n                    self._hass(),\n                    self._cloud(),\n                    cloud_device,\n                )\n\n        self.assertEqual(context.exception.reason, "qr_device_host_required")\n        validate.assert_not_awaited()\n\n'''
test_qr = test_qr[:start] + replacement + test_qr[end:]
test_qr = test_qr.replace(
    '''patch(\n                "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",\n                new=AsyncMock(return_value={}),\n            )''',
    '''patch(\n                "custom_components.localtuya.qr_onboarding._async_find_lan_device",\n                new=AsyncMock(\n                    return_value={\n                        "gwId": "gateway-device-1",\n                        "ip": "192.168.1.80",\n                    }\n                ),\n            )''',
    1,
)
test_qr = test_qr.replace(
    '''patch(\n                "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",\n                new=AsyncMock(return_value=discovered),\n            )''',
    '''patch(\n                "custom_components.localtuya.qr_onboarding._async_find_lan_device",\n                new=AsyncMock(return_value=discovered["gateway-device-1"]),\n            )''',
    1,
)
test_qr_path.write_text(test_qr, encoding="utf-8")

# Existing probe unit tests now exercise the status-first path.
test_probe_path = ROOT / "tests/test_device_probe.py"
test_probe = test_probe_path.read_text(encoding="utf-8")
test_probe = replace_once(
    test_probe,
    '''        interface.detect_available_dps = AsyncMock(\n            return_value={"1": True, "20": 42}\n        )\n''',
    '''        interface.status = AsyncMock(return_value={"1": True, "20": 42})\n        interface.detect_available_dps = AsyncMock()\n''',
    "probe child status fixture",
)
test_probe = replace_once(
    test_probe,
    '''        interface.detect_available_dps = AsyncMock(return_value={"1": True})\n''',
    '''        interface.status = AsyncMock(return_value={"1": True})\n        interface.detect_available_dps = AsyncMock()\n''',
    "probe retry status fixture",
)
test_probe = test_probe.replace(
    "        interface.detect_available_dps.assert_awaited_once_with()\n",
    "        interface.status.assert_awaited_once_with()\n        interface.detect_available_dps.assert_not_awaited()\n",
)

marker = "    async def test_second_connect_failure_is_propagated(self):\n"
fallback_test = '''    async def test_empty_status_falls_back_to_extended_dps_detection(self):\n        interface = unittest.mock.MagicMock()\n        interface.status = AsyncMock(return_value={})\n        interface.detect_available_dps = AsyncMock(return_value={"1": True})\n        interface.close = AsyncMock()\n        connect = AsyncMock(return_value=interface)\n\n        with patch.object(device_probe.pytuya, "connect", connect):\n            result = await device_probe._async_probe_protocol(\n                self._child_data(),\n                "3.3",\n                [],\n            )\n\n        self.assertEqual(result, {"1": True})\n        interface.status.assert_awaited_once_with()\n        interface.detect_available_dps.assert_awaited_once_with()\n        interface.close.assert_awaited_once_with()\n\n'''
if marker not in test_probe:
    raise RuntimeError("probe fallback insertion marker missing")
test_probe = test_probe.replace(marker, fallback_test + marker, 1)
test_probe_path.write_text(test_probe, encoding="utf-8")

metadata_test = ROOT / "tests/test_tuya_local_gateway_metadata.py"
metadata_test.write_text(
    '''"""Regressions for Tuya Device Sharing hub/child metadata quirks."""\n\nfrom __future__ import annotations\n\nimport unittest\n\nfrom custom_components.localtuya.const import CONF_LOCAL_KEY\nfrom custom_components.localtuya.qr_onboarding import (\n    TUYA_HUB_CATEGORIES,\n    _enrich_gateway_routes,\n    _qr_is_locally_eligible,\n)\n\n\nclass TuyaLocalGatewayMetadataTests(unittest.TestCase):\n    def test_known_bluetooth_gateway_category_is_recognized(self):\n        self.assertIn("wg2", TUYA_HUB_CATEGORIES)\n\n    def test_single_hub_recovers_missing_gateway_id_and_prefers_child_key(self):\n        devices = {\n            "gateway-1": {\n                "id": "gateway-1",\n                "name": "Bluetooth Gateway",\n                CONF_LOCAL_KEY: "hub-local-key",\n                "ip": "192.168.1.20",\n                "is_hub": True,\n                "node_id": "",\n            },\n            "lamp-1": {\n                "id": "lamp-1",\n                "name": "BLE Lamp",\n                CONF_LOCAL_KEY: "child-exposed-gateway-key",\n                "node_id": "child-uuid-as-cid",\n                "gateway_id": "",\n                "is_hub": False,\n            },\n        }\n\n        result = _enrich_gateway_routes(devices)\n        child = result["lamp-1"]\n\n        self.assertEqual(child["gateway_id"], "gateway-1")\n        self.assertEqual(child["gateway_local_key"], "child-exposed-gateway-key")\n        self.assertEqual(child["gateway_ip"], "192.168.1.20")\n        self.assertTrue(_qr_is_locally_eligible(child))\n\n    def test_single_hub_key_is_used_when_child_has_no_key(self):\n        devices = {\n            "gateway-1": {\n                "id": "gateway-1",\n                CONF_LOCAL_KEY: "hub-local-key",\n                "ip": "192.168.1.20",\n                "is_hub": True,\n                "node_id": "",\n            },\n            "lamp-1": {\n                "id": "lamp-1",\n                CONF_LOCAL_KEY: "",\n                "node_id": "cid-1",\n                "gateway_id": "",\n                "is_hub": False,\n            },\n        }\n\n        child = _enrich_gateway_routes(devices)["lamp-1"]\n        self.assertEqual(child["gateway_local_key"], "hub-local-key")\n        self.assertTrue(_qr_is_locally_eligible(child))\n\n    def test_multiple_hubs_remain_fail_closed_without_explicit_parent(self):\n        devices = {\n            "gateway-1": {\n                "id": "gateway-1",\n                CONF_LOCAL_KEY: "key-1",\n                "is_hub": True,\n            },\n            "gateway-2": {\n                "id": "gateway-2",\n                CONF_LOCAL_KEY: "key-2",\n                "is_hub": True,\n            },\n            "lamp-1": {\n                "id": "lamp-1",\n                CONF_LOCAL_KEY: "child-key",\n                "node_id": "cid-1",\n                "gateway_id": "",\n                "is_hub": False,\n            },\n        }\n\n        child = _enrich_gateway_routes(devices)["lamp-1"]\n        self.assertFalse(child.get("gateway_id"))\n        self.assertEqual(child["gateway_candidates"], ["gateway-1", "gateway-2"])\n        self.assertFalse(_qr_is_locally_eligible(child))\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
    encoding="utf-8",
)

print("Applied Tuya-local-compatible gateway routing and status-first LAN probing")
