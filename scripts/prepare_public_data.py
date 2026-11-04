"""Rebuild publishable fixtures without publishing the original customer contacts."""

import argparse
import json
from pathlib import Path

from emporio.ingest import sanitize

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data"))
    parser.add_argument("--destination", type=Path, default=Path("fixtures/public"))
    args = parser.parse_args()
    print(json.dumps(sanitize(args.source, args.destination), indent=2))
