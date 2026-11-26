"""Configure optional cloud support. Only a public HTTPS origin belongs here."""
import argparse
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

def endpoint(value):
    value = (value or "").strip()
    if not value:
        return ""
    u = urlsplit(value)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.path not in ("", "/") or u.query or u.fragment or any(c.isspace() for c in value) or "\\" in value:
        raise ValueError("BLD_SYNC_URL must be a public HTTPS origin without a path or credentials")
    return value.rstrip("/")

def stage(target, value, root=ROOT):
    # Flet packages the whole source directory. Never ship backend configuration,
    # .dev.vars, tests or local databases alongside the browser application.
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    for name in ("ui", "core", "data", "assets"):
        shutil.copytree(root/name, target/name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".*"))
    for name in ("main.py", "requirements.txt"):
        shutil.copyfile(root/name, target/name)
    prepare(None, value, target)


def prepare(output, value, root=ROOT):
    value = endpoint(value)
    if output is None:
        (root/"data/cloud_endpoint.py").write_text('"""Public sync-service URL, generated at build time."""\nSYNC_URL = '+repr(value)+'\n',encoding="utf-8")
    else:
        output = Path(output)
        for src in (root/"web_cloud").iterdir():
            if src.is_file():
                shutil.copyfile(src, output/src.name)
        (output/"cloud-endpoint.mjs").write_text("export const API = "+json.dumps(value)+";\n",encoding="utf-8")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output",type=Path)
    mode.add_argument("--stage",type=Path)
    args=parser.parse_args()
    value=os.environ.get("BLD_SYNC_URL","")
    if args.stage: stage(args.stage,value)
    else: prepare(args.output,value)
