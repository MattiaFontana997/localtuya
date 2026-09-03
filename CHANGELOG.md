# Changelog

## 6.0.0

Major modernization release of the LocalTuya fork.

### Home Assistant

- Target Home Assistant 2026.9+
- Python 3.14 test environment
- Modernized CI and HACS validation
- Updated repository dependency tooling

### Automatic entity mapping

Added Tuya Cloud metadata based suggestions for:

- Lights
- Climate
- Covers
- Fans
- Switches
- Binary sensors
- Measurement sensors
- Numbers
- Selects

Automatic mapping uses confidence levels:

- High-confidence entities are preselected
- Medium-confidence entities require user selection
- Low-confidence mappings are not exposed automatically

### Tuya Cloud

- Modern asynchronous Cloud API client
- Signed requests
- Device metadata cache
- Device specification retrieval
- v1.1 specification support
- v1.0 specification fallback
- Validation of numeric DP identifiers

### LAN discovery

- UDP 6666 support
- UDP 6667 support
- UDP 7000 support
- Plain JSON discovery packets
- Legacy AES-ECB packets
- 55AA framing and CRC validation
- 6699 AES-GCM authenticated discovery

### Protocol

Stable support remains:

- Tuya 3.1
- Tuya 3.2
- Tuya 3.3
- Tuya 3.4

Additional hardening includes:

- CRC validation
- HMAC validation
- Safer malformed-packet handling
- Fresh protocol 3.4 session nonces
- Session-key validation
- Session-key reset after disconnect

Protocol 3.5 is not included in this release because physical 3.5 hardware
validation has not yet been completed.

### Diagnostics and lifecycle

- Sensitive credentials are redacted from diagnostics
- Added config-entry setup regression coverage
- Added migration coverage
- Added unload and device-close coverage
- Added failed-unload protection coverage

### Tests

The release is covered by 41 automated regression tests running against
Python 3.14 and Home Assistant 2026.
