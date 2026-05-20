from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.legal_sources.web_verifier import verify_ruleset_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica fonti ufficiali del motore Template Atti.")
    parser.add_argument("--output-dir", default="data/legal_sources/snapshots")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    results = verify_ruleset_sources(
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
        offline=args.offline,
    )
    print(json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
