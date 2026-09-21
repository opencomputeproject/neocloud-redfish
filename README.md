# neocloud-redfish — Redfish out-of-band management profile for neocloud GPU fleets

**Status: DRAFT v0.6.0 for the OCP "Scaling AI Clusters at Neoclouds" workstream and the OCP Hardware
Management project's Manageability Profiles workstream.** Not an approved OCP profile.

A neocloud rents GPU servers it did not design, from several OEMs, to tenants whose operating systems it
often cannot touch. The only management surface it is guaranteed on every node is the BMC. This repository
is a [Redfish Interoperability Profile](https://www.dmtf.org/dsp/DSP0272) family that says what that surface
must expose so a neocloud can run agentless, read-only fleet health at ClusterMAX Reliability and
Monitoring grade — and the **evidence** for every requirement, measured on production fleets rather than
read from datasheets.

## What is different about this profile

1. **Every requirement cites evidence.** `[live]` = a Thanos query against two production sites on
   2026-09-20 (153 BMCs, three platforms, 148k active series); `[rec]` = a recorded BMC tree committed
   as a test fixture; `[sweep]` = an unauthenticated 259-address fleet sweep. See `docs/evidence/`.
2. **It is testable without hardware.** Recorded BMC trees in DMTF mockup layout are served by the
   DMTF Redfish-Mockup-Server and the DMTF Redfish-Interop-Validator runs against them
   (`tools/run-validator.sh`); CI checks every profile against the DSP0272 schema. Results, including the
   upstream profile bugs the run exposed, are in `docs/evidence/recorded-tree-evidence.md`.
3. **It composes, it does not re-specify.** `RequiredProfiles` pulls in the approved OCP Service
   Baseline, Baseline Hardware Management and Server profiles, and the System GPU Management workstream's
   `OCP_UBB_BaselineManagement` 2.0.0. This repo adds only what those leave out for neocloud operations.
4. **Two surfaces, two levels.** The host BMC (DMTF standard, every vendor) and the accelerator
   management controller (NVIDIA HMC, aggregated or not) are profiled separately, because the fleet shows
   they behave differently. *Neocloud-Core* is the Mandatory floor; *Neocloud-Trusted* is the Recommended
   set operators can demand contractually.

## Contents

| Path | What |
|---|---|
| `profiles/OCPNeocloudServiceCore.v0_6_0.json` | Service plane: pre-auth identity, query floor, subordinate-manager liveness, firmware inventory, eventing, RBAC (ReadOnly role), audit log, Trusted-level attestation |
| `profiles/OCPNeocloudPlatform.v0_6_0.json` | Host tier any Redfish BMC must expose: power (with Absent-bay semantics), thermal, drives, DIMM/CPU health, containment for power scope |
| `profiles/OCPNeocloudAccelerator.v0_6_0.json` | Accelerator tier, UseCase-scoped to GPU processors: HBM ECC, PCIe AER + link width, throttle durations, NVLink port health, conditional bulk telemetry, RAS registries |
| `profiles/upstream/` | Verbatim copies of the composed OCP profiles the validator needs (one patched: see its README) |
| `registries/OCPAcceleratorRAS.1.0.0.json` | Draft message registry for accelerator RAS events (subsystem unavailable, HBM ECC, row remap, bus drop, link degraded, sustained throttle, stale metric) |
| `build_profiles.py` | Generates the JSON above. Edit this, not the JSON. |
| `docs/recommendation.md` | The consolidated recommendation and alignment plan |
| `docs/PROFILES.md` | How the family composes, the two levels, how to validate |
| `docs/gap-analysis.md` | ClusterMAX-lensed gap analysis, revised with fleet evidence |
| `docs/dmtf-proposals.md` | Schema and registry proposals to DMTF and OCP that this evidence justifies |
| `docs/evidence/` | Live fleet evidence and recorded-tree / validator evidence |
| `docs/research/` | OCP/DMTF landscape (Sept 2026) and the BMC research this builds on |
| `tools/` | `run-validator.sh` (validator against a recorded tree), `evidence_matrix.py` (profile vs recording) |

## Validate

```bash
pip install redfish_interop_validator
# against a recording in DMTF mockup layout (see docs/evidence/recorded-tree-evidence.md):
MOCKUP_SERVER=/path/to/Redfish-Mockup-Server/redfishMockupServer.py \
  tools/run-validator.sh profiles/OCPNeocloudAccelerator.v0_6_0.json /path/to/recording
```

Against a live BMC (GET-only, a read-only account):

```bash
rf_interop_validator -r https://<bmc> -u <ro-user> -p <pw> --nooemcheck profiles/OCPNeocloudAccelerator.v0_6_0.json
```

## Provenance

Evidence comes from a neocloud operator's production fleets (two sites, 153 BMCs, three platforms),
collected by an agentless GET-only Redfish exporter with read-only credentials, and from BMC trees
recorded with identities redacted. Site, fleet and node names are anonymized throughout (Site A / Site B,
fleets A1, B1, B2, nodes A1-017 and so on). The v0.5.0 draft and gap analysis were developed in a fork of
HWMgmt-OCP-Profiles (branch `neocloud-profiles`). Profiles and documents are CC-BY-SA-4.0, matching the
OCP profile corpus.

Contact: the OCP FTI workstream *Scaling AI Clusters at Neoclouds* (opencompute.org/projects/scaling-ai-clusters-at-neoclouds).
