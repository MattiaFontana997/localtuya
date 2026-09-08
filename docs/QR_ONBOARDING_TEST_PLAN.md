# QR onboarding test plan

Before merge into `develop`, validate these scenarios on Home Assistant:

1. Fresh LocalTuya install shows three onboarding modes: QR login as the recommended path, manual setup as the advanced fallback, and import of an existing configuration/local_key.
2. Valid Smart Life User Code generates a QR selector.
3. Scanning/approving the QR returns an account device list without Tuya Developer Platform credentials.
4. Only devices with usable local credentials are offered.
5. Selecting a LAN device resolves its IP locally, detects protocol version and maps entities.
6. Restart Home Assistant with Internet unavailable: already configured devices continue to operate locally.
7. Add another Smart Life/Tuya device later, then use Add device -> From Smart Life / Tuya without repeating QR login.
8. Confirm refreshed sharing tokens are persisted after the explicit sync.
9. Re-link account by QR after invalidating the saved authorization.
10. Disconnect account and confirm configured LAN devices remain present and operational.
11. Manual Device ID + local_key setup remains available.
12. Import of an existing configuration/local_key validates credentials and LAN connectivity before saving.
13. Upgrade an existing LocalTuya 6.5.x entry and link Smart Life/Tuya by QR without deleting the integration; confirm configured devices remain intact.
14. For an entry that previously used the Tuya Developer Platform, confirm QR linking sets `no_cloud: true` and clears the legacy Client ID, Client Secret and User ID while preserving devices.
15. HACS validation, Hassfest, translation coverage and the complete LocalTuya test suite remain green.

## Existing configuration import
- Import a LocalTuya root `devices` object and confirm Device ID/local_key normalization.
- Import an `id/key/ip/version` record and confirm alias normalization.
- Import without an IP and confirm LAN discovery supplies the host before validation.
- Confirm invalid JSON or missing Device ID/local_key is rejected without logging secrets.
