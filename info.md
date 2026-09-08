# LocalTuya

![LocalTuya](img/logo-small.png)

Local control of Tuya devices for Home Assistant.

This repository is a maintained modernization fork of the original LocalTuya project, targeting current Home Assistant releases with safer protocol handling, QR-based provisioning and a community-driven device catalog.

## LocalTuya 6.6.0

LocalTuya 6.6.0 adds the recommended **Smart Life / Tuya QR onboarding flow**.

Standard setup no longer requires a Tuya Developer Platform project, Data Center configuration, Client ID or Client Secret.

Recommended flow:

`User Code → scan QR → choose device → LAN validation → automatic mapping`

Highlights:

- Home Assistant 2026.9+
- Python 3.14 CI
- Tuya protocols 3.1, 3.2, 3.3, 3.4 and 3.5
- Smart Life / Tuya User Code + QR provisioning
- Device ID, `local_key`, Product ID and provisioning metadata retrieval
- LAN discovery with validated IP / hostname fallback
- Automatic protocol probing and datapoint validation before save
- LAN-only normal runtime after QR provisioning
- Automatic entity suggestions and catalog-first mappings
- Community Device Catalog with remote cache and bundled offline snapshot
- Advanced and multi-DP catalog mappings
- Privacy-safe community contribution flow
- Diagnostics secret redaction
- Existing manual Device ID + `local_key` setup retained

## QR setup guide

Full step-by-step instructions:

https://github.com/MattiaFontana997/localtuya/blob/master/docs/QR_SETUP_GUIDE.md

## Community Device Catalog

The remote catalog can be refreshed independently of LocalTuya releases and supports product-specific mappings plus conservative fingerprints for eligible devices without Product IDs.

Device catalog:

https://github.com/MattiaFontana997/localtuya-device-catalog

## Important

This fork uses the same Home Assistant integration domain as upstream LocalTuya:

`localtuya`

Do not install the upstream integration and this fork simultaneously.

## Documentation

https://github.com/MattiaFontana997/localtuya

## Credits

Based on the original LocalTuya project and the work of its maintainers and contributors:

https://github.com/rospogrigio/localtuya
