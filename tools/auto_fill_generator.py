from __future__ import annotations

import argparse

from pct.legal_coverage_ai import CoverageAutofillEngine, load_presets
from pct.legal_coverage_pipeline import generate_drafts
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera draft automatici con AI + retrieval.")
    add_db_args(parser)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api")
    parser.add_argument("--ollama-model", default="mistral")
    args = parser.parse_args()
    engine = CoverageAutofillEngine(
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        presets=load_presets(),
    )
    dump_payload(generate_drafts(build_repository(args), engine, limit=args.limit))


if __name__ == "__main__":
    main()
