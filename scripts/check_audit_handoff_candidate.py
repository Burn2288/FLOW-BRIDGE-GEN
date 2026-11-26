"""Offline AU-01 candidate gate. The caller supplies trusted checkout facts."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator


SCHEMA = Path(__file__).resolve().parents[1] / "docs/audit/HANDOFF-CANDIDATE.schema.json"


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_candidate(manifest, payload, *, expected_source, previous_hashes=None):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)
    if manifest["source"] != expected_source:
        raise ValueError("manifest source differs from trusted source facts")
    source = manifest["source"]
    for run in manifest["tests"]:
        if (run["checkout_sha"], run["checkout_tree"]) != (source["head_sha"], source["tree_sha"]):
            raise ValueError("CI checkout is not exact head/tree")
    reviewer = manifest["reviewer"]
    if reviewer and reviewer["identity"].casefold() == manifest["developer"].casefold():
        raise ValueError("self-review cannot be recorded as independent")
    if payload.is_symlink() or not payload.is_dir():
        raise ValueError("artifact payload is not a regular directory")
    artifacts = manifest["artifacts"]
    actual = {}
    for path in payload.rglob("*"):
        if path.is_symlink():
            raise ValueError("symbolic links are forbidden in the artifact payload")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("artifact is not a regular file")
        actual[path.relative_to(payload).as_posix()] = path
    for name in artifacts:
        relative = PurePosixPath(name)
        if relative.as_posix() != name or any(part in (".", "..") for part in relative.parts):
            raise ValueError("invalid artifact path")
    if set(actual) != set(artifacts):
        raise ValueError("artifact inventory mismatch")
    for name, path in actual.items():
        if _digest(path) != artifacts[name]:
            raise ValueError(f"artifact checksum mismatch: {name}")
    for name, digest in (previous_hashes or {}).items():
        if artifacts.get(name) != digest:
            raise ValueError(f"historical artifact changed or missing: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("payload", type=Path)
    parser.add_argument("trusted_source", type=Path, help="Independently obtained repository/base/head/tree JSON")
    parser.add_argument("--trusted-prior-inventory", type=Path)
    args = parser.parse_args()

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    validate_candidate(
        read(args.manifest),
        args.payload,
        expected_source=read(args.trusted_source),
        previous_hashes=read(args.trusted_prior_inventory) if args.trusted_prior_inventory else None,
    )
    print("AU-01 candidate manifest and artifact checksums validated (offline; acceptance not evaluated)")


if __name__ == "__main__":
    main()
