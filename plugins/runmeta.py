"""
Sample Run Metadata Plugin for Git2Base

How it’s discovered:
- Place this file as `plugins/runmeta.py` next to the executable (or repository root when running from source).
- No env var needed. The loader auto-discovers `plugins/runmeta.py` and looks for one of:
  - `producer` (an object with project_metadata/run_metadata)
  - `make()` (a factory returning such an object)
  - Top-level functions `project_metadata(...)` and `run_metadata(...)`

Implementing the interface:
- project_metadata(...)-> dict: returns fields to merge into project.json
- run_metadata(...)-> dict: returns fields to merge into run.json

Reserved fields are managed by core and will be ignored if returned:
- project.json: schema_version, id, latest_run, updated_at, runs
- run.json: schema_version, project_id, run_id, run_type, scope_type, scope_key, started_at
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict
import os


class SampleRunMetaProducer:
    def project_metadata(
        self,
        *,
        artifacts_root: str,
        project: str,
        mode: str,
        branch: str,
        base: str,
        target: str,
        repo_path: str,
    ) -> Dict:
        # Example: enrich project.json with owner/team and repo info
        return {
            "product-version": "1.0.0",
            "product-name": "ExampleApp",
            "repository": {
                "path": repo_path,
                "default_branch": branch or None,
            },
        }

    def run_metadata(
        self,
        *,
        artifacts_root: str,
        project: str,
        run_id: str,
        mode: str,
        branch: str,
        base: str,
        target: str,
        repo_path: str,
    ) -> Dict:
        # Example: include CI/build context and scope details
        # Values here are merged into run.json (non-reserved keys only)
        ci_build_id = os.environ.get("CI_BUILD_ID")
        return {
            "mode": mode,
            "branch": branch,
            "base": base,
            "target": target,
            "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "ci_build_id": ci_build_id,
            "sprint": "Sprint 1",
        }


# Option A: provide a ready-made instance named `producer` (preferred)
producer = SampleRunMetaProducer()


# Option B: or provide a factory function named `make()` that returns an instance
def make() -> SampleRunMetaProducer:
    return SampleRunMetaProducer()


# Option C: or export top-level project_metadata/run_metadata functions
# (the loader will wrap them automatically)
def project_metadata(**kwargs):
    return producer.project_metadata(**kwargs)


def run_metadata(**kwargs):
    return producer.run_metadata(**kwargs)

