"""Bounded public transcription recovery using the native archive and acquisition lock."""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.sentenzeweb_corpus import body_available
from pct.sentenzeweb_recovery import enqueue_recovery, recover_pending
from tools.sentenzeweb_importa import FileLock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--seed-existing", action="store_true", help="Explicit initial inventory of missing/notice bodies")
    parser.add_argument("--max-records", type=int, default=25)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--promote-active", action="store_true", help="Requires deployed provenance-aware readers")
    args = parser.parse_args()
    root = args.directory.resolve()
    db = root / "giurisprudenza_corpus.db"
    if not db.is_file() or db.is_symlink():
        raise ValueError("Existing public corpus required")
    try:
        with FileLock(str(root / "acquisizione.lock")):
            owner = GestioneCorpusGiurisprudenza(str(db))
            seeded = 0
            if args.seed_existing:
                with closing(sqlite3.connect(db)) as connection, connection:
                    connection.row_factory = sqlite3.Row
                    rows = connection.execute("""SELECT s.id,s.testo_integrale,MAX(r.source_version) AS version
                        FROM sentenze s JOIN fonti_giurisprudenza f ON f.id=s.fonte_id
                        JOIN sentenzeweb_aliases a ON a.native_uuid=s.uuid_interno
                        JOIN sentenzeweb_receipts r ON r.source_id=a.source_id
                        WHERE f.codice='cassazione_sentenzeweb'
                        AND (s.testo_integrale_presente=0 OR LENGTH(s.testo_integrale)<100)
                        GROUP BY s.id""")
                    for row in rows:
                        if not body_available(row["testo_integrale"]):
                            enqueue_recovery(connection, row["id"], row["version"])
                            seeded += 1
            result = recover_pending(owner, limit=args.max_records, interval=args.interval,
                                     promote_active=args.promote_active)
            print(json.dumps({"seeded": seeded, **result}), flush=True)
    except BlockingIOError:
        return 75
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
