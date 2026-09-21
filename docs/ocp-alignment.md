# Alignment plan — OCP Hardware Management, System GPU Management, and the neocloud workstream

Full landscape survey (Sept 2026): `research/ocp-landscape-2026-09.md`.

## Where this profile lives and how it gets approved

1. **Venue.** All OCP Redfish profiles are owned by the **Hardware Management project, Manageability
   Profiles workstream** (`HWMgmt-OCP-Profiles`; John Leung (Intel) maintains, Mike Raineri (DMTF)
   co-authors). Domain profiles are developed in a subfolder or a workstream repo and promoted to the
   repo root when approved (each with a Usage Guide in the OCP Contribution database).
2. **Path.** Develop here (`opencomputeproject/neocloud-redfish`, created 2026-08-13) → open a tracking
   issue in `HWMgmt-OCP-Profiles` and present at the Profiles call → PR a `Neocloud/` subfolder (or keep
   this repo as the workstream repo, as System GPU Management does) → Usage Guide in the OCP markdown
   template (`ocp-spec-tools`) → promotion.
3. **Co-review.** The **System GPU Management workstream** (`ocp-hm-system-gpu-management`) owns
   `OCP_UBB_BaselineManagement` (2.0.0, Aug 2026) and the `AcceleratorFabric` registry; the accelerator
   tier here composes the former and defers link events to the latter. Ask them to co-review
   `OCPNeocloudAccelerator` and to take the `OCPAcceleratorRAS` messages into their registry work.
4. **Requirements source.** The **FTI "Scaling AI Clusters at Neoclouds"** workstream (chair the contributing operator;
   co-leads Scaleway, Denvr) is the sponsor, not the approval body. Its March 2026 survey ranked
   "HW Mgmt & Interop (BMC/BIOS/firmware/telemetry)" #1 on importance and OCP leverage and named the
   deliverable: an interoperability checklist plus gap tickets into the HM project. This repo is that
   checklist in machine-validatable form.

## What to reuse rather than write

| Existing work | How this profile uses it |
|---|---|
| `OCPServiceBaseline` 1.0.0, `OCPBaselineHardwareManagement` 1.1.x, `OCPServerHardwareManagement` 1.0.0 (1.1.0 pending) | `RequiredProfiles` of ServiceCore |
| `OCP_UBB_BaselineManagement` 2.0.0 (→ MAS) | `RequiredProfiles` of Accelerator |
| `AcceleratorFabric` registry (draft, System GPU Mgmt) | Referenced in Accelerator `Registries`; link/flap/training messages are not duplicated |
| OCP GPU & Accelerator RAS Requirements 1.7 (2025-10-23), GPU FW Update 1.1, GPU & Accelerator Management Interfaces 1.1 (AMC/HMC model) | Cited in Purposes; CPER/`AdditionalDataURI` requirements align |
| DMTF DSP2090 Aggregation Guidance for Compute Expansion Modules | The host-BMC ↔ HMC aggregation model the System GPU spec v0.1 adopts |
| OCP fork of Redfish-Interop-Validator (`ocp-diag-ctam-redfish_interop_validator`) and CTAM | Conformance tooling; this repo's CI uses the DMTF validator 3.0.0 |
| OCP Liquid Cooling, Rack & Power, OpenRMC profiles | Out of scope for v0.6 (node profile); compose for NVL72 racks later |
| Lambda `redfish_exporter` (Apache-2.0) | The only other neocloud OOB GPU collector; same `Oem.Nvidia` field set — cite as second implementation evidence |

## Defects found upstream while validating (to file)

1. `HWMgmt-OCP-Profiles/OCPServerHardwareManagement.v1_0_0.json` declares `"ProfileVersion": "1,0,0"` — fails the DSP0272 schema; the validator aborts on any profile that requires it.
2. `OCPBaselineHardwareManagement.v1_1_1.json` self-declares `ProfileVersion` 1.1.0; `OCPRackManagerController.v1_0_3.json` has no ProfileName/Version (their issue #155).
3. `OCPServerHardwareManagement` 1.0.0 requires `Thermal.Temperatures[].PhysicalContext` to include `Intake` and `SerialConsole.ConnectTypesSupported` SSH or IPMI; a Dell XE9680 GPU server provides neither.
4. `HWMgmt-OCP-Profiles` README cites DSP0272 1.4.0; current is 1.10.0.
5. System GPU spec v0.1 still links the UBB profile at its old HWMgmt-OCP-Profiles path.
6. `ocp-hm-system-gpu-management/profiles/OCP_UBB_BaselineManagement.v2.0.0.json`: `UpdateService.ActionRequirements.SimpleUpdate` has `ReadRequirement: "IfImplement"` (typo) and `ParameterValues: ["HTTP??"]`; the DSP0272 schema rejects both and the validator aborts on every profile that requires UBB 2.0.0.
7. DMTF Redfish-Interop-Validator 3.0.0 (2026-09-18): `profile.py` calls `sut.get_resource_data()` for `UseCaseType` parent lookups; the method is `get_resource()`. Any profile using `UseCaseType: ProcessorType` (as the DSP0272 spec intends) crashes the run. Fix is a one-word rename.

## Other neoclouds

Lambda is the only neocloud with published OOB GPU tooling. CoreWeave (Mission Control), Nebius
(fault-tolerant training) and Fluidstack describe passive/active health pipelines but publish no Redfish
requirements. The FTI workstream is the place to bring them in: the ask is not "adopt our collector" but
"validate your OEMs against this profile and file the fails".
