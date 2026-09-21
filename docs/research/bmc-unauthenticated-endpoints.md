# BMC Redfish endpoints reachable without authentication

**Author:** an operator SRE · **Date:** 2026-08-17 · verified live against every distinct BMC vendor in the contributing operator's fleet.
Reproduced here from the original note (Slack, `bmc-unauthenticated-endpoints.md`, 2026-08-20) with identifying BMC addresses removed.

| BMC vendor | Server(s) probed |
|---|---|
| Supermicro (own BMC) | B1-01 (HGX B200), B5-11 (HGX A100) |
| Dell iDRAC9 | B2-01 XE9680 (H100) |
| Lenovo XCC | B3-02 SR680a V3 (H200) |
| AMI MegaRAC | B4-01 (MSI S337), B5-09 (Gigabyte G493), MSI Pro 6000 |
| Insyde (JBOF) | Supermicro flash trays |

The accessible-without-auth set is defined by the DMTF Redfish spec (the resources a service must expose before a session exists). Vendors differ only in how much of the optional schema/registry surface they leave open — telemetry, inventory, and identity are locked on all of them.

## Reachable without auth (HTTP 200 on every brand)

| Endpoint | What it returns | Useful for |
|---|---|---|
| `/redfish` | Redirect stub to `/redfish/v1/` | Confirming a Redfish service exists |
| `/redfish/v1/` | Service root — `Vendor`, `RedfishVersion`, `UUID`, `ServiceIdentification`, `ProtocolFeaturesSupported`, and the set of top-level services present | Liveness + vendor/capability fingerprint before spending a credential |
| `/redfish/v1/odata` | OData service document | Machine-readable capability discovery |
| `/redfish/v1/$metadata` | CSDL schema catalog | Tooling / schema introspection |

## Requires auth (HTTP 401) — every brand

`Managers`, `Systems`, `Chassis`, `SessionService` (the object itself), `AccountService`, `TelemetryService/*`, `LicenseService`, `ComponentIntegrity`, `Fabrics`, `UpdateService`, `EventService`, `TaskService`, `CertificateService`, `CompositionService` (AMI), `JobService` (Dell/Lenovo/some AMI). `JsonSchemas`/`Registries` are open on Supermicro and the JBOF, `JsonSchemas` only on Dell, locked on Lenovo and AMI. JBOF exception: `TelemetryService` collection lists two report names unauthenticated, but the reports are empty. **No BMC telemetry is reachable without authentication anywhere in the fleet.**

## Per-vendor capability fingerprint (from the unauthenticated service root)

| Field | Supermicro | Dell | Lenovo | AMI | JBOF (Insyde) |
|---|---|---|---|---|---|
| `Vendor` | Supermicro | Dell | Lenovo | AMI | *(null)* |
| `Product` | *(null)* | Integrated Dell Remote Access Controller | *(null)* | AMI Redfish Server | *(null)* |
| `OEM` namespace | Supermicro | Dell | *(none)* | Ami | Supermicro |
| `RedfishVersion` | 1.22.2 | 1.20.1 | 1.22.0 | 1.15.1 | 1.11.0 |
| `ServiceIdentification` (service tag) | ✅ serial | ✅ serial | *(empty)* | *(null)* | *(null)* |
| **`$expand` MaxLevels** | **3** | **1** | **2** | **5** | **2** |
| `FilterQuery` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Advertises `ComponentIntegrity` | ✅ | ✅ | ✗ | ✅ (no HGX behind it) | ✗ |
| Advertises `Fabrics` | ✅ | ✅ | ✗ | ✅ (no HGX behind it) | ✗ |
| Advertises `LicenseService` | ✅ | ✅ | ✅ | ✗ | ✗ |

Notes:
- **Dell's `$expand` MaxLevels is 1** — you cannot deep-expand an iDRAC in a single GET, so GPU data must be walked one resource at a time. This is the mechanical reason the Dell collector path is 4× slower per node than Supermicro (measured p50 6.7 s vs 1.8 s, 2026-09-20).
- **OEM namespace is the most reliable fingerprint.** The JBOF reports `Vendor: null` but `OEM: Supermicro` and a Supermicro-OUI UUID.
- **Service tag leaks pre-auth** on Supermicro and Dell via `ServiceIdentification` — the one identifying field available without a credential; it is what the reference collector's identity check uses to confirm the machine at an address is the one the credential belongs to.
- **Service-root links are hints, not proof.** AMI MegaRAC roots advertise `ComponentIntegrity` and `Fabrics` on 4-GPU PCIe boxes with no HGX tray. Only an authenticated `MetricReports` listing (or the accelerator `Manager`) is a real capability test (the reference collector operator requirements R-OOB-17).

## HGX (NVIDIA HMC) endpoints — all require auth

`Managers/HGX_BMC_0`, `Managers/HGX_FabricManager_0`, `Systems/HGX_Baseboard_0`, `TelemetryService/MetricReports/HGX_*` — 401 unauthenticated on Supermicro HGX B200.

## Fleet sweep (Site B, 2026-08-21)

259 BMC-plane addresses probed GET-only: 121 answered Redfish; 121 of 121 carried a unique identifier with no login (110 non-empty UUIDs with zero collisions, 11 Dell with service tags); 0 identifier collisions. The 138 non-Redfish addresses were 59 Server Technology PDUs, 35 Arista switches, 2 Fortinet firewalls and offline BMCs. PDUs, switches and firewalls expose only device-class information unauthenticated; their identity vector is SNMP, not Redfish.
