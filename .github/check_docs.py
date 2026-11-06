"""Check the documentation entry points and relative Markdown file links."""

from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "docs/README.md",
    "docs/ROADMAP.md",
    "docs/audit/AS_IS_ARCHITECTURE.md",
    "docs/architecture/SYSTEM_OVERVIEW.md",
    "docs/contracts/README.md",
    "docs/operations/DEPLOYMENT.md",
    "docs/product/PRODUCT_SCOPE.md",
    "docs/acceptance/TEST_MATRIX.md",
    "docs/acceptance/EVIDENCE.md",
    "docs/acceptance/KNOWN_LIMITATIONS.md",
)
LINK = re.compile(r"\[[^\]\n]+\]\((<[^>\n]+>|[^\s)]+)\)")


def main():
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    tracked = set(output.decode("utf-8").split("\0"))
    errors = [
        f"Missing tracked document: {name}"
        for name in REQUIRED
        if name not in tracked or not (ROOT / name).is_file()
    ]
    documents = sorted(
        name for name in tracked
        if name in REQUIRED or (name.startswith("docs/") and name.endswith(".md"))
    )

    for name in documents:
        path = ROOT / name
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in LINK.finditer(line):
                url = urlsplit(match[1].strip("<>"))
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (path.parent / unquote(url.path)).resolve()
                if not target.is_relative_to(ROOT):
                    errors.append(f"{name}:{number}: link leaves repository: {match[1]}")
                    continue
                relative = target.relative_to(ROOT).as_posix()
                if not any(item == relative or item.startswith(relative + "/") for item in tracked):
                    errors.append(f"{name}:{number}: missing tracked link target: {match[1]}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(documents)} Markdown files")


if __name__ == "__main__":
    main()
