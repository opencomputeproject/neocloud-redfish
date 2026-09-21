# Gap analysis — Redfish out-of-band management vs. ClusterMAX, revised with fleet evidence

**Revision 2 (2026-09-20).** Revision 1 (the v0.5.0 draft, `the workstream chair/HWMgmt-OCP-Profiles` branch
`neocloud-profiles`) reasoned from the standards and vendor documentation. This revision keeps its
structure and tags and adds what six weeks of production collection on 153 BMCs changed. New or changed
findings are marked **[rev2]**.

Tags: 🟢 A standardizable today · 🟡 B Redfish gap (OEM-only) · 🔴 C out of Redfish scope.

## 0. What the evidence changed

| Rev 1 belief | Rev 2 finding |
|---|---|
| The GPU surface is NVIDIA's and therefore vendor-consistent | True for the *content* of the HMC surface, false for its *reachability*: Supermicro aggregates it; Dell iDRAC models GPUs itself with `Oem.Dell`/`Oem.Nvidia` and no HBM ECC; Lenovo XCC exposes no accelerator surface at all. **The profile must test reachability of the accelerator surface as a conformance item** [rev2]. |
| Mandate `ProcessorMetrics` + `MemoryMetrics` ECC (gap #1) | Confirmed and satisfiable on the HMC surface (14/15 and LifeTime ECC present). Unsatisfiable on iDRAC9 7.20 — that is the point of a profile [rev2]. |
| `EventService` absent from the GPU profile | Present and advertised on every vendor; the gap is *content* (registry MessageIds, `VendorCode`), not the service [rev2]. |
| Streaming telemetry is license-gated | Confirmed and worse: Dell's licensed telemetry shipped `ServiceEnabled=false` fleet-wide; one PATCH fixed it. Conditional (`IfImplemented`) is right [rev2]. |
| Liveness is a collector concern | Liveness of the accelerator subsystem is the single highest-value signal and has no standard carrier. Two detached trays in six weeks, one undetected for nine days [rev2]. |
| Member counts can be profiled as norms | Norms differ by HMC firmware band inside one SKU (25 vs 34 components). Profiles must forbid hardcoding [rev2]. |
| `$expand` is a nicety | It is the fleet-scale cost driver (4x per node at MaxLevels=1) [rev2]. |

## 1. Baseline reality check (rev 1 §1, updated)

`OCP_UBB_BaselineManagement` moved to `ocp-hm-system-gpu-management` and is at **2.0.0** (2026-08-28):
`MultipartHttpPushUri` replaced the deprecated push URI (rev 1 open item closed), `Processor.Ports` and
`TelemetryService` are Mandatory, `MemoryMetrics` still requires only `BandwidthPercent`, `PortMetrics`
only RX/TX bytes. The RAS content gap rev 1 identified is unchanged. UBB is being renamed MAS.

## 2. ClusterMAX category → Redfish mapping (rev 1 §2, with evidence)

### 2.1 Reliability + Monitoring

| ClusterMAX passive check | Redfish carrier | Tag | Fleet evidence [rev2] |
|---|---|---|---|
| GPU temperature / thermal throttling | `EnvironmentMetrics.TemperatureCelsius`; `ProcessorMetrics.*ThrottleDuration` | 🟢 | HMC: per-GPU temp ×2, HBM temp, throttle durations by 4 reasons (2 standard, 2 `Oem.Nvidia`). Dell: temp, `Oem.Dell` violation durations. Power-cap throttling ~45 s/day on busy GPUs; thermal 0. |
| ECC (GPU/HBM) | `MemoryMetrics.LifeTime.*`, `CacheMetricsTotal.LifeTime.*` | 🟢 / vendor gap | HMC: present. Dell: **absent**. Live: 1 GPU UCE>0, 7 CE>0 (up to 2.6e9), 10 with remaps. |
| HBM row remapping | `Oem.Nvidia.RowRemapping.*` | 🟡 | 2 GPUs with zero remap capacity left — RMA candidates found OOB. DMTF proposal #2. |
| GPU fell off the bus | `PCIeInterface.LanesInUse=0` + `Status` should be UnavailableOffline | 🟡→🟢 with guidance | 9 GPUs at 0 lanes on 2 nodes; Status still Enabled/OK. Proposal #8. |
| PCIe AER | `ProcessorMetrics.PCIeErrors.*` | 🟢 | HMC: 9 counters. Dell: Correctable only. |
| XID / SXID | `LogEntry.MessageId` + **`VendorCode` (2026.2)** | 🟡→🟢 | Free text today; `VendorCode` is the new standard carrier. Proposal #6. |
| NVLink connectivity and errors | `Port.LinkStatus`, `PortMetrics.RXErrors` (std); link-down/BER/symbol counters (`Oem.Nvidia`) | 🟡 | 5 nodes with all 8 GPUs' ports down (persisting 7 days); NVSwitch link-down counters to 978. Proposal #3. |
| GPU utilization (SM/tensor/occupancy) | `BandwidthPercent` (std); GPM `Oem.Nvidia` | 🟡 | HMC GPM report; Dell `Oem.Nvidia` (with a uint overflow seen on `SMUtilizationPercent`). |
| Power monitoring / capping | `EnvironmentMetrics.PowerWatts`, `PowerLimitWatts`; chassis `PowerControl` | 🟢 | 555.5 kW chassis / 309.7 kW GPU-tray visible fleet-wide OOB; both scopes needed. |
| Fans / environment | `Thermal`/`ThermalSubsystem`, `Sensor` | 🟢 | 37 chassis temps, 3 fan groups, 93 HGX sensors per node. |
| PSU health | `PowerSupplies[].Status`, input/output watts | 🟢 | 13 dead supplies on 11 nodes (Critical, ~5 W input), 8 of them in one rack → upstream feed suspect. Absent-bay semantics required. |
| Drive health | `Drive.FailurePredicted`, `PredictedMediaLifeLeftPercent`; Dell NVMe SMART report | 🟢 | 5 coarse fields on every platform; 15 SMART fields on Dell via telemetry. |
| Firmware consistency | `SoftwareInventory.Version` | 🟢 | 3 HMC firmware bands in production during a rolling update (27 → 100 nodes on 26.04 over 8 days). |
| **Accelerator subsystem liveness** | none standard | 🟡 | **A1-69 (Aug), A1-17 (Sept)**. Proposal #1. |
| Driver/NCCL/job-level checks, auto-drain | in-band / orchestration | 🔴 | unchanged |

### 2.2 Security — unchanged from rev 1, plus: the monitoring credential must be a `ReadOnly` role verified
at the role (`Role.RoleId` MinSupportValues), because demoting a shared account to read-only broke
provisioning that depended on it [rev2]. Pre-authentication identity (`ServiceIdentification`/UUID) lets a
client bind credentials to a machine rather than an IP and detect swaps before spending a credential
(121/121 in the sweep) [rev2]. The JBOF firmware that leaks power history unauthenticated is a security
conformance item RIP cannot express; test it separately [rev2].

### 2.3 Storage, 2.4 Networking, 2.5 Lifecycle, 2.6 out-of-scope — unchanged from rev 1, with one
addition: **facility gear is the weak link**. PDUs in the fleet either do not speak Redfish (SNMP only) or
ship a broken Redfish (session token accepted, every resource 404). The OCP RackPDU/PowerShelf profiles
exist; neoclouds should make them a procurement requirement [rev2].

## 3. The major gaps, prioritized (rev 1 §3, re-ranked by evidence)

1. **Accelerator subsystem liveness as a standard state** — new #1 [rev2].
2. **Mandate the GPU health content set** (ProcessorMetrics, HBM `MemoryMetrics.LifeTime`) — confirmed; the HMC already satisfies it, Dell does not.
3. **Standardize the `Oem.Nvidia` RAS counters** (row remap, NVLink errors, throttle reasons, stale flag) — these carry the real alert load.
4. **Accelerator RAS registry + `VendorCode`** for XID/SXID — align with `AcceleratorFabric`.
5. **Query floor / bulk telemetry** for fleet-scale cost.
6. **Firmware inventory as component census**; firmware-band-aware norms.
7. **Read-only role, pre-auth identity, audit log** (security plane).
8. **Absent-vs-failed semantics** (PSU bays, devices off the bus).
9. **Rack power/cooling composition** for NVL72 (unchanged; out of v0.6 scope).

## 4. OEM implementability (rev 1 §4, now measured)

| Vendor / BMC | Redfish | `$expand` | Accelerator surface | Passes Platform? | Passes Accelerator Core? |
|---|---|---|---|---|---|
| Supermicro (HGX B200, own BMC) | 1.22.2 | MaxLevels 3, excerpt, select | NVIDIA HMC aggregated: 12 bulk reports, 34 fw components, ComponentIntegrity 13–21 | yes (0 probe errors, 143 nodes) | yes (ProcessorMetrics 14/15, HBM LifeTime ECC); `LinkStatus` enum, `Status.Conditions` empty |
| Dell (XE9680 H100, iDRAC9 7.20.80.50) | 1.20.1 | **MaxLevels 1** | GPUs as `Processors/Video.Slot.*` with `Oem.Dell`/`Oem.Nvidia`; 29 telemetry definitions; no HMC | yes (10 nodes) | **no**: no HBM ECC, no `Ports`, PCIe Correctable only |
| Lenovo (SR680a V3 H200, XCC) | 1.22.0 | MaxLevels 2 | none: `Processors/GPU1..8` with temp/power sensors only | yes (per spike) | **no**: no accelerator RAS at all |
| AMI MegaRAC (Gigabyte, MSI PCIe GPU boxes) | 1.15.1 | MaxLevels 5 | n/a (no HMC); root advertises ComponentIntegrity/Fabrics with nothing behind | platform tier only | n/a |
| Supermicro JBOF (Insyde) | 1.11.0 | MaxLevels 2 | n/a | partial; telemetry names leak unauth | n/a |

The Core floor is therefore: **Platform passes on every vendor tested; Accelerator Core passes only where
the NVIDIA HMC surface is aggregated.** That is the finding to take to Dell and Lenovo (and to the
System GPU Management workstream, whose System GPU spec expects the aggregated model per DSP2090).

## 5–8. Out of scope, deliverable structure, protocol features, reconciliation — see rev 1

The rev 1 text for §5 (explicit disclaimers), §6 (two-axis structure), §7 (DSP0266 features to require:
aggregation, query parameters, SSE with `includeoriginofcondition`, apply-time, multipart update, mTLS,
OAuth2, restricted roles, outbound connections) and §8 (reconciliation with companion research) stands.
The v0.6.0 family implements §6 as three files (ServiceCore / Platform / Accelerator) instead of two, for
the reason in §0. New since rev 1: DSP0266 **1.25.0** (Aug 2026) adds resource aliases and registry
import-by-reference; DSP8010 **2026.2** adds `VendorCode`, `Policy`, Port UALink fields, `PowerBrake`,
`ComponentIntegrity.RawBitstream`, and the `Device`/`EventService` registries — see
`research/ocp-landscape-2026-09.md` §5 and `dmtf-proposals.md`.

---

## Appendix — Revision 1 text (v0.5.0 draft, for reference)

## OCP Neocloud Redfish Profile — Gap Analysis vs. ClusterMAX

_Prepared for the OCP "Scaling AI Clusters at Neoclouds" workgroup. Uses SemiAnalysis ClusterMAX criteria as the lens for finding gaps in a standardized Redfish profile for neoclouds._

---

### 0. The one thing to internalize first: the scope boundary

Redfish is **out-of-band, BMC-mediated hardware management**. ClusterMAX rates a **whole GPU-cloud business**. Most ClusterMAX line-items are not hardware-manageability at all — they're compliance attestations, software-plane orchestration, in-band fabric tuning, filesystem performance, and pricing. A Redfish profile can only ever move the needle on the *hardware-health and out-of-band-control* slices of ClusterMAX.

So the productive question is not "does Redfish cover ClusterMAX" (it can't), but: **of the ClusterMAX requirements that *are* hardware-manageability, which can a profile mandate today, which need the standard extended, and which are structurally out of scope?** Every gap below is tagged:

- **🟢 A — Standardizable today.** Standard Redfish schema exists; the profile just has to *require* it. The current OCP GPU baseline largely *doesn't*.
- **🟡 B — Redfish gap.** In Redfish's remit, but the standard schema is missing the property/registry, so it's OEM-only today. Needs a DMTF schema proposal and/or a profile-defined convention.
- **🔴 C — Out of Redfish scope.** Belongs to the software/orchestration plane, a companion OCP spec, or the business. The profile should explicitly *disclaim* these so the workgroup doesn't over-promise.

---

### 1. Baseline reality check — what the current OCP GPU profile actually mandates

The current accelerator profile in the repo is **`gpu/OCP_UBB_BaselineManagement.v1.0.0.json`** (Universal Baseboard / OAM baseline). It is **thin on exactly the signals ClusterMAX weights hardest**:

| Resource it covers | What it actually requires | Problem |
|---|---|---|
| `Processor` | Inventory only (`ProcessorType`, `Model`, `Status`, `Location`, `Ports`, link to `Metrics`) | Requires the *link* to `ProcessorMetrics` but mandates **no metric properties** — no utilization, clocks, throttle, ECC |
| `MemoryMetrics` | **`BandwidthPercent` only** | **Does not require `CorrectableECCErrorCount` / `UncorrectableECCErrorCount` or `HealthData`** — i.e. HBM ECC, the single most important GPU RAS signal, is not mandated |
| `PortMetrics` | `RXBytes`, `TXBytes` only | **No error counters at all** — no link errors, no NVLink/RDMA health |
| `Port` | `LinkState`, `LinkStatus`, speed | OK for up/down, nothing on flaps or error rates |
| `LogEntry` / `LogService` | Decent envelope (`MessageId`, `Severity`, `OriginOfCondition`, `AdditionalDataURI`) | But no required RAS message registry, and **no `EventService` to subscribe to them** |
| `TelemetryService` | Service + report definitions present | Mechanism is there; **content (which metrics) is not pinned** |
| `EnvironmentMetrics`, `ThermalSubsystem`, `ThermalMetrics`, `Sensor` | Present | Reasonable thermal/power coverage |
| `UpdateService`, `SoftwareInventory` | Present | OK for update mechanism + version reporting |
| `Certificate` | Present | But **no `AccountService`, `Role`, `ComponentIntegrity`, `SecureBoot`, `EventService`** |

**Resources entirely absent from the current GPU profile:** `ProcessorMetrics` (as a required block), `AccountService`, `Role`, `ComponentIntegrity` (SPDM/TPM attestation), `SecureBoot`, `EventService`/`EventDestination` (eventing & streaming), `Fabric`/`Switch` (NVLink/NVSwitch topology), `NetworkAdapter`/`NetworkDeviceFunction`/`EthernetInterface` (host fabric NIC — lives in the separate `OCP_NIC` profile), `PowerSubsystem`/`PowerDistribution`/`Outlet` (rack power — in `RackManagerController`), `CoolingUnit`/`LeakDetector` (liquid cooling — in `LiquidCooling`).

The neocloud profile's job is to **compose the existing OCP building blocks (Server HW Mgmt + NIC + RackManager + LiquidCooling + UBB) into one operator-grade requirement set, and then fill the GPU/fabric RAS holes the standard hasn't closed.**

---

### 2. ClusterMAX category → Redfish mapping (where the gaps live)

#### 2.1 Reliability + Monitoring — **the heart of what a profile can deliver, and the biggest current gap**

ClusterMAX's Reliability and Monitoring sections are a dense list of *hardware-health telemetry* — and this is precisely where Redfish is strong as a mechanism but the current profile is nearly empty on content.

| ClusterMAX requirement | Redfish mapping | Tag | Status / action |
|---|---|---|---|
| GPU temperature / thermal throttling alerts | `EnvironmentMetrics.TemperatureCelsius`; `ProcessorMetrics.ThrottlingCelsius`, `*ThrottleDuration` | 🟢 A | Mandate `ProcessorMetrics` properties — currently not required |
| ECC error detection (GPU/HBM) | `MemoryMetrics.{Correctable,Uncorrectable}ECCErrorCount`, `HealthData.AlarmTrips` | 🟢 A | **Mandate these — profile today requires only `BandwidthPercent`** |
| HBM row-remapping (pending/failed) | — | 🟡 B | OEM-only (NVIDIA). Propose `MemoryMetrics` extension; require via OEM convention meanwhile |
| GPU "falling off the bus" detection | Infer from `Status.State`→`Absent` + `PCIeErrors`; **no discrete "device removed" event** | 🟡 B | Propose a standard removal event; mandate `PCIeErrors` + state polling now |
| PCIe error monitoring (AER) | `ProcessorMetrics.PCIeErrors` / `PCIeDevice` (`Correctable/NonFatal/Fatal`, `L0ToRecoveryCount`, `ReplayCount`, `NAK*`, `BadTLP/DLLP`) | 🟢 A | Standardized & solid — mandate it |
| NVIDIA XID / NVSwitch SXID detection | `LogEntry` envelope exists; **no standard XID/SXID message registry** | 🟡 B | **Define an OCP accelerator-RAS message registry** (align to OCP GPU/Accelerator RAS Requirements v1.0); today XID is often syslog-scraped, not Redfish |
| NVLINK connectivity & error tracking (critical for NVL72) | `Fabric`/`Switch`/`Port` topology + `LinkState`/`LinkStatus`/`LinkDownCount`; **NVLink CRC/flit/replay/recovery counters not standardized** | 🟡 B | Profile must add `Fabric`/`Switch`; propose NVLink `PortMetrics` extension for the error counters |
| GPU utilization / per-engine util | `ProcessorMetrics.BandwidthPercent`; **no SM-occupancy / NVENC / mem-BW% breakdown** | 🟡 B | Mandate `BandwidthPercent`; flag per-engine as a DMTF gap |
| GPU throttle *reason* (HW slowdown / power cap / thermal) | Durations only; **no `ThrottleReasons` enum** | 🟡 B | Propose enum (mirror DCGM `CLOCK_THROTTLE_REASONS`) |
| Power monitoring & capping | `EnvironmentMetrics.PowerWatts/PowerLimitWatts`; `Control` (`SetPoint`, PID); `PowerSubsystem` | 🟢 A | Standard & strong — mandate, incl. `Control` for capping |
| Fan speed / IPMI-style env | `EnvironmentMetrics.FanSpeedsPercent`, `ThermalSubsystem.Fans` | 🟢 A | Mandate (replaces IPMI fallback) |
| IB link status / error counters / PKey consistency | `Port.InfiniBand` (GUIDs only); **no IB symbol/link-integrity/link-downed counters; no PKey/GID/SM modeling** | 🟡 B | See §2.4 — major IB gap |
| Driver/library version consistency across nodes | `SoftwareInventory.Version` per component; **no fleet "golden manifest"** | 🟡 B | Client-side aggregation; define expected-version reconciliation in profile guidance |
| Automated node draining/replacement, failure-prediction AI | — (this is orchestration consuming the signals) | 🔴 C | Out of scope; profile *feeds* it via eventing |
| Active/passive health checks, burn-in, TFLOP/MFU tracking | In-band (DCGM, NCCL tests, ncu) | 🔴 C | Out of scope; in-band tooling |

**Headline:** The profile already has the *mechanism* (TelemetryService, EventService, LogService). What's missing is a **mandated metric content set** and an **RAS error registry**. Today an operator validating a BMC against the OCP GPU profile is guaranteed almost none of the telemetry ClusterMAX expects.

#### 2.2 Security — maps partially; current profile barely engages

| ClusterMAX requirement | Redfish mapping | Tag |
|---|---|---|
| SOC 2 / ISO 27001 / FedRAMP / GDPR/PCI/HIPAA attestations | — | 🔴 C (business/process; the *critical-failure* item — purely org-level) |
| Penetration testing of IB/RoCE fabric | — | 🔴 C |
| RBAC / least-privilege on the management interface | `AccountService`, `Role` (`AssignedPrivileges`), `PrivilegeMap`, predefined roles | 🟢 A — **absent from current GPU profile; mandate it** |
| MFA / external identity for BMC admin | `AccountService.MultiFactorAuth`, `LDAP`/`OAuth2`/`ActiveDirectory`/`TACACSplus` | 🟢 A — mandate at least one external IdP + MFA option |
| TLS / certificate lifecycle on the mgmt plane | `CertificateService`, per-service `Certificate` collections, CSR actions | 🟢 A — mandate (profile has `Certificate` but not the service) |
| Device attestation / supply-chain integrity (GPU, NIC, switch) | `ComponentIntegrity` (SPDM + TPM), `TrustedComponent`, `SecureBoot` w/ PK/KEK/db/dbx | 🟢 A — **absent today; this is a strong neocloud differentiator** |
| Signed/verified firmware | `UpdateService.SupportedUpdateImageFormats`, `SoftwareInventory.Measurement`/`WriteProtected` | 🟢 A — mandate |
| InfiniBand security keys (SM/SA/CKey/VSKey/AMKey) | — (IB subnet control plane) | 🔴 C — managed by SM/UFM, not Redfish |
| vLAN/PKey tenant isolation, SR-IOV QP0/MAD disable | — (host OS / NIC firmware / SM) | 🔴 C — out of band of Redfish today |
| Container-escape / NVIDIA Container Toolkit CVEs | — (software plane) | 🔴 C |
| Audit logs: actor identity, action, target, timestamp, success/fail; 90-day retention; queryable | `LogService` with `LogPurpose=Security` + `LogEntry.{Originator, OriginatorType, Username, UserAuthenticationSource, Created, MessageId}`; forward via `EventDestination` Syslog/SNMP to SIEM | 🟢 A / 🟡 B — building blocks exist but **content not normatively required**; mandate a Security-purpose audit log on privileged ops |

**Headline:** A neocloud profile can carry real security weight — RBAC, MFA, TLS lifecycle, **SPDM attestation**, SecureBoot, signed firmware, and a mandated audit log — *all standard Redfish, all absent from today's GPU profile*. It cannot touch the certification/pentest/tenant-isolation items (those are org + SM/UFM + software plane).

#### 2.3 Storage — split sharply between local NVMe (in scope) and the parallel FS (out)

| ClusterMAX requirement | Redfish mapping | Tag |
|---|---|---|
| Local NVMe health, wear, temperature | `Drive`, `Storage`, `StorageController`, NVMe `Drive.Metrics` (`PredictedMediaLifeLeftPercent`), `Volume` | 🟢 A — add `Drive`/`Storage` to the profile (not in UBB today) |
| NVMe-oF / disaggregated storage fabric | `Fabric`/`Endpoint`/`Connection`, NVMe-oF model | 🟡 B — partial standard; uneven implementation |
| Parallel FS (Weka/VAST/DDN) performance, mount reliability | — | 🔴 C — appliance/software plane, not BMC |
| S3-compatible object storage, durability SLAs | — | 🔴 C |
| Backups, PITR, CRR, snapshots, WORM/object-lock, CMK/BYOK | — | 🔴 C — data-service plane |
| Checkpoint storage durability for training | — | 🔴 C |

**Headline:** Redfish reaches *node-local drives and the storage-fabric hardware*. The things ClusterMAX actually grades storage on (parallel-FS throughput, object durability, backup/DR) are entirely software/appliance plane. Scope storage in the profile to **local-drive health + storage-fabric inventory** and disclaim the rest.

#### 2.4 Networking — the second-biggest hardware gap (IB/RoCE fabric)

| ClusterMAX requirement | Redfish mapping | Tag |
|---|---|---|
| NIC port status / speed / GUID / MAC | `Port`, `NetworkDeviceFunction.InfiniBand` (NodeGUID/PortGUID), `EthernetInterface` | 🟢 A — pull host NIC into the profile (today only in `OCP_NIC`) |
| RoCE lossless config visibility (PFC/ECN) | `Port.Ethernet.FlowControl*`, `PortMetrics.Networking.*PFCFrames`, RDMA counters | 🟢 A — mandate |
| Link-flap detection/prevention | `Port.LinkTransitionIndicator`; **no cumulative flap counter** | 🟡 B — propose standard flap counter; OEM meanwhile |
| IB symbol/link-integrity/link-downed/recv errors | **No standard `PortMetrics` mapping** (classic IB PortCounters absent) | 🟡 B — **major gap**; propose IB counter block, else OEM/`perfquery`/UFM |
| PKey / GID / LID / Subnet Manager state | **None — only GUIDs modeled** | 🔴/🟡 — IB control plane lives in SM/UFM; Redfish models endpoints, not the subnet |
| Switch (ToR/leaf/spine) inventory, fw, env, reset | `Fabric`, `Switch`, `Port`, `EnvironmentMetrics` | 🟢 A — usable for **platform mgmt of switches**; add to profile |
| Switch data-plane config (VLAN/BGP/EVPN/ACL/ECN-WRED, IB routing/adaptive routing) | — | 🔴 C — **NOS-native (NVUE/gNMI/Cumulus/NVOS), not Redfish.** Scope switch Redfish to BMC/platform only |
| NCCL config, HPC-X, GID index, SHARP, NCCL tests | — (in-band) | 🔴 C |

**Headline:** Redfish gives you switch *platform* management and host-NIC *inventory + Ethernet/RDMA counters*. The IB-specific health counters (symbol errors, link recovery/downed) and the entire IB control plane (PKeys/SM) are gaps — partly fixable via DMTF proposals, partly structurally owned by the Subnet Manager/UFM.

#### 2.5 Lifecycle — mostly out of scope, one real audit hook

| ClusterMAX requirement | Tag | Note |
|---|---|---|
| UI vs Terraform onboarding, delivery timelines, egress fees | 🔴 C | Business/portal plane |
| Out-of-box GPUDirect RDMA, IB/RoCE drivers, head-node provisioning | 🔴 C | In-band provisioning |
| **Audit logs (resource/admin/billing actions, actor identity, 90-day retention, queryable, export)** | 🟢 A / 🟡 B | The *infrastructure-action* slice maps to a Redfish Security `LogService` (see §2.2). Resource-lifecycle/billing audit is the control-plane's job, but BMC-level admin actions should be in the mandated audit log |

#### 2.6 Orchestration / Pricing / Partnerships / Availability — 🔴 C, out of scope

SLURM/Kubernetes automation, Pyxis, kubectl/RBAC/SSO, PVC/S3 mounts, $/GPU-hr, consumption models, NVIDIA NCP/Lepton/SchedMD partnerships, GPU model availability/roadmap — **none are hardware-manageability.** A Redfish profile is irrelevant to these. State this plainly so reviewers don't expect coverage. (Indirectly, good out-of-band telemetry *enables* the orchestration layer's health-aware scheduling and chargeback metering via `EnvironmentMetrics.EnergykWh`/`Outlet.EnergykWh` — worth noting as an enabler.)

---

### 3. The major gaps, prioritized for the workgroup

Ranked by (impact on ClusterMAX hardware criteria) × (how fixable in a profile):

1. **Mandate a GPU health-telemetry content set (🟢 A — do this first, highest ROI).**
   The profile must *require* `ProcessorMetrics` (utilization, clocks, throttle durations, `PCIeErrors`) and real `MemoryMetrics` ECC (`Correctable/UncorrectableECCErrorCount`, `HealthData.AlarmTrips`) — not just `BandwidthPercent`. This single change closes most of the ClusterMAX Reliability/Monitoring hardware list and is pure standard Redfish.

2. **Add a standardized accelerator-RAS message registry (🟡 B).**
   No DMTF standard for NVIDIA XID / NVSwitch SXID (or AMD equivalents). Define an **OCP message registry** for accelerator RAS events, aligned with **OCP GPU & Accelerator RAS Requirements v1.0** and the UEFI CPER/`AdditionalDataURI` envelope. Without this, XID detection stays vendor-specific and often syslog-scraped.

3. **Add NVLink/NVSwitch fabric to the profile + propose the missing counters (🟡 B).**
   Require `Fabric`/`Switch`/`Port` topology with `LinkState`/`LinkStatus`/`LinkDownCount` (standard, NVIDIA already implements). Then drive a DMTF proposal for **NVLink-specific `PortMetrics`** (CRC/flit/replay/recovery) — critical for NVL72 where NVLink *is* the system fabric.

4. **Mandate `EventService`/`EventDestination` (🟢 A).**
   Eventing is entirely absent today. Without subscriptions/SSE + Syslog/SNMP forwarding, there's no push path to monitoring or SIEM — which silently undercuts both the Monitoring *and* Audit stories. Required for any serious neocloud.

5. **Add the security/attestation stack (🟢 A).**
   `AccountService`+`Role` (RBAC), MFA + external IdP, `CertificateService`, `SecureBoot`, and **`ComponentIntegrity` (SPDM/TPM) device attestation**. All standard, all absent. SPDM attestation in particular is a credible neocloud trust differentiator and supports the "sell to secure customers" ClusterMAX bar at the hardware-root level.

6. **Mandate a Security-purpose audit `LogService` (🟢 A / 🟡 B).**
   Require `LogPurpose=Security` populated with `Originator`/`Username`/`UserAuthenticationSource` on privileged operations, forwardable via `EventDestination` syslog. Maps directly to the ClusterMAX audit-log requirements (actor identity, action, timestamp, success/fail) at the BMC layer.

7. **Pull host fabric NIC + IB health into the profile, propose IB counters (🟡 B).**
   Compose `OCP_NIC` in; mandate Ethernet/RDMA/PFC counters; drive DMTF proposals for **IB symbol/link-integrity/link-downed counters and a link-flap counter**. Acknowledge PKey/GID/SM stays with the Subnet Manager/UFM.

8. **Compose rack power + liquid cooling for NVL72 (🟢 A).**
   Bring in `PowerDistribution`/`Outlet` (per-outlet energy → chargeback/showback), `Control` (power capping), and **`ThermalSubsystem.CoolantConnectors` + `LeakDetection` + `CoolingUnit`** (CDU). Liquid-cooling RAS is non-optional for GB200-class racks and the standard already models it.

9. **Add local-drive health + define firmware fleet-consistency guidance (🟢 A / 🟡 B).**
   `Drive`/`Storage` NVMe health; and since there's no standard "golden manifest," specify in profile guidance how operators reconcile `SoftwareInventory.Version` across the fleet for driver/firmware consistency.

---

### 4. The binding constraint — OEM implementability and conformance tiering

The neocloud OEMs in scope are **Supermicro, Dell, Lenovo, HPE, Gigabyte, MSI, ASUS**. A profile is only useful if it's implementable across all of them — so the real ceiling on "what to mandate" is not the Redfish standard, it's the **weakest BMC that must pass**. Two findings dominate:

#### 4.1 There are two surfaces, with opposite implementability

**(a) The GPU/accelerator surface is vendor-consistent — because it isn't the host OEM's.** On NVIDIA HGX 8-GPU (SXM) systems, the GPU management surface is produced by NVIDIA's own on-baseboard controller (the **HMC / "AMC" — Accelerator Management Controller**), which the host BMC aggregates or proxies. So Dell, HPE, Lenovo, Supermicro, Gigabyte, and ASUS HGX boxes all expose a **substantially identical NVIDIA-defined Redfish tree** for the GPUs: `Systems/HGX_Baseboard_0`, `Processors/GPU_SXM_<1..8>` with `ProcessorMetrics`/`MemoryMetrics`+ECC, `TelemetryService/MetricReportDefinitions/HGX_PlatformEnvironmentMetrics_0`, and `ComponentIntegrity` SPDM against per-device **ERoT** roots of trust. **This is great news:** the GPU-telemetry gaps in §2.1 are NVIDIA's to standardize, not each OEM's, and **OCP already has a spec for it — "GPU & Accelerator Management Interfaces v1.1" (the AMC model).** The profile should *align to and require that NVIDIA/AMC surface* for SXM systems rather than try to re-specify GPU telemetry per-OEM. (The AMD/Intel OAM equivalent is the UBB baseboard surface the current `OCP_UBB_BaselineManagement` profile targets — so the accelerator layer has two lineages: NVIDIA-AMC and OAM/UBB. MI300X-class systems matter to ClusterMAX, so cover both.)

Two consequences the profile must encode:
- **Allow both aggregation patterns** for reaching the GPU tree: native **Redfish Aggregation** *and* a **proxied/port-forwarded HMC** (NVIDIA's default host→HGX forward is TCP 18888). Don't assume a single flattened tree.
- **GPU surface lives on a separate Manager** (`Managers/HGX_BMC_0`) distinct from the host `Managers/BMC_0` — model both.

**(b) The host surface is where the seven OEMs diverge — and it splits into tiers:**

| Tier | Vendors | BMC stack | Host-side Redfish reality |
|---|---|---|---|
| **1 — strong** | **Dell** (iDRAC9/**iDRAC10**), **HPE** (iLO5/**iLO6**), **Lenovo** (**XCC3 = OpenBMC**, XCC2) | proprietary / OpenBMC | Mature TelemetryService streaming, full EventService (SSE+SNMP+syslog), ComponentIntegrity SPDM, SecureBoot, multipart UpdateService. Rarely needs IPMI fallback. |
| **2 — uneven (MegaRAC)** | **Supermicro** (X13/X14), **Gigabyte** (MegaRAC SP-X), **ASUS** (ASMB11 / MegaRAC SP-X) | AMI MegaRAC-derived (AST2600) | Redfish + IPMI run in tandem; **community reports IPMI fallbacks**. TelemetryService/EventService present but coverage uneven; SPDM/SecureBoot strictness is **firmware-version-gated** (improves with MegaRAC **OneTree**). |
| **3 — weakest / outlier** | **MSI** (EPS MegaRAC) | AMI MegaRAC | Newest entrant, least-proven; **ships PCIe 4-GPU servers only (no HGX SXM)** — so the NVIDIA HMC surface from (a) doesn't exist; GPU data comes via PLDM-to-BMC. |

#### 4.2 What this forces in the profile design

1. **Set the host-side conformance floor at what the MegaRAC trio can actually meet**, and split everything above it into a higher tier. The §2 items most at risk of being "🟢 in the standard but not in the box" on Tier-2/3 BMCs are exactly the host-side mandates: **EventService subscriptions, ComponentIntegrity/SPDM strictness, SecureBoot, the Security audit LogService, and streaming TelemetryService**. Treat those as a forcing function with a maturity ramp, not as an assumed baseline.

2. **Define conformance levels**, e.g. **Neocloud-Core** (must pass on all 7 — inventory, basic Processor/Memory/Sensor health, ECC, thermal/power, UpdateService, basic eventing) and **Neocloud-Trusted** (Tier-1-class — streaming telemetry, SPDM attestation, SecureBoot enforced, mandated audit log). This lets a neocloud *demand* Tier-1 behavior contractually while still onboarding MegaRAC boxes at Core.

3. **Make SXM-specific resources conditional.** Gate the NVIDIA `HGX_Baseboard_0`/`GPU_SXM_n`/HMC requirements on "system is an HGX SXM platform." Otherwise MSI (PCIe-only) and any PCIe-GPU SKU fail the profile spuriously.

4. **Use the variance as the profile's reason to exist.** The IPMI-fallback reality on Supermicro/Gigabyte/ASUS *is* the problem neoclouds feel today (telemetry inconsistency, event-subscription quirks). A profile validated by the **DMTF Redfish-Interop-Validator** turns "we think it works" into a pass/fail gate the OEM must clear — that's the lever to pull the MegaRAC trio up to the floor.

5. **Security note that ties back to ClusterMAX:** four of the seven (Supermicro, Gigabyte, ASUS, MSI) run AMI MegaRAC, which has a recurring history of **auth-bypass CVEs (MegaRAC SPx)**. The management plane itself is an attack surface — which is *why* mandating `ComponentIntegrity`/`SecureBoot`/RBAC/MFA on the BMC (§2.2) is a real ClusterMAX-Security contribution, not box-ticking: it hardens the most-shared, most-vulnerable component in the rack.

6. **Validate, don't trust datasheets.** No published per-vendor OCP conformance certificates exist for specific GPU SKUs. Run the Interop Validator against an actual HGX unit from each vendor as part of authoring the profile, so the floor is empirically set.

---

### 5. Explicitly out of scope — disclaim these in the profile

So the workgroup isn't asked "where's the SOC2 control": **compliance attestations (SOC2/ISO/FedRAMP/GDPR/PCI/HIPAA), pentesting, tenant network isolation (PKey/SM/SR-IOV QP0-MAD), container-runtime CVEs, SLURM/Kubernetes orchestration, in-band fabric tuning (NCCL/HPC-X/SHARP/GID index), parallel-filesystem & object-storage performance, backups/PITR/CRR/WORM, switch data-plane config, pricing, partnerships, and GPU availability/roadmap.** Redfish can *feed signals to* the layers that own these (health-aware scheduling, chargeback metering, SIEM), but it cannot satisfy them. The profile should say so.

---

### 6. Suggested structure for the deliverable

A **two-axis profile** — layered by *surface* (GPU vs host) and tiered by *conformance level* (Core vs Trusted) — all validated by the **DMTF Redfish-Interop-Validator**:

**Axis 1 — surfaces (from §4.1):**
- **Accelerator layer** = align to / require the NVIDIA **AMC/HMC** surface for HGX SXM systems (`HGX_Baseboard_0`, `GPU_SXM_n`, `HGX_PlatformEnvironmentMetrics`, `ComponentIntegrity`/ERoT), per **OCP GPU & Accelerator Management Interfaces v1.1**; mirror with the **OAM/UBB** surface for AMD/Intel. Gate on platform type so PCIe-GPU SKUs (e.g. MSI) don't fail spuriously. Allow both **Redfish Aggregation** and **port-forwarded HMC (TCP 18888)** access patterns.
- **Host layer** = compose existing OCP profiles (`OCPServerHardwareManagement` + `OCP_NIC` + `OCPRackManagerController` + `LiquidCooling`) and *tighten* the telemetry/eventing/security content that's currently optional (gaps #1, #4, #5, #6, #8, #9).

**Axis 2 — conformance tiers (from §4.2):**
- **Neocloud-Core** — the floor all 7 OEMs must pass on shipping firmware: inventory, Processor/Memory/Sensor health, **HBM ECC**, thermal/power, `UpdateService`, basic `EventService`. Set this empirically by running the Interop Validator against a real HGX unit from each vendor — pitched at what the **MegaRAC trio (Supermicro/Gigabyte/ASUS)** clears.
- **Neocloud-Trusted** — Tier-1-class (Dell iDRAC / HPE iLO / Lenovo XCC3): streaming TelemetryService, **SPDM `ComponentIntegrity`**, enforced `SecureBoot`, mandated **Security audit LogService**, full RBAC/MFA. Lets operators *contractually demand* Tier-1 behavior while still onboarding MegaRAC boxes at Core.

Two upstream tracks to open in parallel: **(a) DMTF Redfish proposals** for the 🟡 B schema gaps (NVLink/IB counters, GPU throttle-reason enum, HBM row-remapping, link-flap counter, device-removed event); **(b) an OCP accelerator-RAS message registry** harmonizing XID/SXID/AMD codes with OCP GPU & Accelerator RAS Requirements v1.0 — and since the GPU surface is NVIDIA's (§4.1), drive (a)/(b) jointly with NVIDIA so the AMC firmware and the DMTF schema converge rather than fork.

---

### 7. Protocol features ALREADY in DSP0266 v1.24.0 the profile should require

The §2 gaps are mostly about *schema content* (what telemetry exists). This section is the opposite and more encouraging: the **protocol spec (DSP0266 v1.24.0, dated 2026-04-02)** already standardizes a rich set of *mechanisms* that neoclouds need and that most BMCs under-implement. These need **no new standards work** — the profile can mandate them today. Each is tagged with the spec clause and the version it landed in (to show maturity).

#### 7.1 Redfish Aggregation (§16) — the highest-leverage feature, and it directly solves the §4.1 seam

The spec defines a **complex aggregator**: one Redfish service that proxies and unifies many subordinate management controllers behind a single endpoint. The normative requirements (§16.2.2) are exactly what a neocloud wants:
- **"The aggregation implementation hosts only one event service … shall combine all events into one stream. The implementation also hosts only one sessions service, telemetry service, update service."** → a single pane for an entire node, rack, or pod.
- **URI fix-up + unique `Id`** (UUID/serial/MAC/WWN) so aggregated systems don't collide.
- **Health/state roll-up** to the parent.
- **`AggregationSource` + `ConnectionMethod`** (§16.2.4): a `ConnectionMethod` can be **Redfish, IPMI, *or* proprietary**.

Two consequences for the profile:
1. **It's the standardized form of the host-BMC↔GPU-HMC relationship** from §4.1 — the host BMC is a complex aggregator over the NVIDIA HMC. Require the aggregator behavior so the GPU tree appears unified (alongside the port-forward fallback).
2. **`ConnectionMethod=IPMI` turns the Tier-2 weakness into a managed problem.** A rack/pod-level aggregator can absorb IPMI-fallback MegaRAC boxes (Supermicro/Gigabyte/ASUS) and the GPU HMCs into **one event + telemetry stream** — letting the neocloud's monitoring/SIEM hit one endpoint per pod instead of per-BMC. This is the single biggest operational simplifier in the spec.

#### 7.2 Query parameters for fleet-scale polling (§7.3)

Polling thousands of GPUs naively melts BMCs. The spec standardizes the fixes — require the service to advertise `ProtocolFeaturesSupported` in ServiceRoot and to support:
- **`$expand` with `$levels`** (§7.3.2) — pull a subtree in one GET instead of walking hyperlinks (e.g. all `Processors` + their `Metrics`).
- **`$select`** (§7.3.3) and **`excerpt`** — return only the properties you poll on (e.g. just ECC counts + temps), cutting payloads by orders of magnitude. `excerpt` returns the schema-defined telemetry subset.
- **`$filter`** (§7.3.4) — server-side filtering of collections (e.g. only members with a degraded `Status`).
- **`$top`/`$skip`** pagination and **`only`** for single-member collections.
- **`clientcontext`** (§7.3.5, **NEW in 1.24.0**) — stateless **iterative retrieval of `LogEntryCollection`**. Purpose-built for incrementally scraping huge BMC/SEL logs without re-reading — directly useful for **harvesting XID/SXID and RAS log entries** at fleet scale.

#### 7.3 Streaming eventing & telemetry (§12.1, §12.5) — require it, since it's the §2.1/§4.2 "EventService absent" fix

- **SSE event stream** (§12.5.2.1) and **SSE metric-report stream** (§12.5.2.2) — push events and periodic `MetricReport`s over a single long-lived connection instead of polling. This is the standardized streaming-telemetry channel.
- **`includeoriginofcondition`** (§12.5, query param **NEW in 1.22.0**) — the event payload carries the **expanded `OriginOfCondition` resource inline**, so a SIEM/monitoring consumer gets the faulting GPU/port/PSU's full state *with* the event — no follow-up GET. Big reduction in alert-to-context latency.
- **Subscription delivery to Syslog/SNMP/Redfish** and **privilege enforcement on event delivery** (§13.7, hardened in 1.20.1).

#### 7.4 Operation apply time + maintenance windows (§7.12, §9.9.8–9.9.9)

`@Redfish.OperationApplyTime` lets a client schedule *when* a disruptive operation lands — `SupportedValues` include **`Immediate`, `OnReset`, `AtMaintenanceWindowStart`, `InMaintenanceWindowOnReset`** — with `MaintenanceWindowStartTime` / `MaintenanceWindowDurationInSeconds` / `MaintenanceWindowResource`. Applies to **firmware update (multipart), config, action, and delete** bodies. This is how you push fleet-wide firmware/driver-consistency fixes (gap #9) **without unplanned reboots** — schedule them into the next maintenance window per node.

#### 7.5 Bulk firmware, config, and (re)provisioning push

- **Multipart HTTP push update** (§12.7.2.2) — push a firmware image targeting **specific components** via `MultipartHttpPushUri`; combines with apply-time (§7.4).
- **Import configuration data** (§12.8, **NEW in 1.23.0**) — multipart **bulk config import** → golden-config push across the fleet; supports onboarding/standardization.
- **Boot image multipart virtual-media insertion** (§12.9, **NEW in 1.24.0**) — push a boot image over Redfish → re-image / reprovision a node out-of-band (lifecycle / node replacement).

#### 7.6 Security mechanisms already standardized (§13) — most of §2.2's host-side asks

- **TLS 1.2/1.3 mandated** with a defined cipher-suite floor (§13.1).
- **Client-certificate / mTLS authentication** (§13.3.5) — mutual-TLS BMC access.
- **OAuth 2.0 delegated authorization / JWT** (§13.4.4) — SSO/IdP integration for the management plane (maps to ClusterMAX RBAC/SSO).
- **Operation-to-privilege mapping + PrivilegeRegistry** (§13.4.3) and **restricted roles / restricted privileges** (§13.4.2.2, since 1.11) — fine-grained authz that **prevents privilege escalation** — directly relevant to the AMI-MegaRAC BMC attack-surface concern (§4.2.5).
- **TOTP secret-key handling for session creation** (§13.5.5, **NEW in 1.21.0**) — protocol-level **MFA**.
- **Atomic password changes** (§13.5.3) and **session termination when an account is deleted/disabled** (§13.3.4, hardened in 1.23.2).

#### 7.7 Two more worth requiring

- **Outbound connections with mTLS** (§12.10, WebSocket-based) — the **BMC initiates a call-home** to an aggregator/manager. Lets BMCs on isolated/NAT'd management networks reach the neocloud control plane **without inbound reachability** — valuable for multi-site fleets.
- **Transiently unavailable resources** (§9.11.3, **NEW in 1.20.1**) + **absent resources** (§9.11.2) — standard `Status.State` semantics for a device that has dropped, giving a cleaner protocol-level signal for **"GPU fell off the bus"** than inference alone (partially closes that §2.1 gap).
- **ETags / conditional `If-Match` PATCH** (§6.5) and **deep operations** (§7.13) — safe concurrent config and multi-resource updates in one request.

**Net:** require **Aggregation (§16), `ProtocolFeaturesSupported` + a query-parameter floor (§7.3), SSE streaming with `includeoriginofcondition` (§12.5), operation-apply-time/maintenance-windows (§7.12), multipart update + config import (§12.7–12.8), and the §13 security stack (mTLS, OAuth2, restricted roles, TOTP)** in the **Neocloud-Trusted** tier, with a lighter subset (query params, basic SSE, multipart update) in **Neocloud-Core**. None of this needs new schema — it's the maturity ramp that pulls the MegaRAC trio up and gives Tier-1 BMCs a contract to prove against.

---

### 8. Reconciliation with companion research — what we missed, and one correction

Two independent research passes (`deep-research-report.md`, `Research Report redfish.md`) corroborate the core thesis (Redfish covers the hardware/service plane; the UBB GPU baseline under-specifies RAS; NVLink/XID/ECC are the critical gaps; layered profile + RAS message registry is the fix). They also add material this analysis missed. Net-new and corrective items, verified against the repo and vendor docs where load-bearing:

#### 8.1 Correction: the service-plane security/eventing primitives are NOT absent — they live in `OCPServiceBaseline`
I earlier flagged AccountService/Role/CertificateService/EventService as "absent from the GPU profile." Literally true for `OCP_UBB_BaselineManagement`, but misleading: the approved **`OCPServiceBaseline.v1_0_0`** already requires/recommends them. Confirmed resource list: **`AccountService`, `Role`, `ManagerAccount`, `CertificateService`+`Certificate`, `EventService`+`EventDestination`, `SessionService`+`Session`, `TaskService`, `UpdateService`, `ManagerNetworkProtocol`** — plus, notably, **`OutboundConnection`** (the §7.7 mTLS call-home), **`RegisteredClient`**, **`License`/`LicenseService`**, and **`ServiceConditions`**. **The fix is composition, not invention:** make `OCPServiceBaseline` a hard `RequiredProfiles` dependency of the neocloud profile. (Still genuinely missing even there: SecureBoot, ComponentIntegrity/SPDM, and a normatively-populated audit log.)

#### 8.2 The thing required *everywhere* has zero GPU telemetry
Confirmed: **`OCPBaselineHardwareManagement.v1_1_1`** (and the Server profile) contain **no `TelemetryService`, no `Processor`/`ProcessorMetrics`, no `Memory`/`MemoryMetrics`, no `Port`, no `PCIeDevice`** — and still carry the **deprecated `Power`/`Thermal`** schemas alongside `PowerSubsystem`/`ThermalSubsystem` (either/or accepted), with power-capping only *Recommended*. So the universally-required baseline is inventory/power-state oriented; all GPU telemetry rests on the in-development UBB subfolder profile alone.

#### 8.3 OEM telemetry is license-gated and platform-limited — this reshapes the tier design (VERIFIED)
The single most important thing missed. "Mandate TelemetryService" is not freely satisfiable:
- **HPE iLO 5/6 implement the Telemetry Service on Intel-based servers only** — AMD (Gen10/11) and ARM Gen11 **don't provide it**. Many neocloud GPU nodes are AMD-EPYC → a hard mandate is *un*-implementable there. (Verified against HPE iLO Telemetry docs.)
- **Dell iDRAC telemetry streaming requires a Datacenter license** (14G+). (Verified against Dell iDRAC9 telemetry white paper.)
- **Supermicro** end-to-end Redfish is gated behind the **SFT-DCMS-SINGLE** license; **Lenovo** GPU telemetry behind **Premier/Platinum** tiers.

**Design consequence:** the profile cannot treat streaming telemetry as a free Core requirement. Express it as **conditional** ("if `TelemetryService` is implemented, then these MetricReportDefinitions/properties are Mandatory"), keep raw `ProcessorMetrics`/`MemoryMetrics`/`Sensor` polling (no license needed) in **Neocloud-Core**, and put licensed streaming in **Neocloud-Trusted** — while using the profile as leverage to push OEMs to **de-license basic health telemetry**. `OCPServiceBaseline` already models `LicenseService`, so license state is itself discoverable/auditable.

#### 8.4 Use the modern structured-health model we under-emphasized: `Status.Conditions` + `HealthRollup`
Redfish's standard **`Status.Conditions`** array (active conditions with `MessageId`, `Severity`, `OriginOfCondition`, `Timestamp`) and **`Status.HealthRollup`** are the vendor-neutral way to surface *active faults* — the natural carrier for "this GPU has an active XID/ECC/NVLink condition" that pairs with the §2 RAS message registry. `OCPServiceBaseline` already exposes `ServiceConditions`. Require `Conditions`/`HealthRollup` on GPU `Processor`, `Memory`, `Port`, and `Switch` so a client can read current faults without log-scraping.

#### 8.5 DC infrastructure: adopt DSP2056 + DSP2064; the approved rack profile is on deprecated schemas
For GB200 NVL72-class racks, require the modern models: **DSP2056** — `PowerDistribution`/`Outlet`/`Circuit`/`PowerDistributionMetrics` (rack PDU/busbar/power-shelf), and **DSP2064** — `ThermalEquipment/CDUs` (`CoolingUnit`), `CoolingLoop`, `CoolantConnector` (supply/return temp, flow LPM, pressure), `LeakDetection`/`LeakDetector`, `Pump`. The **approved `OCPRackManagerController` still uses the legacy/deprecated `Power`/`Thermal` schemas** with no MetricReport requirements; CDU/leak/outlet requirements exist only in the in-development LiquidCooling/RackAndPower subfolders. NVIDIA GB200 already exposes `Chassis/.../ThermalSubsystem/LeakDetection/...`, proving the model — it just isn't profiled. **Migrate the rack profile off `Power`/`Thermal`** as part of this.

#### 8.6 Storage is SNIA Swordfish, not plain Redfish
The OCP storage profile is **v0.1.0**, requiring only three Swordfish feature profiles (discovery, event-notification, block-provisioning). Expansion path is selectively requiring more **Swordfish** capability (performance instrumentation, file provisioning, replication, snapshots, security management) — not re-modeling storage in base Redfish. (This refines §2.3: node-local `Drive`/`Storage` health stays base Redfish; managed/array storage is Swordfish; parallel-FS/object durability remains 🔴 out of scope.)

#### 8.7 Rack-scale NVLink (NVL72) is managed out-of-band of Redfish — and the LinkState property is currently buggy
On GB200 NVL72, the rack-scale NVLink fabric is owned by **NMX-C / NVIDIA Global Fabric Manager (GFM)**, *outside* the HMC Redfish tree. So per-node Redfish `Processor.Ports`/`Fabric`/`Switch` requirements only cover **intra-node** NVLink; the cross-tray fabric needs a **GFM API reference**, not a Redfish mandate. Also: NVIDIA's own GB200 release notes document a firmware bug where NVLink **`LinkState`/`LinkStatus` misreport** (disabled links show `Enabled`/`LinkUp`) — so don't lean on that single property for health today; corroborate with error counters/conditions.

#### 8.8 OCP is already moving here — align, don't duplicate
A draft **OCP "GPU Management" profile (v0.9.1)** already shows `Status.Conditions`, `HealthRollup`, chassis `Switches` links, and certificate/SPDM fields — i.e. the community is heading exactly where §2/§8.4 point. And **SPDM attestation** is being handled by the **OCP Security WG ("Attestation of System Components")** and **"GPU & Accelerator Management Interfaces"** (SPDM over MCTP/Redfish, §4.1's AMC model). The neocloud profile should *reference and converge* with these rather than re-specify them.

#### 8.9 Housekeeping the workgroup should do first
- **Schema-refresh pass.** An open (Mar 2026) repo issue notes UBB still mandates the **deprecated `HttpPushUriOptions`** instead of `MultipartHttpPushUri` parameters. Align the corpus to a current DSP8010 snapshot *before* layering new requirements.
- **DMTF service-root capabilities not yet surfaced by OCP service baseline** and worth considering: **`JobService`** (scheduled fleet jobs), **`KeyService`** (key management), **`CompositionService`/`ResourceBlocks`** (disaggregation/bring-up), **`AggregationService`** (§7.1), **`TelemetryService`**.

#### 8.10 Two framing nuances
- **Partial credit on tenant isolation:** the OCP **NIC profile already requires SR-IOV fields** (`MaxVirtualFunctions`, `VirtualFunctionsEnabled`) + `@Redfish.Settings` + RDMA `PortMetrics`. So ClusterMAX's "SR-IOV with QP0/MAD disabled" is *partially* observable (VF enablement), though QP0/MAD restriction itself remains SM/firmware territory (🔴).
- **ClusterMAX is relative, not a checklist.** ClusterMAX 2.0 (SemiAnalysis, launched 2025-11-06; rated 84 of 209+ providers) is **peer-benchmarked** and cites DCGM field names (e.g. `DCGM_FI_DEV_ECC_SBE_VOL_TOTAL`). A conformant profile is **necessary but not sufficient** for Gold/Platinum — it standardizes the *substrate* of the Monitoring/Reliability criteria, not the operator excellence layered on top.

---

#### Key sources
- OCP HWMgmt-OCP-Profiles repo — current profiles incl. `gpu/OCP_UBB_BaselineManagement.v1.0.0.json`: https://github.com/opencomputeproject/HWMgmt-OCP-Profiles
- OCP Scaling AI Clusters at Neoclouds: https://www.opencompute.org/wiki/OCP_Future_Technologies_Initiative/Scaling_AI_Clusters_at_Neoclouds
- OCP GPU & Accelerator RAS Requirements v1.0: https://www.opencompute.org/documents/ocp-gpu-and-accelerators-ras-requirements-1-0-final-pdf
- Redfish Specification (protocol) DSP0266 v1.24.0, 2026-04-02 — §7.3 query params, §7.12 apply time, §12 eventing/SSE/update/outbound, §13 security, §16 aggregation: https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.24.0.html
- Redfish Resource & Schema Guide (DSP2046): https://redfish.dmtf.org/schemas/DSP2046_2024.2.html
- ProcessorMetrics / MemoryMetrics / Port / PortMetrics / PCIeDevice / EnvironmentMetrics / ThermalSubsystem / Control / ComponentIntegrity / EventService schemas: https://redfish.dmtf.org/schemas/v1/
- Modeling NVLink in Redfish (DMTF forum): https://redfishforum.com/thread/1189/model-nvlink-interconnection-gpus
- Redfish Streaming Telemetry WIP (OCP 2025): https://www.dmtf.org/sites/default/files/OCP_Summit_2025-Redfish_Streaming_Telemetry.pdf
- DMTF PMCI / PLDM (DSP0248, DSP0249): https://www.dmtf.org/standards/pmci
- NVIDIA GB200 NVL72 known issues (OEM NVLink/NVSwitch URIs): https://docs.nvidia.com/dgx/dgxgb200nvl72-release-notes/known-issues.html
- OCP GPU & Accelerator Management Interfaces v1.1 (AMC/HMC model): https://www.opencompute.org/documents/ocp-gpu-accelerator-management-interfaces-v1-1-pdf
- DMTF Redfish-Interop-Validator (profile conformance testing): https://github.com/DMTF/Redfish-Interop-Validator
- NVIDIA DGX H100/H200 Redfish + FW guide (host↔HGX aggregation, port 18888): https://docs.nvidia.com/dgx/dgxh100-user-guide/redfish-api-supp.html
- NVIDIA SPDM attestation via Redfish ComponentIntegrity (ERoT): https://docs.nvidia.com/networking/display/bluefieldbmcv2601/DPU-BMC-SPDM-Attestation-via-Redfish
- Per-OEM BMC: Dell iDRAC10 telemetry streaming, HPE iLO6 SPDM, Lenovo XCC3 (OpenBMC), Supermicro Redfish guide, AMI MegaRAC OneTree — see vendor docs (iDRAC10 telemetry: https://infohub.delltechnologies.com/en-us/l/idrac10-real-time-telemetry-in-action-streaming-server-gpu-and-os-metrics-to-external-tools/ ; XCC3: https://lenovopress.lenovo.com/lp2273-lenovo-xclarity-controller-3-xcc3 ; AMI OneTree: https://www.ami.com/blog/2025/08/20/ami-releases-megarac-onetree-2-1/ )
- OEM telemetry licensing/platform limits (verified): HPE iLO Telemetry Service is Intel-only (no AMD/ARM): https://servermanagementportal.ext.hpe.com/docs/redfishservices/ilos/supplementdocuments/ilotelemetryservice ; Dell iDRAC telemetry streaming requires Datacenter license (14G+): https://dl.dell.com/manuals/common/dell-emc-idrac9-telemetry-streaming-basics.pdf
- OCP profiles confirmed via repo: `OCPServiceBaseline.v1_0_0.json` (AccountService/Role/CertificateService/EventService/SessionService/TaskService/OutboundConnection/LicenseService/ServiceConditions), `OCPBaselineHardwareManagement.v1_1_1.json` (no TelemetryService/Processor/Memory; deprecated Power/Thermal): https://github.com/opencomputeproject/HWMgmt-OCP-Profiles
- DMTF DC infrastructure white papers: DSP2056 (PowerDistribution/Outlet/Circuit) and DSP2064 (CoolingUnit/CoolingLoop/CoolantConnector/LeakDetection): https://www.dmtf.org/standards/redfish
- SNIA Swordfish (storage extension to Redfish): https://www.snia.org/forums/smi/swordfish
