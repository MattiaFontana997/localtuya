# Changelog

## 6.4.0 — 2026-09-06

Comprehensive catalog-driven runtime and Tuya Local compatibility release.
LocalTuya 6.4.0 expands the Community Device Catalog from the V2 foundation
introduced in 6.3.0 to a much broader runtime surface, adds safe multi-DP and
advanced mapping support, and introduces fail-closed exact-DPS fingerprints for
profiles that do not expose a Tuya Product ID.

### Catalog-driven Home Assistant platforms

Added catalog/runtime support for:

- Button
- Text
- Valve
- Humidifier
- Lock
- Time
- Water heater
- Siren
- Alarm control panel
- Event
- Camera
- Datetime
- Lawn mower
- Remote
- Infrared

The new platform handlers preserve manual configuration compatibility and only
activate catalog-specific semantics when those semantics are explicitly present
in a trusted mapping.

### Advanced mappings and multi-DP runtime

- Added a safe declarative advanced-mapping grammar with no executable
  templates, callbacks or expressions
- Added support for `dps_val` / `value`, scaling, inversion, step/range
  transforms, target ranges, constraints, conditions, value redirection,
  hidden/invalid values and defaults
- Added referenced-DP registration and validation
- Added optional-DP pruning for mappings whose optional dependencies are not
  present on a firmware variant
- Added grouped multi-DP writes through `set_dps` when one logical operation
  must update multiple datapoints
- Preserved unconsumed compatible Tuya Local DPS as raw entity attributes rather
  than silently discarding them

### Catalog V3 productless fingerprints

- Added Catalog Schema V3 support while preserving V1 and V2 compatibility
- Added fail-closed `exact_dps` fingerprints for profiles without Product IDs
- Product-ID mappings always remain authoritative and are never replaced by a
  productless fingerprint fallback
- Productless fingerprints require every required DP to be observed
- Any observed LAN DP outside the declared required/optional set rejects the
  fingerprint
- More-specific valid fingerprints are preferred
- Equal-best fingerprint matches are rejected as ambiguous instead of guessed
- Productless mappings cannot be marked `verified`
- Imported productless mappings remain `experimental` until reviewed

The Community Device Catalog already publishes the first conservatively
filtered set of unambiguous V3 productless fingerprints. Catalog updates can be
published independently of LocalTuya releases.

### Lights

- Added independent raw brightness ranges for white brightness and HSV value
  data
- Added catalog-provided custom scene mappings through `scene_values`
- Added dedicated effect DP support through `effect` and `effect_values`
- Added dedicated-effect precedence matching Tuya Local behavior
- Added deterministic support for the legacy extended RGB+HSV payload format
  `RRGGBBHHHHSSVV`
- Added dedicated RGBW white mode support for lights that use a standalone
  white channel without a color-temperature DP

### Events and camera safety

- Event entities are driven by unsolicited raw Tuya STATUS updates so repeated
  identical event pushes are preserved
- Camera catalog support is limited to locally supplied snapshot values
- Remote URL fetching is deliberately not performed by the camera runtime

### Community contributions

- Kept contribution export privacy guarantees unchanged
- Local Key, Device ID, IP address, Tuya Cloud credentials and user-defined
  friendly names remain excluded from contribution payloads
- Nothing is uploaded automatically
- The contribution call to action remains exactly `Submit to Community Catalog`

### Compatibility and safety

- Existing configurations remain backward compatible
- Catalog V1 and V2 mappings remain supported alongside V3
- Unsupported Tuya Local semantics continue to fail closed rather than being
  approximated
- Special remote-code lock protocols are not emulated when their semantics
  cannot be represented safely
- Optional firmware capabilities are pruned instead of creating broken entities

### Validation

- LocalTuya regression tests pass on the final 6.4.0 runtime baseline
- HACS validation passes
- Catalog mapping validation covers advanced mapping DP references, optional-DP
  pruning and V3 fingerprint constraints


## 6.3.0

Device Catalog V2 compatibility release.

### Community device catalog

- Added backward-compatible Catalog Schema V1 + V2 runtime support
- Added multiple product-ID aliases per mapping
- Added required vs optional DP matching
- Added optional capability and entity pruning for firmware variants
- Added source and license provenance metadata support
- Updated `Submit to Community Catalog` exports to Catalog Schema V2
- Kept bundled and remote catalog resolution backward compatible

### Switches

- Added standard Home Assistant switch device-class support
- Added defensive handling for invalid configured switch device classes


## 6.2.0

Feature release adding stable Tuya protocol 3.5 support and refreshing the
product-specific device catalog.

### Tuya protocol 3.5

- Added 6699 AES-GCM framing and authenticated payload handling
- Added Tuya 3.5 session-key negotiation
- Added Tuya 3.5 protocol selection and automatic protocol detection
- Added support for Tuya 3.5 global response sequence numbers
- Hardened protocol probe and malformed-frame error handling
- Preserved legacy Tuya 3.1, 3.2, 3.3 and 3.4 compatibility

Tuya 3.5 was physically validated on real hardware for discovery,
configuration, bidirectional state updates, power, brightness, color
temperature and color control.

### Device state handling

- Keep LocalTuya DPS caches synchronized after multi-DP writes
- Fixed stale state after partial Tuya status updates

### Lights

- Added mapping support for compatible string/raw `colour_data_v2` and
  `color_data_v2` datapoints
- Structured JSON color data remains excluded from encoded-string handling

### Community device catalog

The bundled offline snapshot now contains two physically verified
product-specific mappings:

- LSC Smart Connect RGB+CCT smart light sold by Action
- EMOS GoSmart P56201 Wi-Fi Room Thermostat

The remote catalog remains independently refreshable between LocalTuya
releases.

### Documentation

- Updated README for Tuya 3.5 and the community catalog
- Documented contribution and promotion lifecycle
- Updated HACS information and verified device examples

### Tests

- Expanded automated protocol and catalog regression coverage
- Physical validation completed for Tuya 3.5, 3.4 and 3.3 devices


## 6.1.1

Stability hotfix for catalog loading and Tuya LAN discovery.

- Moved bundled catalog file loading off the Home Assistant event loop
- Removed the blocking catalog I/O warning during integration setup
- Added active Tuya device-information discovery over UDP port 7000
- Added Home Assistant `network` dependency for adapter-aware broadcast
  discovery
- Fixed discovery of devices that listen on the LAN but do not advertise
  passively


## 6.1.0

Community catalog and mapping workflow release.

- Added remote community device catalog support
- Added persistent catalog cache
- Added bundled offline catalog snapshot
- Added unified generic/catalog mapping resolver
- Added mapping review workflow
- Added privacy-safe mapping export
- Added `Prepare community contribution` configuration flow
- Added `localtuya.export_device_mapping`
- Added `localtuya.refresh_device_catalog`
- Expanded generic climate mapping
- Hardened diagnostics redaction
- Expanded translations, tests and catalog tooling


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
