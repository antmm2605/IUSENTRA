"""UI adapters for the shared public SentenzeWeb owner."""

from pct.sentenzeweb_corpus import configured_corpus


def inventory(config=None):
    """Read the shared owner's counts, without searching or loading decision bodies."""
    corpus = configured_corpus(config)
    if corpus is None:
        return {"available": False}
    with corpus._connect() as connection:
        progress = connection.execute("SELECT seen,expected,status FROM sentenzeweb_progress WHERE id=1").fetchone()
        count = connection.execute("SELECT count(*) FROM sentenze").fetchone()[0]
    return {
        "available": True,
        "caseCount": count,
        "received": progress["seen"] if progress else 0,
        "expected": progress["expected"] if progress else 0,
        "status": progress["status"] if progress else "unknown",
    }


def search(config, query=""):
    corpus = configured_corpus(config)
    if corpus is None:
        return {
            "ok": True,
            "available": False,
            "records": [],
            "message": "Corpus condiviso SentenzeWeb non configurato.",
        }
    query = str(query).strip()
    if len(query) > 500:
        raise ValueError("Query too long")
    records = corpus.cerca_sentenze(q=query, limit=10, semantica=False) if query else corpus.recent_acquisitions(10)
    return {
        "ok": True,
        **inventory(config),
        "records": [
            {
                "id": row["id"],
                "title": row["titolo"],
                "number": row["numero_sentenza"],
                "year": row["anno_sentenza"],
                "authority": row["organo_giudicante"],
                "section": row["sezione"],
                "date": row["data_deposito"],
                "textAvailable": bool(row["testo_integrale_presente"]),
                "textHref": f"/giurisprudenza/sentenzeweb/{row['id']}/testo",
            }
            for row in records
        ],
    }


def read_text(config, record_id):
    corpus = configured_corpus(config)
    if corpus is None:
        return ""
    record = corpus.get_sentenza(int(record_id))
    return str((record or {}).get("testo_integrale") or "")


def variants(config, record_id):
    corpus = configured_corpus(config)
    record = corpus.get_sentenza(int(record_id)) if corpus else None
    if not record:
        return {"ok": False, "documents": []}
    return {
        "ok": True,
        "documents": [
            {
                "id": row["id"],
                "title": row["titolo"],
                "sha256": row["sha256"],
                "chars": row["testo_estratto_chars"],
                "textHref": f"/giurisprudenza/sentenzeweb/{int(record_id)}/documenti/{row['id']}/testo",
            }
            for row in record.get("documenti", [])
        ],
    }


def read_variant(config, record_id, document_id):
    corpus = configured_corpus(config)
    if corpus is None:
        return ""
    with corpus._connect() as connection:
        row = connection.execute(
            "SELECT testo_estratto FROM documenti_sentenza WHERE sentenza_id=? AND id=?",
            (int(record_id), int(document_id)),
        ).fetchone()
    return str(row[0] or "") if row else ""
