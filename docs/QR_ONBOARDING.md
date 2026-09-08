# LocalTuya QR onboarding

## Goal

Make Smart Life / Tuya QR login the recommended onboarding path without requiring users to create or maintain a Tuya Developer Platform project.

## User flow

### First setup

1. Install LocalTuya.
2. Choose **QR login with Smart Life / Tuya**.
3. Enter the Smart Life / Tuya **User Code**.
4. Scan the generated QR code in the mobile app and approve access.
5. Choose a locally controllable device.
6. LocalTuya combines temporary cloud metadata with LAN discovery, auto-detects the Tuya LAN protocol, and resolves mappings through the LocalTuya catalog/mapper.
7. LocalTuya stores the local device configuration and a renewable account link for future provisioning.

### Existing LocalTuya installation

An existing 6.5.x configuration does not need to be removed or recreated. Open LocalTuya options and choose **Link Smart Life / Tuya account by QR**, enter the User Code, and approve the generated QR code. Existing LAN devices and their mappings remain intact.

If the existing entry previously used the Tuya Developer Platform, choosing the QR account link explicitly migrates that entry to provisioning-only cloud access: `no_cloud` is enabled and the legacy Client ID, Client Secret and User ID are cleared. Normal device control therefore remains LAN-only after migration.

### Adding devices later

1. Open LocalTuya options and choose **Add a new device**.
2. Choose **From Smart Life / Tuya**.
3. LocalTuya refreshes the linked Tuya account once, saves any refreshed token, and shows only new locally controllable devices.
4. Choose the device. LocalTuya performs LAN discovery and mapping as above.

No new QR scan is required while the saved Tuya authorization remains valid.

## Runtime privacy model

The QR account link is provisioning-only. New QR-created entries keep the legacy LocalTuya cloud runtime disabled (`no_cloud: true`). Device control therefore continues over the Tuya LAN protocol and does not poll Tuya Cloud.

Persisted account-link data is limited to the User Code, terminal ID, endpoint, access/refresh token bundle required by `tuya-device-sharing-sdk`. Client ID, Client Secret, IoT Core project configuration and Tuya Developer Platform Data Center setup are not required for the standard flow.

Users may explicitly disconnect the linked Tuya account. This deletes the account authorization while keeping already configured device IDs, local keys, IP/protocol settings and mappings intact.

## Safety rules

- A QR device is not saved unless a usable `local_key` is available.
- Cloud-reported IP addresses are not trusted for local control; LocalTuya must find the selected device on the Home Assistant LAN.
- LAN protocol detection must succeed before the device is stored.
- Product ID and temporary DP metadata may enrich automatic mapping, but observed LAN DPs remain authoritative.
- Hub child devices are rejected by the initial QR flow until LocalTuya has an explicit, tested child-device transport model.
- Cloud errors do not affect already configured LAN devices.

## Backward compatibility

Existing LocalTuya configuration entries and the legacy Tuya Developer Platform cloud client remain readable for compatibility. The new standard onboarding does not expose those credentials as a requirement. Existing users can opt into QR onboarding in place; the migration preserves configured devices while disabling the legacy cloud runtime.

## Existing configuration import

The third onboarding mode accepts a single device JSON object, a list of devices, a LocalTuya `devices` object, or common Tuya/TinyTuya aliases (`id`, `key`, `ip`, `version`). Imported credentials are validated over LAN before they are saved. Existing entity definitions are preserved; otherwise Catalog/mapper suggestions and the manual fallback are used.

## Merge status

The implementation remains on a draft pull request until the complete User Code -> QR -> Smart Life/Tuya approval -> device retrieval -> LAN provisioning flow has been validated against a real Home Assistant installation and real Tuya account.
