from pathlib import Path

path = Path("custom_components/localtuya/qr_onboarding.py")
text = path.read_text()
old = '''        except Exception as exc:
            _LOGGER.exception("Unexpected imported-device validation failure: %s", exc)
            error, placeholders = "unknown", {}
'''
new = '''        except Exception as exc:
            # Never log exception text here: an underlying library could include
            # device credentials in its message. The exception class is enough
            # for diagnostics while keeping imported secrets private.
            _LOGGER.error(
                "Unexpected imported-device validation failure (%s)",
                type(exc).__name__,
            )
            error, placeholders = "unknown", {}
'''
if old not in text:
    raise SystemExit("privacy hardening anchor not found")
path.write_text(text.replace(old, new, 1))
