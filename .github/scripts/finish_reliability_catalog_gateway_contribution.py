from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


# Gateway child metadata: safe UUID->CID fallback and import preservation.
path = Path("custom_components/localtuya/qr_onboarding.py")
text = path.read_text(encoding="utf-8")
needle = '''            gateway_id = str(
                getattr(device, "gateway_id", "")
                or getattr(device, "gatewayId", "")
                or getattr(device, "parent_id", "")
                or ""
            ).strip()
            device_ip = str(getattr(device, "ip", "") or "").strip()
'''
replacement = '''            gateway_id = str(
                getattr(device, "gateway_id", "")
                or getattr(device, "gatewayId", "")
                or getattr(device, "parent_id", "")
                or ""
            ).strip()
            is_subdevice = bool(getattr(device, "sub", False))
            device_uuid = str(getattr(device, "uuid", "") or "").strip()
            if not node_id and is_subdevice and gateway_id and device_uuid:
                # Some Tuya subdevice records omit node_id. For an explicitly
                # marked child with a known gateway, UUID is the local CID.
                node_id = device_uuid
            device_ip = str(getattr(device, "ip", "") or "").strip()
'''
text = replace_once(text, needle, replacement, "QR child metadata")

needle = '''    if protocol not in {"auto", "3.1", "3.2", "3.3", "3.4", "3.5"}:
        protocol = "auto"
    result: dict[str, Any] = {
'''
replacement = '''    if protocol not in {"auto", "3.1", "3.2", "3.3", "3.4", "3.5"}:
        protocol = "auto"
    gateway_id = str(
        raw.get("gateway_id")
        or raw.get("gatewayId")
        or raw.get("parent_id")
        or ""
    ).strip()
    node_id = str(
        raw.get("node_id")
        or raw.get("cid")
        or raw.get("device_cid")
        or ""
    ).strip()
    if not node_id and bool(raw.get("sub", False)) and gateway_id:
        node_id = str(raw.get("uuid") or "").strip()
    result: dict[str, Any] = {
'''
text = replace_once(text, needle, replacement, "import routing metadata")

needle = '''        CONF_ENABLE_DEBUG: bool(raw.get(CONF_ENABLE_DEBUG, False)),
    }
    product_key = (
'''
replacement = '''        CONF_ENABLE_DEBUG: bool(raw.get(CONF_ENABLE_DEBUG, False)),
    }
    if node_id:
        result["node_id"] = node_id
    if gateway_id:
        result["gateway_id"] = gateway_id
    product_key = (
'''
text = replace_once(text, needle, replacement, "import routing persistence")
path.write_text(text, encoding="utf-8")

# Repairs must write wall-clock epoch metadata, not event-loop monotonic time.
path = Path("custom_components/localtuya/repairs.py")
text = path.read_text(encoding="utf-8")
text = replace_once(text, "import copy\n", "import copy\nimport time\n", "repairs time import")
text = replace_once(
    text,
    'str(int(asyncio.get_running_loop().time() * 1000))',
    'str(int(time.time() * 1000))',
    "repairs updated_at",
)
path.write_text(text, encoding="utf-8")

# Normal contribution UX: review -> prefilled GitHub directly. The old JSON
# result step remains only as a backwards-compatible internal fallback.
path = Path("custom_components/localtuya/config_flow.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "                return await self.async_step_prepare_contribution_result()\n",
    "                return await self.async_step_submit_to_community_catalog()\n",
    "contribution direct submit",
)
path.write_text(text, encoding="utf-8")

# Compact the GitHub prefill so ordinary contributions fit without asking the
# user to copy JSON. Keep the pretty JSON only for internal/fallback use.
path = Path("custom_components/localtuya/mapping_export.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "MAX_GITHUB_PREFILL_URL_LENGTH = 7500",
    "MAX_GITHUB_PREFILL_URL_LENGTH = 30000",
    "GitHub prefill limit",
)
needle = '''    suggested_filename = f"{mapping_id}.json"
    new_submission_url = _build_github_submission_url(
        suggested_filename,
        submission_json,
    )
'''
replacement = '''    suggested_filename = f"{mapping_id}.json"
    submission_prefill_json = json.dumps(
        submission,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    new_submission_url = _build_github_submission_url(
        suggested_filename,
        submission_prefill_json,
    )
'''
text = replace_once(text, needle, replacement, "compact contribution prefill")
path.write_text(text, encoding="utf-8")
