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
6. LocalTuya first tries Tuya LAN discovery to resolve the device address. If broadcast/multicast discovery cannot determine a usable address, LocalTuya asks for the current IP address or hostname instead of failing the onboarding.
7. Whether the address came from discovery or manual entry, LocalTuya authenticates directly to that LAN device with the Device ID/local key, auto-detects the Tuya protocol, reads datapoints, and only then resolves mappings through the LocalTuya catalog/mapper.
8. LocalTuya stores the validated local device configuration and a renewable account link for future provisioning.

The manual address fallback is intentionally not a bypass. A typed IP or hostname is accepted only when the selected Tuya identity and local key can actually communicate with that device over LAN and protocol/datapoint validation succeeds.

### Existing LocalTuya installation

An existing 6.5.x configuration does not need to be removed or recreated. Open LocalTuya options and choose **Link Smart Life / Tuya account by QR**, enter the User Code, and approve the generated QR code. Existing LAN devices and their mappings remain intact.

If the existing entry previously used the Tuya Developer Platform, choosing the QR account link explicitly migrates that entry to provisioning-only cloud access: `no_cloud` is enabled and the legacy Client ID, Client Secret and User ID are cleared. Normal device control therefore remains LAN-only after migration.

### Adding devices later

1. Open LocalTuya options and choose **Add a new device**.
2. Choose **From Smart Life / Tuya**.
3. LocalTuya refreshes the linked Tuya account once, saves any refreshed token, and shows only new locally controllable devices.
4. Choose the device. LocalTuya tries LAN discovery first and offers the same validated IP/hostname fallback when discovery is unavailable or blocked.

No new QR scan is required while the saved Tuya authorization remains valid.

## Runtime privacy model

The QR account link is provisioning-only. New QR-created entries keep the legacy LocalTuya cloud runtime disabled (`no_cloud: true`). Device control therefore continues over the Tuya LAN protocol and does not poll Tuya Cloud.

Persisted account-link data is limited to the User Code, terminal ID, endpoint, access/refresh token bundle required by `tuya-device-sharing-sdk`. Client ID, Client Secret, IoT Core project configuration and Tuya Developer Platform Data Center setup are not required for the standard flow.

Users may explicitly disconnect the linked Tuya account. This deletes the account authorization while keeping already configured device IDs, local keys, IP/protocol settings and mappings intact.

## Address resolution and validation

LocalTuya treats address discovery and device validation as two separate concerns:

- Tuya UDP discovery is the preferred source for the current LAN address because it also confirms the advertised device identity.
- Failure of UDP broadcast/multicast discovery is recoverable. Networks using VLANs, containers, restrictive access points or unusual multicast handling can still permit direct LAN communication.
- When discovery cannot provide the address, the user may enter the current IP address or hostname from a router/DHCP list.
- A manually entered address is never trusted merely because it is syntactically valid or accepts TCP connections. The normal LocalTuya Device ID/local-key authentication, protocol probing and datapoint retrieval must succeed before configuration can continue.
- Cloud-reported addresses are not used as an authority for local control.

## Safety rules

- A QR device is not saved unless a usable `local_key` is available.
- Automatic discovery is preferred, but its failure alone does not make a device ineligible for local control.
- Every discovered or manually supplied address must pass direct LAN authentication, protocol detection and datapoint retrieval before the device is stored.
- A wrong/unreachable address is rejected without saving partial device configuration.
- An authentication failure is kept distinct from an address/connectivity failure so stale IPs and stale local keys are not conflated.
- Cloud metadata is enrichment only and is fetched after local validation for the selected address.
- Product ID and temporary DP metadata may enrich automatic mapping, but observed LAN DPs remain authoritative.
- Hub child devices are rejected by the initial QR flow until LocalTuya has an explicit, tested child-device transport model.
- Cloud errors do not affect already configured LAN devices.
- QR tokens, refresh tokens and local keys must never be included in diagnostic or error logging.

## Backward compatibility

Existing LocalTuya configuration entries and the legacy Tuya Developer Platform cloud client remain readable for compatibility. The new standard onboarding does not expose those credentials as a requirement. Existing users can opt into QR onboarding in place; the migration preserves configured devices while disabling the legacy cloud runtime.

## Existing configuration import

The third onboarding mode accepts a single device JSON object, a list of devices, a LocalTuya `devices` object, or common Tuya/TinyTuya aliases (`id`, `key`, `ip`, `version`). Imported credentials are validated over LAN before they are saved. Existing entity definitions are preserved; otherwise Catalog/mapper suggestions and the manual fallback are used.

## Merge status

The implementation remains on a draft pull request until the complete User Code -> QR -> Smart Life/Tuya approval -> device retrieval -> LAN provisioning flow has been validated against a real Home Assistant installation and real Tuya account.
