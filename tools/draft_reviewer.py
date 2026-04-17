from __future__ import annotations

import argparse

from pct.legal_coverage_pipeline import approve_draft, publish_approved_drafts, reject_draft
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestisce review e publish dei draft coverage.")
    parser.add_argument("command", choices=["list", "approve", "reject", "publish"])
    parser.add_argument("--draft-id", type=int)
    parser.add_argument("--reviewer", default="cli-reviewer")
    add_db_args(parser)
    args = parser.parse_args()

    repository = build_repository(args)
    if args.command == "list":
        dump_payload(repository.list_drafts())
        return
    if args.command == "approve":
        approve_draft(repository, int(args.draft_id), args.reviewer)
        dump_payload({"ok": True, "draft_id": args.draft_id, "status": "approved"})
        return
    if args.command == "reject":
        reject_draft(repository, int(args.draft_id), args.reviewer)
        dump_payload({"ok": True, "draft_id": args.draft_id, "status": "rejected"})
        return
    dump_payload(publish_approved_drafts(repository, limit=20, auto_only=False, apply_to_db=True))


if __name__ == "__main__":
    main()
