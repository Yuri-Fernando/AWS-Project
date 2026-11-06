"""Publica artifacts/champion/ no S3 com manifesto (sha256 por arquivo). Endpoint via AWS_ENDPOINT_URL (floci)."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3

bucket = os.environ.get("ARTIFACT_BUCKET", "argus-platform-lab-ml-artifacts")
prefix = f"riskcredit/champion/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
root = Path("artifacts/champion")
s3 = boto3.client("s3")
try:
    s3.head_bucket(Bucket=bucket)
except Exception:
    s3.create_bucket(Bucket=bucket)
manifest = {"model": "riskcredit-champion", "prefix": prefix, "files": {}}
for f in sorted(p for p in root.rglob("*") if p.is_file()):
    key = f"{prefix}/{f.relative_to(root).as_posix()}"
    manifest["files"][key] = hashlib.sha256(f.read_bytes()).hexdigest()
    s3.upload_file(str(f), bucket, key)
s3.put_object(Bucket=bucket, Key=f"{prefix}/manifest.json", Body=json.dumps(manifest, indent=2).encode())
s3.put_object(Bucket=bucket, Key="riskcredit/champion/LATEST", Body=prefix.encode())
print(json.dumps({"bucket": bucket, "prefix": prefix, "files": len(manifest["files"])}))
