# Recommendation — the optimal Redfish out-of-band profile for neoclouds, and how to land it in OCP

**Date:** 2026-09-20 · **Status:** draft for the OCP FTI "Scaling AI Clusters at Neoclouds" workstream (next call 2026-09-21) and the OCP Hardware Management Profiles workstream · **Contact:** OCP FTI Scaling AI Clusters at Neoclouds workstream

## The recommendation in five sentences

1. Publish the neocloud requirement as a **three-file Redfish Interoperability Profile family** — ServiceCore, Platform, Accelerator — composing the approved OCP Service Baseline, Baseline Hardware Management and Server profiles plus the System GPU Management workstream's `OCP_UBB_BaselineManagement` 2.0.0, with two levels (Neocloud-Core = Mandatory, Neocloud-Trusted = Recommended).
2. Set the Core floor **empirically**: Platform passes on every BMC vendor measured; Accelerator Core passes where the NVIDIA HMC surface is aggregated by the host BMC (Supermicro), fails on Dell iDRAC9 (no HBM ECC, no Ports) and Lenovo XCC (no accelerator surface) — and those two fails are the deliverable, not a defect of the profile.
3. Make **accelerator-subsystem liveness** a first-class conformance item (subordinate `Manager.Status.State`), because two detached HGX trays in six weeks were invisible to every other monitoring path.
4. Take the `Oem.Nvidia` counters the fleet actually alerts on — HBM row remapping, NVLink link-down/BER/symbol errors, throttle reasons, stale-value flags — to DMTF as schema proposals, and XID/SXID to the OCP `AcceleratorFabric`/`OCPAcceleratorRAS` registries with Redfish 2026.2's `VendorCode` as the carrier.
5. Ship it through the OCP Hardware Management project's Profiles workstream with System GPU Management as co-reviewer, using the FTI workstream as sponsor, with CI that runs the DMTF Interop Validator against recorded BMC trees so every requirement stays tied to evidence.

## Why this shape (what changed since the v0.5.0 draft)

The v0.5.0 draft (Aug 2026) reasoned from the standards. Since then the collector it described shipped
(`the reference exporter` 1.0.0) and has run continuously against 153 BMCs at two sites, and two
BMC trees were recorded as test fixtures. That changed the design in four ways:

| Evidence | Design consequence |
|---|---|
| Supermicro aggregates the HMC (12 bulk reports, `ProcessorMetrics` 14/15 standard paths, HBM `LifeTime` ECC); Dell models GPUs itself with `Oem.Dell`/`Oem.Nvidia` and no HBM ECC; Lenovo exposes GPU temp/power only | Split the GPU tier from the host tier; scope accelerator requirements with `UseCases` on `ProcessorType`; keep HBM ECC Mandatory so the Dell/Lenovo gaps are legible |
| A1-69 (Aug, 9 days) and A1-17 (Sep 18, caught in 5 min): tray gone, BMC healthy | `Manager.Status.State` semantics + `FirmwareInventory` census requirement + `AcceleratorSubsystemUnavailable` message |
| `$expand` MaxLevels 1 (Dell) vs 3 (Supermicro) = 6.7 s vs 1.7 s per node | `ProtocolFeaturesSupported.ExpandQuery.MaxLevels` Mandatory with ≥2 guidance; bulk reports as the alternative |
| Firmware band changes member counts (25 vs 34); PSU bays report `Absent`; `LinkStatus` reads `"OK"`; `CurrentPeriod`/`HealthData` exist nowhere | Demote un-implementable items, add Absent-bay semantics, forbid hardcoded counts, note the enum drift as a vendor item |

Full detail: `PROFILES.md` (what changed and why), `gap-analysis.md` (rev 2), `evidence/`.

## What we measured (2026-09-20)

| Site / fleet | Platform | BMCs | OOB coverage | Series/node | Probe p50 |
|---|---|---:|---|---:|---|
| Site A fleet A1 | Supermicro HGX B200 | 128 | 128/128 BMC, 127/128 HMC, 10 days continuous | 996 | 1.7 s |
| Site B fleet B1 | Supermicro HGX B200 | 15 | 15/15, 14 days | 1,062 | 1.8 s |
| Site B fleet B2 | Dell XE9680 H100, iDRAC9 7.20 | 10 | 10/10 platform, no HMC by design | 432 | 6.7 s |

Live hardware state the profile's Mandatory set surfaced on 2026-09-20, all with no host agent: 1 HGX tray
detached (host off, 0/34 accelerator components), 13 dead power supplies on 11 nodes (8 in one rack →
feed problem), 9 GPUs at 0 PCIe lanes on 2 nodes (bus drop, still `Enabled/OK`), 2 GPUs with no HBM
remap capacity left (RMA candidates), 1 GPU with lifetime uncorrectable HBM ECC, NVSwitch link-down
counters to 978, 3 HMC firmware bands mid-rollout. Zero probe errors. Details: `evidence/live-evidence-2026-09-20.md`.

Validator (DMTF Redfish-Interop-Validator 3.0.0) against the recorded trees, composed profile tree,
`--nooemcheck`: Platform on Dell 675 pass / 40 fail / 78 not tested, on Supermicro 48 / 25 / 26;
Accelerator on Dell 7,107 / 93 / 98 (15 property-level fails, 8 of them UBB 2.0.0 items), on Supermicro 54 / 47 / 22. Property-level fails on recorded resources are few and real
(Dell: `MultipleHTTPRequests`, `UUID`, `Chassis.Controls`, `Intake` thermal context, serial-console
types, `LogServices` link on the GPU system; Supermicro: `MultipleHTTPRequests`); the rest are
resources the recording never fetched. Details: `evidence/recorded-tree-evidence.md`.

## The profile family

```
OCPNeocloudAccelerator 0.6.0  ── requires ──►  OCPNeocloudServiceCore 0.6.0  ── requires ──►  OCPServiceBaseline 1.0.0
        │                                              ▲                                          OCPBaselineHardwareManagement 1.1.0
        └── requires ──►  OCP_UBB_BaselineManagement 2.0.0                                        OCPServerHardwareManagement 1.0.0
OCPNeocloudPlatform 0.6.0     ── requires ──►  OCPNeocloudServiceCore 0.6.0
```

| Profile | Neocloud-Core (Mandatory) highlights | Neocloud-Trusted (Recommended) highlights |
|---|---|---|
| **ServiceCore** | pre-auth identity (`ServiceIdentification`/UUID), `ProtocolFeaturesSupported` incl. expand depth, `Manager.Status.State` for subordinate controllers, `FirmwareInventory` enumerating every accelerator component, `MultipartHttpPushUri`, `EventService` subscriptions, RBAC with a `ReadOnly` role, audit `LogService`, `LogEntry.MessageId` | SSE + `includeoriginofcondition`, `VendorCode`/CPER on log entries, `Status.Conditions`, `ComponentIntegrity` (SPDM), `SecureBoot`, `OutboundConnection`, MFA/OAuth2, `LicenseService`, `AggregationService` |
| **Platform** | `ComputerSystem.PowerState`/Status, chassis power with `PowerSupply.Status.State=Absent` semantics and input/output watts, thermal/fans, `Drive.FailurePredicted`, DIMM/CPU health, `Storage`, containment links for power scope | `EnvironmentMetrics` energy, `Sensor` thresholds, NVMe SMART where the BMC has it |
| **Accelerator** (UseCase: `ProcessorType` GPU/Accelerator) | `ProcessorMetrics` (`BandwidthPercent`, `OperatingSpeedMHz`, `PCIeErrors` correctable/non-fatal/fatal, `PCIeInterface.LanesInUse/MaxLanes`), HBM `MemoryMetrics.LifeTime` ECC, `EnvironmentMetrics` temp/power, `Port.LinkStatus`/speed/`Metrics`, `PortMetrics` bytes + `RXErrors`, accelerator `Manager`, conditional `TelemetryService` content | throttle durations, cache ECC, `CurrentPeriod`/`HealthData`, `Status.Conditions`, `Switch`/`Fabric`, `Triggers`, `MetricReport` per-value timestamps, RAS registry MessageIds |

## Alignment plan (who, where, when)

| Step | Owner | When |
|---|---|---|
| Present v0.6.0 + evidence at the FTI neocloud workstream; ask Denvr, Scaleway, Lambda, Crusoe to run the validator against one HGX unit per OEM they operate and file fails as issues | JM | 2026-09-21 call |
| Open a tracking issue in `HWMgmt-OCP-Profiles` ("Neocloud profile family, evidence-based") and file the 5 upstream defects found while validating (`1,0,0` version string; UBB 2.0.0 `IfImplement`/`HTTP??`; Server 1.0.0 `Intake`/serial-console assumptions; README DSP0272 pointer; System GPU spec stale UBB link) | JM | this week |
| Ask System GPU Management (John Leung) to co-review `OCPNeocloudAccelerator`, fold `OCPAcceleratorRAS` messages into their registry work (their issue #56), and track the UBB→MAS rename | JM + Jeff Autor (Vertiv, action from 2026-06-08 call) | Sep–Oct |
| Vendor asks: Dell — HBM ECC and `Ports` over Redfish on iDRAC9 (iDRAC10 GPU Statistics report suggests it exists); Lenovo — HMC aggregation on SR680a V3; NVIDIA — `LinkStatus` enum, HMC `Manager.Status.State` on tray loss, standardize `MetricValueStale`; Supermicro — `Status.Conditions`, `MultipleHTTPRequests` | via HM Profiles call + OEM account teams | Q4 |
| DMTF schema proposals (row remap, scale-up link counters, throttle reasons, stale flag) through the HM Profiles workstream where DMTF co-authors | JM + Mike Raineri (DMTF) | OCP Global Summit, Oct 12–15 |
| Usage Guide in the OCP markdown template; request promotion of the family once two machines per OEM validate | workstream | after summit |

## Gaps this pass adds beyond v0.5.0 (see `gap-analysis.md` §0–3 and `dmtf-proposals.md`)

Accelerator-subsystem liveness as standard state · read-only role verified at the role · pre-auth
identity for credential binding · `$expand`/bulk-telemetry as fleet-scale cost · firmware-band-aware
norms · Absent-vs-failed semantics (PSU bays, devices off the bus) · `VendorCode`/CPER as the XID
carrier · accelerator-controller time sync · facility Redfish (PDUs) as a procurement item · JBOF
unauthenticated telemetry leak as a security conformance test outside RIP.

## What is out of scope and said so

Host OS metrics, container/job attribution, NCCL, the InfiniBand subnet manager, rack-scale NVLink
(NMX-C/GFM), and every ClusterMAX item that is a business process. Rack power/cooling (`OCPRackPDU`,
`OCPLiquidCoolingBaseline`) composes later for NVL72 — the June workstream action to add PDU/thermal
requirements is deferred to a `OCPNeocloudRack` profile once a Redfish-speaking PDU is in the fleet
to record.
