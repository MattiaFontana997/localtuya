# LocalTuya

![LocalTuya](img/logo-small.png)

Local control of Tuya devices for Home Assistant.

This repository is a modernization fork of the original LocalTuya project,
targeting current Home Assistant releases.

## LocalTuya 6.2

LocalTuya 6.2 adds stable and physically validated **Tuya protocol 3.5**
support while retaining support for protocols 3.1 through 3.4.

Highlights:

- Home Assistant 2026.9+
- Python 3.14 CI
- Tuya protocols 3.1, 3.2, 3.3, 3.4 and 3.5
- Automatic protocol probing including Tuya 3.5
- Tuya 3.5 6699 AES-GCM framing
- Tuya 3.5 session-key negotiation and authentication
- Tuya 3.5 payload handling and response sequence support
- Active LAN discovery for devices that do not advertise passively
- Automatic entity suggestions from Tuya Cloud metadata
- Community device catalog with remote cache and bundled offline snapshot
- Mapping review and privacy-safe community contribution flow
- Verified product-specific mappings
- Improved string-based Tuya v2 color-data mapping
- Diagnostics secret redaction
- Expanded protocol, catalog and lifecycle regression coverage

## Verified catalog devices

The bundled snapshot includes physically verified mappings for:

- **LSC Smart Connect RGB+CCT smart light**, sold by Action
- **EMOS GoSmart P56201 Wi-Fi Room Thermostat**

The remote community catalog can be refreshed independently of LocalTuya
releases.

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
- 3.5

## Important

This fork uses the same Home Assistant integration domain as upstream
LocalTuya:

`localtuya`

Do not install the upstream integration and this fork simultaneously.

## Documentation

Full documentation and development information:

https://github.com/MattiaFontana997/localtuya

Device catalog:

https://github.com/MattiaFontana997/localtuya-device-catalog

## Credits

Based on the original LocalTuya project and the work of its maintainers and
contributors:

https://github.com/rospogrigio/localtuya
