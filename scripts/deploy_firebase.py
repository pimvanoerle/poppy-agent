#!/usr/bin/env python3
"""Deploy docs/ to Firebase Hosting via REST, using gcloud credentials.

Needed because UCP/Poppy profiles must be served with `Cache-Control: public, max-age>=60`
(GitHub Pages can't do that). Usage: python3 scripts/deploy_firebase.py [project] [site]
"""
import gzip, hashlib, json, subprocess, sys, urllib.request
from pathlib import Path

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "ipinch-crab-assistant"
SITE = sys.argv[2] if len(sys.argv) > 2 else "poppy-agent"
ROOT = Path(__file__).resolve().parent.parent / "docs"
CONFIG = {"headers": [{"glob": "**", "headers": {"Cache-Control": "public, max-age=300",
                                                 "Access-Control-Allow-Origin": "*"}}]}


def token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()


def call(method, url, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token()}", "x-goog-user-project": PROJECT, "Content-Type": ctype})
    with urllib.request.urlopen(req) as r:
        out = r.read()
    return json.loads(out) if out and ctype == "application/json" else out


api = f"https://firebasehosting.googleapis.com/v1beta1/sites/{SITE}"
blobs = {}
for f in sorted(p for p in ROOT.rglob("*") if p.is_file()):
    gz = gzip.compress(f.read_bytes(), mtime=0)
    blobs["/" + f.relative_to(ROOT).as_posix()] = (hashlib.sha256(gz).hexdigest(), gz)

ver = call("POST", f"{api}/versions", {"config": CONFIG})
name = ver["name"]
pop = call("POST", f"https://firebasehosting.googleapis.com/v1beta1/{name}:populateFiles",
           {"files": {k: v[0] for k, v in blobs.items()}})
by_hash = {h: gz for h, gz in blobs.values()}
for h in pop.get("uploadRequiredHashes", []):
    call("POST", f"{pop['uploadUrl']}/{h}", raw=by_hash[h], ctype="application/octet-stream")
call("PATCH", f"https://firebasehosting.googleapis.com/v1beta1/{name}?update_mask=status", {"status": "FINALIZED"})
rel = call("POST", f"{api}/releases?versionName={name}", {})
print("released", rel.get("version", {}).get("name"), f"-> https://{SITE}.web.app")
