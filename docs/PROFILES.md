# The profile family — composition, levels, validation

## Composition

```
OCPNeocloudAccelerator.v0_6_0      accelerator tier (UseCase-scoped to ProcessorType GPU/Accelerator)
   requires: OCPNeocloudServiceCore 0.6.0
             OCP_UBB_BaselineManagement 2.0.0   [ocp-hm-system-gpu-management; UBB -> "MAS" rename pending]

OCPNeocloudPlatform.v0_6_0         host tier (any Redfish BMC in a GPU fleet)
   requires: OCPNeocloudServiceCore 0.6.0

OCPNeocloudServiceCore.v0_6_0      service plane
   requires: OCPServiceBaseline 1.0.0                [approved, HWMgmt-OCP-Profiles root]
             OCPBaselineHardwareManagement 1.1.0     [approved]
             OCPServerHardwareManagement 1.0.0       [approved; 1.1.0 is in Server/ awaiting promotion]
```

A GPU node is expected to conform to **Platform + Accelerator** (which transitively includes
ServiceCore and the four upstream profiles). A non-accelerator node (storage tray, CPU node) conforms
to **Platform** alone. The validator merges required profiles and applies the most restrictive
requirement per property, so one run tests the whole tree.

Why three files rather than one: the fleet shows the two surfaces fail independently. Supermicro's
BMC passes the accelerator tier and fails a handful of service items; Dell's iDRAC passes the service
and platform tiers and fails the accelerator tier on HBM ECC and Ports; Lenovo's XCC passes platform
and has no accelerator surface at all. Separate files make each vendor's gap legible instead of one
red "fail".

## Two conformance levels, expressed by ReadRequirement

| Level | ReadRequirement | Meaning | Who passes today (evidence) |
|---|---|---|---|
| **Neocloud-Core** | `Mandatory` | The floor for onboarding a fleet for agentless health. Direct-GET telemetry only, no telemetry license needed, no writes. | Platform: Supermicro, Dell, Lenovo. Accelerator: Supermicro HGX (NVIDIA HMC surface). Dell fails Accelerator on `MemoryMetrics.LifeTime` (no HBM ECC over Redfish) and `Processor.Ports`. |
| **Neocloud-Trusted** | `Recommended` | What an operator asks for contractually: streaming telemetry, SPDM attestation, SecureBoot, audit log with actor identity, outbound connections, `VendorCode`/CPER on log entries, `Status.Conditions`, expand depth >= 2. | Partially: Supermicro (ComponentIntegrity, SSE, excerpt/select); Dell (TelemetryService streaming once enabled). No BMC in the fleet populates `Status.Conditions`. |

`IfImplemented` marks a resource whose presence is platform- or license-dependent (TelemetryService,
Fabric, Switch, PowerSubsystem vs legacy Power); when present, its listed content is required.

## What changed from v0.5.0 (and why)

| Change | Evidence |
|---|---|
| Split GPU requirements out of a monolithic "GPUServer" into **Platform + Accelerator**; scope accelerator requirements with `UseCases` on `ProcessorType` | Validator applied GPU requirements to CPU sockets and failed them (`CPU.Socket.1`: 3 fails) [rec] |
| Require `OCP_UBB_BaselineManagement` **2.0.0** from the System GPU Management repo instead of 1.0.0 from HWMgmt-OCP-Profiles | Profile moved (PR #175, 2026-08); 2.0.0 replaced deprecated `HttpPushUriOptions` with `MultipartHttpPushUri` (closes v0.5.0 open item 1) |
| `MemoryMetrics.CurrentPeriod` demoted to Recommended (children Mandatory when present); `HealthData` kept Recommended | HMC exposes `LifeTime` only; nothing in the fleet exposes `CurrentPeriod` or `HealthData` [rec] |
| `Port.LinkState` demoted to Recommended; `LinkStatus` Purpose notes the `"OK"` value | HMC port reports carry `LinkStatus` only, reading `"OK"` [rec] |
| `Processor.Ports` Recommended in this profile (UBB still mandates it) | Dell models NVLink in `Oem.Dell` on ProcessorMetrics, not as Ports [rec] |
| New: `PCIeInterface.LanesInUse/MaxLanes` Mandatory when present | `LanesInUse 0` on 9 GPUs is the live bus-drop signature [live] |
| New: `Manager.Status.State` semantics for subordinate (accelerator) managers; `Manager.FirmwareVersion` Mandatory | Two detached trays in six weeks; firmware band decides tree shape [live] |
| New: `UpdateService.FirmwareInventory` shall enumerate every accelerator component | HGX 34 members; a drop is a component gone [live: A1-17 0/34] |
| New: `ServiceRoot.ServiceIdentification` Recommended; `UUID` demoted | Dell has no UUID; 121/121 BMCs uniquely identified pre-auth [sweep] |
| New: `ProtocolFeaturesSupported.ExpandQuery.MaxLevels` Mandatory (value guidance >= 2) | MaxLevels=1 costs 4x per node [live] |
| New: `Role.RoleId` MinSupportValues `ReadOnly` | The monitoring credential must be provably read-only [operator requirement] |
| New: `Chassis.Links.ContainedBy/Contains` Recommended | Node chassis vs GPU-tray chassis power scope [rec] |
| New: `LogEntry.VendorCode`, `DiagnosticDataType`, `CPER` Recommended | Redfish 2026.2 gives XID codes a standard field; RAS Requirements 1.7 wants CPER |
| New: `PowerSupply.Status.State=Absent` semantics; `Drive.FailurePredicted` Mandatory | PSU bays 5/6 Absent on a 4-supply chassis; drive fields are the tenant-node path [rec] |
| Registry: 6 new messages (subsystem unavailable/restored, HBM UCE, correctable rate, remap capacity exhausted, PCIe link degraded, sustained throttle, stale metric); link events deferred to OCP `AcceleratorFabric` | Each maps to an alert firing or defined in production [live] |
| Protocol MinVersion 1.15 (was 1.16) | AMI MegaRAC fleet at 1.15.1; newer features are IfImplemented/Recommended [sweep] |
| `SchemaDefinition` v1_10_0, `ProfileType: Conformance` | DSP0272 1.10.0 (2026.1); validator 3.0.0 |

## Validate

```bash
# against a recording in DMTF mockup layout: starts the DMTF mockup server on 127.0.0.1:8443 and runs the validator
MOCKUP_SERVER=/path/to/Redfish-Mockup-Server/redfishMockupServer.py \
  tools/run-validator.sh profiles/OCPNeocloudAccelerator.v0_6_0.json /path/to/recording

# property presence matrix without the validator
tools/evidence_matrix.py profiles/OCPNeocloudAccelerator.v0_6_0.json /path/to/recording-1 /path/to/recording-2
```

Read validator results with the recording's scope in mind: a resource the collector never fetched is
"not found" in the recording, not absent from the BMC. Record a new platform GET-only with a read-only
account, redact serials, tags, hostnames, MACs and UUIDs, and keep every metric value and firmware string.

## Open items for the workgroup

1. **UBB → MAS rename** (ocp-hm-system-gpu-management PR #64): update `RequiredProfiles` when it lands.
2. **Dell HBM ECC**: `MemoryMetrics.LifeTime` is Mandatory and iDRAC9 7.20 fails it. Confirm on iDRAC10 (its Telemetry Reference Guide documents a GPU Statistics report with SBE/DBE counters) and raise with Dell for iDRAC9.
3. **Lenovo XCC** exposes no accelerator surface (no HMC aggregation). Raise with Lenovo/NVIDIA: the SR680a V3 is an HGX H200 system without the HGX Redfish tree.
4. **`LinkStatus` enum** on the NVIDIA HMC (`"OK"` vs `LinkUp`): raise with NVIDIA.
5. **Second machines**: every recording is one machine per platform; the profile's Core floor should be re-run on a second unit per OEM and on Gigabyte/ASUS/MSI HGX units before it is proposed as approved.
6. **Registry mapping**: the XID/SXID code → MessageId table remains the open work item with the System GPU Management workstream; `VendorCode` (2026.2) may make a full mapping unnecessary.
