from __future__ import annotations

from pct.legal_coverage_pipeline import approve_draft, publish_approved_drafts, reject_draft
from tools.legal_coverage_cli_common import build_base_parser, build_repository, cli_main_guard, dump_payload, require_positive_int


def main() -> None:
    parser = build_base_parser('Gestisce review e publish dei draft coverage.')
    parser.add_argument('command', choices=['list', 'approve', 'reject', 'publish'])
    parser.add_argument('--draft-id', type=int)
    parser.add_argument('--reviewer', default='cli-reviewer')
    args = parser.parse_args()

    repository = build_repository(args)
    if args.command == 'list':
        dump_payload(repository.list_drafts())
        return

    if args.command == 'publish':
        dump_payload(publish_approved_drafts(repository, limit=20, auto_only=False, apply_to_db=True))
        return

    draft_id = require_positive_int(args.draft_id, 'draft-id')
    if args.command == 'approve':
        approve_draft(repository, draft_id, args.reviewer)
        dump_payload({'ok': True, 'draft_id': draft_id, 'status': 'approved'})
        return

    reject_draft(repository, draft_id, args.reviewer)
    dump_payload({'ok': True, 'draft_id': draft_id, 'status': 'rejected'})


if __name__ == '__main__':
    cli_main_guard(main)
