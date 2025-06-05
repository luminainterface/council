#!/usr/bin/env bash
set -euo pipefail

# Ensure pip-audit is present
python -m pip install --quiet --disable-pip-version-check \
    "pip-audit>=2.6,<3"

# Run the audit and emit json for artefacts
pip-audit -r requirements.txt -f json -o pip_audit.json

# Fail on any vuln ≥ medium
python - <<'PY'
import json, sys, pathlib
data = json.loads(pathlib.Path("pip_audit.json").read_text())
bad = [v for v in data if v["vuln_severity"].lower() in {"medium","high","critical"}]
if bad:
    print("❌  Supply-chain vulnerabilities detected:")
    for v in bad:
        print(f'   • {v["dependency"]} – {v["vuln_id"]} ({v["vuln_severity"]})')
    sys.exit(1)
print("✅  pip-audit clean (no medium+ vulns)")
PY 