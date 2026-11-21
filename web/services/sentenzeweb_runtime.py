"""UI adapters for the shared public SentenzeWeb owner."""

from pct.sentenzeweb_corpus import configured_corpus, source_text_status


def inventory(config=None):
    """Read the shared owner's counts, without searching or loading decision bodies."""
    from web.services.conteggi_archivio_cache import conteggio_memorizzato

    corpus = configured_corpus(config)
    if corpus is None:
        return {"available": False}
    # Il conteggio di 426.000 pronunce con il disco occupato costava fino a 90 s: si calcola fuori dalla richiesta.
    counts = conteggio_memorizzato(f"sentenzeweb:{corpus.db_path}", corpus.db_path, lambda: _inventory_counts(corpus))
    if counts is None:
        return {"available": True, "caseCount": None, "received": None, "expected": None, "status": "counting"}
    return {"available": True, **counts}


def _inventory_counts(corpus):
    with corpus._connect() as connection:
        progress = connection.execute("SELECT seen,expected,status FROM sentenzeweb_progress WHERE id=1").fetchone()
        count = connection.execute("SELECT count(*) FROM sentenze").fetchone()[0]
    return {
        "caseCount": count,
        "received": progress["seen"] if progress else 0,
        "expected": progress["expected"] if progress else 0,
        "status": progress["status"] if progress else "unknown",
    }


def _per_estremi(corpus, estremi):
    """Pronunce con quel numero e anno, dall'indice (anno, numero): risposta immediata anche su 426.000 decisioni."""
    from contextlib import closing

    from pct.giurisprudenza_corpus import _COLONNE_RICERCA

    numero = estremi["numero"]
    sql = (f"SELECT {_COLONNE_RICERCA} FROM sentenze s WHERE s.anno_sentenza = ? "
           "AND s.numero_sentenza IN (?, ?, ?, ?)")
    # SentenzeWeb scrive il numero con gli zeri iniziali («05425»): l'avvocato cita «5425/2021».
    params = [estremi["anno"], numero, numero.zfill(5), numero.zfill(6), f"{numero}/{estremi['anno']}"]
    if estremi["sezione"]:
        sql += " AND UPPER(COALESCE(s.sezione,'')) = ?"
        params.append(estremi["sezione"])
    if estremi["ramo"]:
        sql += " AND LOWER(s.organo_giudicante) LIKE ?"
        params.append(f"%{estremi['ramo']}%")
    with closing(corpus._connect()) as connection:
        rows = [dict(row) for row in connection.execute(sql + " ORDER BY s.data_deposito DESC LIMIT 20", params)]
    return corpus._guard_text_availability(rows)


def _scheda(row):
    from web.services.sentenzeweb_estremi import intestazione, materia_leggibile, ramo, sezione_leggibile

    organo = row.get("organo_giudicante") or ""
    branca = ramo(organo)
    return {
        "id": row["id"],
        "title": intestazione(row),
        "court": "Corte di cassazione",
        "branch": branca,
        "number": str(row.get("numero_sentenza") or "").lstrip("0") or row.get("numero_sentenza"),
        "year": row.get("anno_sentenza"),
        "authority": organo,
        "section": row.get("sezione"),
        "sectionLabel": sezione_leggibile(row.get("sezione"), organo),
        "kind": str(row.get("tipo_provvedimento") or ""),
        "subject": materia_leggibile(row.get("oggetto") or row.get("materia_principale")),
        "date": row.get("data_deposito"),
        "decisionDate": row.get("data_decisione") or "",
        "textAvailable": bool(row["testo_integrale_presente"]),
        "textStatus": row.get("source_text_status", "empty"),
        "textSourceUrl": row.get("text_source_url", ""),
        "textSourceOfficial": row.get("text_source_official"),
        "textHref": f"/giurisprudenza/sentenzeweb/{row['id']}/testo",
    }


def search(config, query="", numero="", anno="", sezione="", ramo=""):
    from web.services.sentenzeweb_estremi import estremi_cassazione

    corpus = configured_corpus(config)
    if corpus is None:
        return {
            "ok": True,
            "available": False,
            "records": [],
            "message": "Archivio delle sentenze della Cassazione non ancora attivato su questa installazione: la ricerca nei testi scaricati non è disponibile.",
        }
    query = str(query).strip()
    if len(query) > 500:
        raise ValueError("Query too long")
    estremi = estremi_cassazione(query, numero, anno)
    sezione = str(sezione or "").strip().upper()
    ramo = str(ramo or "").strip().lower()
    if estremi and sezione in {"U", "L", "F", "1", "2", "3", "4", "5", "6", "7"}:
        estremi["sezione"] = sezione
    if estremi and ramo in {"civile", "penale"}:
        estremi["ramo"] = ramo
    if not estremi and (str(numero or "").strip() or str(anno or "").strip()):
        return {"ok": True, **inventory(config), "searchedBy": "estremi", "records": [],
                "message": "Per cercare per estremi indica sia il numero sia l'anno (per esempio 5425 e 2021)."}
    message = ""
    if estremi:
        records = _per_estremi(corpus, estremi)
        if not records:
            message = (f"Nessuna pronuncia n. {estremi['numero']}/{estremi['anno']} nell'archivio scaricato"
                       + (" con la sezione indicata" if estremi["sezione"] or estremi["ramo"] else "") + ".")
    elif query:
        records = corpus.cerca_sentenze(q=query, limit=10, semantica=False)
    else:
        records = corpus.recent_acquisitions(10)
    return {
        "ok": True,
        **inventory(config),
        "searchedBy": "estremi" if estremi else "testo" if query else "recenti",
        **({"message": message} if message else {}),
        "records": [_scheda(row) for row in records],
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
                "textStatus": source_text_status(row.get("testo_estratto")),
                "official": bool(row.get("ufficiale")),
                "sourceUrl": row.get("url_origine") or "",
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
