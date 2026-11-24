"""Validate the synthetic AU-02 handoff fixture without network access."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SECRET_CANARY = re.compile(r"(?:sk|rk|ghp|github_pat)-[A-Za-z0-9_-]{16,}")
PR_PATH = re.compile(r"^/Burn2288/FLOW-BRIDGE-GEN/pull/[1-9][0-9]*$")
CI_PATH = re.compile(r"^/Burn2288/FLOW-BRIDGE-GEN/actions/runs/[1-9][0-9]*$")


class HandoffError(ValueError):
    """The local handoff package does not satisfy the AU-02 fixture contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffError(message)


def _safe_report(root: Path, relative: object) -> Path:
    _require(isinstance(relative, str) and relative.strip(), "report path is required")
    path = Path(relative)
    _require(not path.is_absolute() and ".." not in path.parts, "unsafe report path")
    resolved = (root / path).resolve()
    _require(resolved.is_relative_to(root.resolve()), "report escapes package root")
    _require(resolved.suffix.lower() == ".md", "only documentation reports may be archived")
    return resolved


def _check_url(value: object, pattern: re.Pattern[str], label: str) -> None:
    _require(isinstance(value, str), f"{label} URL is required")
    parsed = urlsplit(value)
    _require(
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and not parsed.query
        and not parsed.fragment
        and bool(pattern.fullmatch(parsed.path)),
        f"invalid {label} URL",
    )


def validate(root: Path, manifest: dict[str, object]) -> tuple[int, int]:
    """Validate checksums, append history, provenance shape and docs-only scope."""
    _require(manifest.get("schema_version") == "au02-handoff-v1", "unsupported schema")
    _require(manifest.get("task_id") == "AU-02", "wrong task id")
    _require(manifest.get("fixture_mode") == "SYNTHETIC_ONLY", "fixture must be labelled synthetic")
    revisions = manifest.get("revisions")
    _require(isinstance(revisions, list) and len(revisions) == 2, "exactly two revisions are required")
    _require([r.get("revision") for r in revisions if isinstance(r, dict)] == ["r1", "r2"], "revision order must be r1 then r2")

    verdicts: list[dict[str, object]] = []
    for revision in revisions:
        _require(isinstance(revision, dict), "revision entry must be an object")
        _require(revision.get("files") and isinstance(revision["files"], list), "file inventory is required")
        _check_url(revision.get("pr_url"), PR_PATH, "PR")
        _check_url(revision.get("ci_url"), CI_PATH, "CI")
        for item in revision["files"]:
            _require(isinstance(item, dict), "file inventory entry must be an object")
            report = _safe_report(root, item.get("path"))
            _require(report.is_file(), "manifest references a missing report")
            expected = item.get("sha256")
            _require(isinstance(expected, str) and SHA256.fullmatch(expected), "invalid or missing SHA-256")
            raw = report.read_bytes()
            _require(hashlib.sha256(raw).hexdigest() == expected, "report SHA-256 mismatch")
            _require(not SECRET_CANARY.search(raw.decode("utf-8", errors="replace")), "secret canary detected")
        verdict = revision.get("verdict")
        _require(isinstance(verdict, dict), "revision verdict record is required")
        verdicts.append(verdict)

    _require(verdicts[0].get("result") == "REJECTED", "r1 negative verdict must be retained")
    _require(verdicts[0].get("source") == "SYNTHETIC_FIXTURE", "r1 verdict must be clearly synthetic")
    _require(verdicts[1].get("result") == "PENDING_INDEPENDENT_REVIEW", "r2 must remain pending review")
    _require(verdicts[1].get("preserved_prior_verdict") == verdicts[0], "r2 must preserve r1 verdict verbatim")
    return len(revisions), sum(len(revision["files"]) for revision in revisions)


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/audit/handoffs/AU-02-SYNTHETIC")
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        revisions, files = validate(root, manifest)
    except (OSError, json.JSONDecodeError, HandoffError) as exc:
        print(f"AU-02 handoff validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"AU-02 synthetic handoff valid: {revisions} revisions, {files} documentation files")
    print("Offline shape/checksum validation only; URLs, CI and independent review are not remotely verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

