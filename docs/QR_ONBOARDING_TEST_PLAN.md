# QR onboarding test plan

Before merge into `develop`, validate these scenarios on Home Assistant:

1. Fresh LocalTuya install shows three onboarding modes: QR login as the recommended path, manual setup as the advanced fallback, and import of an existing configuration/local_key.
2. Valid Smart Life User Code generates a QR selector.
3. Scanning/approving the QR returns an account device list without Tuya Developer Platform credentials.
4. Only devices with usable local credentials are offered.
5. Selecting a normally discoverable LAN device resolves its IP locally, detects protocol version and maps entities.
6. With Tuya UDP discovery unavailable, blocked or unable to resolve the selected device, the flow asks for the current LAN IP address/hostname instead of aborting.
7. Enter a wrong/unreachable fallback address and confirm LocalTuya rejects it without saving a partial device configuration.
8. Enter the correct fallback address and confirm Device ID/local_key authentication, protocol auto-detection and datapoint retrieval all succeed before mapping or save.
9. Confirm an invalid/stale local key produces an authentication error distinct from an address/connectivity error.
10. Confirm cloud DP/product metadata is enrichment only: it must not make a device pass when direct LAN validation fails.
11. Restart Home Assistant with Internet unavailable: already configured devices continue to operate locally.
12. Add another Smart Life/Tuya device later, then use Add device -> From Smart Life / Tuya without repeating QR login.
13. Repeat the blocked-discovery/manual-address fallback while adding a later device through the saved account link.
14. Confirm refreshed sharing tokens are persisted after the explicit sync.
15. Re-link account by QR after invalidating the saved authorization.
16. Disconnect account and confirm configured LAN devices remain present and operational.
17. Manual Device ID + local_key setup remains available.
18. Import of an existing configuration/local_key validates credentials and LAN connectivity before saving.
19. Upgrade an existing LocalTuya 6.5.x entry and link Smart Life/Tuya by QR without deleting the integration; confirm configured devices remain intact.
20. For an entry that previously used the Tuya Developer Platform, confirm QR linking sets `no_cloud: true` and clears the legacy Client ID, Client Secret and User ID while preserving devices.
21. Confirm QR tokens, refresh tokens and local keys never appear in diagnostics or error logs, including failed manual-address validation.
22. HACS validation, Hassfest, translation coverage and the complete LocalTuya test suite remain green.

## Existing configuration import

- Import a LocalTuya root `devices` object and confirm Device ID/local_key normalization.
- Import an `id/key/ip/version` record and confirm alias normalization.
- Import without an IP and confirm LAN discovery supplies the host before validation.
- Confirm invalid JSON or missing Device ID/local_key is rejected without logging secrets.

## Real-network fallback smoke test

- Use a device that is visible in the QR account list but not returned by Tuya UDP discovery.
- Confirm the device selector automatically advances to the LAN-address fallback form.
- Read the device's current IP from the router/DHCP client list rather than reusing a stale LocalTuya address.
- Confirm a deliberately wrong IP fails and leaves the flow open for correction.
- Confirm the correct IP advances only after direct LAN authentication, protocol detection and datapoint retrieval.
- Complete mapping and save, restart Home Assistant, then verify the device remains controllable with Internet access disabled.
