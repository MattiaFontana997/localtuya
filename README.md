# LocalTuya

![LocalTuya](img/logo-small.png)

Local control of Tuya devices in Home Assistant, with a modern onboarding flow and a community-driven device catalog.

This repository is a maintained modernization fork of the original [LocalTuya project](https://github.com/rospogrigio/localtuya), focused on current Home Assistant releases, safer Tuya protocol handling, easier device setup and predictable local-first behavior.

## In development: 6.7.0 Reliability & Repair

The `develop` branch is building a reliability layer around LocalTuya's existing LAN-first runtime. It is not a stable release yet.

Current development highlights:

- Structured, privacy-safe LAN/protocol/datapoint health checks
- **Check device health** from the LocalTuya options flow
- `localtuya.check_device_health` admin service with response data suitable for diagnostics
- Active rediscovery before reconnecting offline devices
- Automatic host recovery when a device receives a new DHCP address; a discovered address is never persisted until the existing LocalTuya credentials validate it over the LAN
- Home Assistant **Repairs** issues when a discovered replacement host cannot be validated
- Interactive Repairs flow with automatic rediscovery or a manually supplied host, both validated before save
- Gateway-aware host recovery: when a BLE/Zigbee gateway changes IP, configured child devices can inherit the new gateway transport address after child-level validation
- Gateway child recoveries are serialized per gateway instead of opening a recovery connection for every child simultaneously
- Tuya 3.5 query compatibility fallback and hardened handling of devices that reply with `data unvalid`
- Diagnostics and repair reports exclude local keys, device IDs, IP addresses, QR authorization material, exception messages and raw datapoint values

`master` remains the stable line until the 6.7.0 work is completed and validated.

## What's new in 6.6.0

LocalTuya 6.6.0 introduces the recommended **Smart Life / Tuya QR onboarding flow**.

You no longer need to create a Tuya Developer Platform project, enable a Data Center, or manually copy a Client ID / Client Secret for the standard setup path.

The recommended flow is now:

`Install LocalTuya → User Code → scan QR → choose device → LocalTuya validates it on the LAN → done`

Highlights:

- Recommended **User Code + QR login** with Smart Life / Tuya
- No Tuya Developer Platform required for normal onboarding
- Automatic retrieval of Device ID, `local_key`, Product ID and provisioning metadata
- LAN discovery first, with a validated IP / hostname fallback when UDP discovery is unavailable
- Automatic protocol detection and datapoint discovery before a device is saved
- Catalog-first automatic entity mapping
- Normal device control remains **LAN-only** after provisioning
- Existing manual Device ID + `local_key` setup remains available
- Existing configurations can link a Tuya account by QR without recreating configured devices

**Step-by-step guide:** [Smart Life / Tuya QR setup](docs/QR_SETUP_GUIDE.md)

![LocalTuya QR onboarding](docs/images/qr-setup/01-localtuya-qr-choice.png)

## Local-first design

LocalTuya controls configured devices directly over the local network.

The Smart Life / Tuya account link introduced in 6.6.0 is used for **provisioning only**: it obtains the device credentials and metadata needed to create a local configuration. After onboarding, normal device control does not require Tuya Cloud polling.

A device is not saved merely because it appears in the Tuya account. LocalTuya must successfully:

1. Resolve or receive a LAN address.
2. Authenticate to the selected device with its Device ID and `local_key`.
3. Detect a compatible Tuya protocol.
4. Read the device datapoints.
5. Resolve a safe entity mapping or let the user review/configure one.

If those checks fail, the device is not partially saved.

Gateway-backed BLE/Zigbee children keep their own Tuya Device ID and `node_id`/`cid`, while their local transport uses the parent gateway IP and local key. The gateway address is still validated before it is accepted.

## Requirements

Current development and CI target:

- Home Assistant **2026.9 or newer**
- Python **3.14**
- Tuya LAN protocols **3.1, 3.2, 3.3, 3.4 and 3.5**
- Local push updates

## Supported platforms

LocalTuya supports a broad range of Home Assistant platforms, including:

- Switch
- Light
- Cover
- Fan
- Climate
- Vacuum
- Sensor
- Binary sensor
- Number
- Select
- Button
- Text
- Valve
- Humidifier
- Lock
- Time / Datetime
- Water heater
- Siren
- Alarm control panel
- Event
- Camera
- Lawn mower
- Remote / infrared catalog mappings where the local semantics are safely representable

Energy monitoring such as voltage, current and power is supported on compatible devices.

## Installation with HACS

This fork must be added as a **custom HACS repository**.

1. Open **HACS**.
2. Open **Integrations**.
3. Open the menu and choose **Custom repositories**.
4. Add:

   `https://github.com/MattiaFontana997/localtuya`

5. Select **Integration** as the repository type.
6. Install **LocalTuya**.
7. Restart Home Assistant.

> Do not install this fork and the upstream LocalTuya integration at the same time. Both use the `localtuya` integration domain.

## Recommended setup: Smart Life / Tuya QR

After installing LocalTuya:

1. Open **Settings → Devices & services** in Home Assistant.
2. Add **LocalTuya**.
3. Choose **QR login with Smart Life / Tuya**.
4. In the Smart Life or Tuya mobile app, locate your account **User Code**.
5. Enter the User Code in Home Assistant.
6. Scan the QR code shown by LocalTuya with the Smart Life / Tuya app and approve the authorization.
7. Choose the device you want to add.
8. LocalTuya tries to discover the device on the LAN and validates its local credentials, protocol and datapoints.
9. Review any suggested mappings if Home Assistant asks you to do so.
10. Finish setup.

For the full illustrated walkthrough, troubleshooting and the flow for adding more devices later, see:

**[Smart Life / Tuya QR setup guide](docs/QR_SETUP_GUIDE.md)**

### Adding more devices later

While the saved Tuya authorization is still valid, you normally do **not** need to scan another QR code.

Open the LocalTuya integration options, choose **Add a new device**, then select the Smart Life / Tuya provisioning path. LocalTuya refreshes the linked account and shows eligible devices that are not already configured.

### Existing LocalTuya installation

You do not need to remove your existing LocalTuya entry or recreate devices.

Open the integration options and choose:

**Link Smart Life / Tuya account by QR**

Existing LAN devices and mappings are preserved. If the entry previously used the legacy Tuya Developer Platform cloud configuration, explicitly linking the account by QR migrates that entry to the provisioning-only model and disables normal cloud runtime use.

## Manual setup

Advanced users can still choose **Manual device setup** and provide:

- Device name
- IP address / hostname
- Device ID
- `local_key`
- Protocol version, or automatic probing where available

The manual path remains useful for offline setups, imported credentials, unusual networks and devices that are not eligible for QR provisioning.

LocalTuya also supports importing existing LocalTuya / Tuya JSON containing Device ID and `local_key` data. Imported credentials are validated over the LAN before they are saved.

## LAN discovery and IP fallback

LocalTuya prefers Tuya UDP discovery because it can resolve the current device address and confirm its advertised identity.

Some networks do not pass discovery broadcasts correctly, especially setups involving:

- VLANs
- Docker or container networking
- restrictive Wi-Fi access points
- unusual multicast / broadcast handling

If automatic discovery cannot determine a usable address, the QR flow can ask for the current device IP address or hostname.

This is **not** a trust bypass: the address is accepted only if LocalTuya can authenticate to the selected device locally and successfully read its datapoints.

## Device health, recovery and Repairs

On the 6.7 development line, LocalTuya uses the same bounded LAN preflight for onboarding, manual health checks and repair validation.

From the LocalTuya integration options, **Check device health** reports the useful stage reached by the device — LAN, protocol, datapoints or ready — without exposing the host, Device ID, `local_key` or raw datapoint values.

For administrative troubleshooting, `localtuya.check_device_health` returns the same privacy-safe structured snapshot.

When an already configured device is rediscovered at a different address, LocalTuya first authenticates against the candidate address with the existing credentials. Only a successful protocol/datapoint validation can update the stored host. If validation fails, the previous host remains untouched and Home Assistant can create a fixable **Repair** issue.

The Repair flow offers:

- automatic rediscovery and validation
- manual IP/hostname entry followed by the same validation path

A failed candidate is never persisted merely because it appeared in a UDP discovery packet.

For gateway-backed children, discovery of the parent gateway can recover the transport host for all configured children. Child identities and Product IDs remain unchanged, and child validation is performed sequentially to avoid unnecessarily exhausting gateway connection limits.

## Automatic mapping

LocalTuya combines observed LAN datapoints with safe metadata and the Community Device Catalog.

Mapping behavior is confidence-based:

- **High confidence** mappings can be included automatically.
- **Medium confidence** mappings are shown for review.
- Ambiguous or unsafe mappings are not guessed.

Product-specific catalog mappings are authoritative when their Product ID / fingerprint and observed datapoints match the device requirements. Generic mapping fills capabilities that can be inferred safely.

Manual entity configuration remains available.

## Community Device Catalog

LocalTuya uses a community-maintained catalog for product-specific mappings that cannot be inferred reliably from generic Tuya metadata alone.

Catalog matching can use:

- Tuya Product ID
- Tuya category
- datapoints observed from the real device over the LAN
- conservative exact-DP fingerprints for eligible devices without Product ID

LocalTuya uses:

- the remote community catalog for current mappings
- a persistent local cache
- a bundled `builtin_catalog.json` snapshot as an offline fallback

Catalog confidence levels:

`experimental → community → verified`

Verified mappings are additionally validated on real hardware.

Device catalog repository:

`https://github.com/MattiaFontana997/localtuya-device-catalog`

## Submit a device mapping

After configuring and testing a device, open LocalTuya options and choose the community contribution flow.

The final call to action is:

**Submit to Community Catalog**

LocalTuya prepares a privacy-safe mapping contribution. It does **not** automatically upload the contribution.

The export excludes sensitive/user-specific data such as:

- `local_key`
- Tuya Device ID
- IP address
- Tuya account authorization
- legacy Tuya Cloud credentials
- user-defined friendly names

LocalTuya also exposes:

- `localtuya.export_device_mapping`
- `localtuya.refresh_device_catalog`
- `localtuya.check_device_health`

## Privacy and diagnostics

LocalTuya redacts device secrets and QR authorization material from diagnostics.

Health and Repair results are designed to remain privacy-safe: they can report protocol attempts, failure categories and observed datapoint IDs/counts, but not local keys, device IDs, IP addresses, QR authorization material, exception messages or raw datapoint values.

QR access/refresh tokens and device `local_key` values must not be copied into issues, screenshots or logs posted publicly.

Disconnecting the linked Smart Life / Tuya account removes the provisioning authorization while preserving already configured LAN devices.

## Troubleshooting

### Device appears in Smart Life / Tuya but LocalTuya cannot find it on the LAN

Confirm that Home Assistant can reach the device network directly. If discovery is blocked but direct LAN communication works, use the IP / hostname fallback when offered.

### Device IP changed

On the 6.7 development line, LocalTuya actively rediscovers offline devices and can validate a replacement host before saving it. If automatic validation fails, open the Home Assistant Repair issue and choose automatic rediscovery or enter the current IP/hostname manually.

A DHCP reservation is still recommended where practical because stable addresses reduce reconnect latency and network ambiguity.

### Device cannot be authenticated

A reachable IP is not enough. The Device ID / `local_key` pair must match the device. Re-link or reprovision if the Tuya credentials changed. On Tuya 3.5 devices, LocalTuya also handles the known query-shape case where the device establishes a LAN session but initially responds with `data unvalid`.

### Hub child device is not shown / cannot be added

The QR onboarding path supports gateway-backed children when Tuya exposes the child `node_id`/`cid`, parent gateway identity and usable gateway transport credentials. The child keeps its own Device ID while LocalTuya connects through the parent gateway IP/local key.

If a child still does not appear, collect the LocalTuya diagnostics/logs for the provisioning step without posting account tokens or local keys. Some device families expose different relationship metadata and may need an additional compatibility mapping.

### QR authorization expired

Open LocalTuya options and choose **Link Smart Life / Tuya account by QR** again.

## Manual installation

Copy:

`custom_components/localtuya`

into:

`/config/custom_components/localtuya`

and restart Home Assistant.

## Upgrading

Before upgrading a production Home Assistant instance, create a backup.

Existing LocalTuya config entries are intended to be retained across 6.x upgrades. Version 6.6.0 does not require existing users to delete their integration and start over.

## Reliability and testing

The modernization fork includes regression coverage for areas such as:

- Tuya protocol framing and authentication
- Tuya 3.1 through 3.5 payload handling
- Tuya 3.4 / 3.5 session-key negotiation
- Tuya 3.5 query compatibility and error handling
- passive and active LAN discovery
- 55AA and 6699 discovery frames
- validated host recovery after DHCP address changes
- Home Assistant Repairs and privacy-safe device-health reporting
- gateway child onboarding, routing and gateway-host recovery
- config-entry migration and lifecycle
- QR account linking and provisioning
- LAN validation before save
- automatic and catalog mapping
- advanced / multi-DP mappings
- diagnostics secret redaction

CI runs against current Home Assistant / Python targets and includes HACS/Hassfest validation.

## Documentation

- [Smart Life / Tuya QR setup guide](docs/QR_SETUP_GUIDE.md)
- [QR onboarding architecture and safety model](docs/QR_ONBOARDING.md)
- [QR onboarding test plan](docs/QR_ONBOARDING_TEST_PLAN.md)
- [Community Device Catalog](https://github.com/MattiaFontana997/localtuya-device-catalog)

## Credits

This fork builds on the work of the original LocalTuya maintainers and contributors.

Original project:

`https://github.com/rospogrigio/localtuya`

The modernization work in this fork includes current Home Assistant compatibility, Tuya 3.5 support, QR provisioning, discovery/protocol hardening, catalog-driven mappings and expanded regression testing.
