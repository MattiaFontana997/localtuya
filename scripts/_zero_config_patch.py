from pathlib import Path

p = Path('custom_components/localtuya/qr_onboarding.py')
s = p.read_text(encoding='utf-8')

if 'from .zero_config import (' not in s:
    s = s.replace(
        'from .device_mapper import MappingConfidence\n',
        'from .device_mapper import MappingConfidence\nfrom .zero_config import (\n    ZeroConfigDecision,\n    evaluate_zero_config,\n)\n',
        1,
    )

# Replace bulk confidence-only persistence block when present.
old = '''            candidates = item.get("candidates", [])
            high = [candidate for candidate in candidates if getattr(candidate, "confidence", None) == MappingConfidence.HIGH]
            medium = [candidate for candidate in candidates if getattr(candidate, "confidence", None) == MappingConfidence.MEDIUM]
            entities = [copy.deepcopy(candidate.config) for candidate in high]
            if medium:
                review_required.append(str(item["device_id"]))
            if not entities and not medium:
                review_required.append(str(item["device_id"]))
            device_data[CONF_ENTITIES] = entities
'''
new = '''            candidates = item.get("candidates", [])
            zero_config = evaluate_zero_config(candidates)
            entities = (
                copy.deepcopy(zero_config.entities)
                if zero_config.decision is ZeroConfigDecision.AUTO_CONFIGURE
                else []
            )
            if zero_config.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                review_required.append(str(item["device_id"]))
            device_data[CONF_ENTITIES] = entities
'''
if old in s:
    s = s.replace(old, new, 1)

# Wire ordinary single-device QR path: before medium-candidate review, auto-save
# only when the decision engine says the whole mapping is deterministic.
needle = '        medium_candidates = [\n'
pos = s.find(needle)
if pos >= 0 and 'zero_config = evaluate_zero_config(candidates)' not in s[max(0, pos-1200):pos+500]:
    insertion = '''        zero_config = evaluate_zero_config(candidates)
        if zero_config.decision is ZeroConfigDecision.AUTO_CONFIGURE:
            device_data[CONF_ENTITIES] = copy.deepcopy(zero_config.entities)
            return await self._async_finish_qr_device(device_data)

'''
    s = s[:pos] + insertion + s[pos:]

p.write_text(s, encoding='utf-8')
