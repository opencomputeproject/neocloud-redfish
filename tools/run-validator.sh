#!/usr/bin/env bash
# Run the DMTF Redfish-Interop-Validator for a profile in this repo against a recorded BMC tree served by
# the DMTF Redfish-Mockup-Server. No hardware, no credential.
#
#   tools/run-validator.sh profiles/OCPNeocloudAccelerator.v0_6_0.json /path/to/recording
#
# A recording is a directory in DMTF mockup layout: <dir>/redfish/v1/<path>/index.json, one file per
# resource, identities redacted. Any Redfish mockup works; the OCP evidence recordings are described in
# docs/evidence/recorded-tree-evidence.md.
#
# Requires: pip install redfish_interop_validator ; git clone https://github.com/DMTF/Redfish-Mockup-Server
# (set MOCKUP_SERVER to its redfishMockupServer.py). The validator resolves RequiredProfiles by file name in
# the profile's directory, so the family and profiles/upstream/ are assembled into a temp dir first.
set -euo pipefail
PROFILE=${1:?profile json}
RECORDING=${2:?recording directory in mockup layout}
PORT=${PORT:-8443}
HERE=$(cd "$(dirname "$0")/.." && pwd)
LOGDIR=${LOGDIR:-$HERE/logs/$(basename "$RECORDING")-$(basename "$PROFILE" .json)}
MOCKUP_SERVER=${MOCKUP_SERVER:-redfishMockupServer.py}

WORK=$(mktemp -d)
cp "$HERE"/profiles/*.json "$HERE"/profiles/upstream/*.json "$WORK"/
python3 "$MOCKUP_SERVER" -D "$RECORDING" -H 127.0.0.1 -p "$PORT" &
BMC=$!
trap 'kill $BMC 2>/dev/null || true; rm -rf "$WORK"' EXIT
for _ in $(seq 1 20); do curl -fs "http://127.0.0.1:${PORT}/redfish/v1/" >/dev/null && break; sleep 0.5; done

rf_interop_validator -u x -p x --authtype Basic -r "http://127.0.0.1:${PORT}" \
  --logdir "$LOGDIR" --timeout 20 --nooemcheck "$WORK/$(basename "$PROFILE")" || true
echo "reports: $LOGDIR"
