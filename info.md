# LocalTuya

![LocalTuya](img/logo-small.png)

Local control of Tuya devices for Home Assistant.

This repository is a modernization fork of the original LocalTuya project,
targeting current Home Assistant releases.

## LocalTuya 6.0

This release includes:

- Home Assistant 2026 support
- Python 3.14 CI
- Tuya protocols 3.1–3.4
- Hardened Tuya 3.4 session handling
- Modern asynchronous Tuya Cloud API
- Improved LAN discovery
- 55AA and 6699 discovery frame support
- Automatic entity suggestions from Tuya Cloud metadata
- Confidence-based automatic configuration
- Generic light mapping
- Generic climate mapping
- Generic cover mapping
- Generic fan mapping
- Generic switch mapping
- Binary sensor mapping
- Measurement sensor mapping
- Number and select mapping
- Diagnostics secret redaction
- Expanded lifecycle and protocol regression tests

The current automated test suite contains **41 tests**.

## Automatic configuration

High-confidence entities are selected automatically.

Medium-confidence suggestions are presented for review and remain unselected
until you choose them.

Manual configuration is always available.

## Supported Tuya protocols

Stable:

- 3.1
- 3.2
- 3.3
- 3.4

Protocol 3.5 is intentionally not part of this stable release until it has
been validated with real 3.5 hardware.

## Important

This fork uses the same Home Assistant integration domain as upstream
LocalTuya:

`localtuya`

Do not install the upstream integration and this fork simultaneously.

## Documentation

Full documentation and development information:

https://github.com/MattiaFontana997/localtuya

## Credits

Based on the original LocalTuya project and the work of its maintainers and
contributors:

https://github.com/rospogrigio/localtuya
