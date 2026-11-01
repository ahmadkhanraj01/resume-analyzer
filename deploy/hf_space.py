"""Deploys backend/ to a Hugging Face Docker Space.

A Space is its own git repo whose README.md must start with Space metadata,
so this stages the committed backend files (git archive, so nothing local or
uncommitted ships), swaps in a metadata README, and mirrors the result to
the Space. Secrets are set in the Space's settings, never here.

Usage, from the repo root, after `hf auth login` with a write token:

    uv run --with huggingface_hub python deploy/hf_space.py

Space URL: https://<owner>-<name>.hf.space (the API is under /api).
"""

import argparse
import io
import subprocess
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parent.parent

# app_port matches the Dockerfile's fallback port, so the Space needs no PORT.
SPACE_README = """---
title: Resume Analyzer API
emoji: 📏
colorFrom: yellow
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
---

Backend API for Resume Analyzer. Source and docs:
https://github.com/ahmadkhanraj01/resume-analyzer
"""


def stage(dest: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD", "backend"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            rel = Path(member.name).relative_to("backend") if member.name != "backend" else None
            # Tests are excluded from the image by .dockerignore anyway, and
            # their PDF fixtures would trip the Hub's binary-file check.
            if rel is None or rel.parts[0] == "tests" or not member.isfile():
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
    (dest / "README.md").write_text(SPACE_README)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-id", default="ahmadkhanraj01/resume-analyzer-api")
    args = parser.parse_args()

    api = HfApi()
    api.create_repo(args.repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="space",
            folder_path=tmp,
            delete_patterns="*",  # mirror: drop files removed from backend/
            commit_message=f"Deploy backend at {commit}",
        )
    owner, name = args.repo_id.split("/")
    print(f"Deployed {commit}. Build logs: https://huggingface.co/spaces/{args.repo_id}")
    print(f"API: https://{owner.lower()}-{name.lower()}.hf.space/api/health")


if __name__ == "__main__":
    main()
