"""Read-only audit of staged/tracked files before publishing this specific challenge."""

import csv
import re
import subprocess
from pathlib import Path


def main():
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    files = [f for f in files if f]
    problems = []
    forbidden = [
        r"^referencias teoricas/",
        r"^desafio_tecnico_ai_eng_artefact\.pdf$",
        r"^data/.*\.csv$",
        r"^\.env$",
        r"^\.(aws|codex|agents)/",
        r"^runtime/",
        r"\.sqlite",
    ]
    secrets = re.compile(
        r"(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|"
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    )
    texts = {}
    for filename in files:
        if any(re.search(pattern, filename) for pattern in forbidden):
            problems.append(f"Excluded path tracked: {filename}")
        path = Path(filename)
        if path.suffix != ".pdf":
            content = path.read_text(encoding="utf-8")
            texts[filename] = content
            if secrets.search(content):
                problems.append(f"Possible secret in {filename}")
    customers = Path("data/desafio_tecnico_ai_eng - customers.csv")
    contacts_checked = False
    if customers.exists():
        with customers.open(encoding="utf-8-sig", newline="") as stream:
            values = [r[k] for r in csv.DictReader(stream) for k in ("name", "email", "phone")]
        for filename, content in texts.items():
            if any(value in content for value in values):
                problems.append(f"Original customer identifier in {filename}")
        contacts_checked = True
    with Path("fixtures/public/customers.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if not (
                row["name"].startswith("Cliente Demonstração")
                and row["email"].endswith("@example.invalid")
                and row["phone"].startswith("00")
            ):
                problems.append("Public customer fixtures are not sanitized")
    history = (
        subprocess.check_output(
            ["git", "-c", "core.quotepath=false", "log", "--all", "--name-only", "--pretty=format:"]
        )
        .decode()
        .splitlines()
    )
    if any(any(re.search(pattern, f) for pattern in forbidden) for f in history):
        problems.append("Excluded path found in Git history")
    if problems:
        print("\n".join(problems))
        return 1
    print(
        f"PASS: {len(files)} tracked files; no excluded paths or detected secrets. "
        f"Original-contact comparison: {'performed' if contacts_checked else 'originals absent'}. "
        "Public customer fixtures are synthetic; excluded paths absent from history."
    )
    print("Heuristic scan only; not a comprehensive secret/PII detector.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
