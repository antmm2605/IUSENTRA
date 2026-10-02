"""Banco fonti di Lex: misura quanto la ricerca Normattiva trova gli articoli attesi.

Carica il mini-corpus (``corpus.json``) in un database SQLite temporaneo con lo schema dell'importer
Normattiva e confronta due ricerche sulle stesse domande (``domande.json``):

- ``attuale``: ``search_normattiva`` del commit 50d9060 (LIKE con AND di tutti i termini), caricata con
  ``git show`` in un modulo temporaneo;
- ``fts``: ricerca lessicale FTS5 (bm25, articolo esatto, vigenza) del modulo 2A.

Metriche: recall@k = media sulle domande della quota di articoli attesi presenti nei primi k risultati
(un risultato e' un articolo di un codice; versioni diverse dello stesso articolo contano una volta);
MRR = media di 1/posizione del primo articolo atteso trovato (0 se assente).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from lex.normativa import normattiva_importer as imp
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from lex.ricerca_giuridica.testo import articolo_normalizzato, codice_da_atto

CARTELLA = Path(__file__).resolve().parent
RADICE = CARTELLA.parent.parent
COMMIT_BASE = "50d9060"
K_MAX = 10


def carica_corpus() -> dict[str, Any]:
    return json.loads((CARTELLA / "corpus.json").read_text(encoding="utf-8"))


def carica_domande() -> list[dict[str, Any]]:
    return json.loads((CARTELLA / "domande.json").read_text(encoding="utf-8"))["domande"]


def costruisci_db(percorso: Path, *, con_fts: bool = True) -> Path:
    """Importa il corpus con le stesse funzioni dell'importer (articoli e chunk) e indicizza FTS5."""

    conn = sqlite3.connect(str(percorso))
    conn.execute("PRAGMA foreign_keys=ON")
    imp.ensure_schema(conn)
    sink = io.StringIO()
    for documento in carica_corpus()["documenti"]:
        record = imp.DocumentRecord(
            collection_name="banco", zip_path="banco.zip", xml_entry=f"{documento['xml_sha256']}.xml",
            tipo_atto="CODICE", numero=documento["numero"], data_atto=documento["data_atto"],
            data_pubblicazione=documento["data_atto"], titolo=documento["titolo"],
            urn=f"urn:banco:{documento['xml_sha256']}", redazione_id=None, vigenza=documento["vigenza"],
            xml_sha256=documento["xml_sha256"], text_content="", topics=[], relevance_score=5.0, is_relevant=True,
            articles=[imp.ArticleRecord(a["numero"], a["rubrica"], f"Art. {a['numero']}. {a['rubrica']}. {a['testo']}", [], 1.0)
                      for a in documento["articoli"]],
        )
        doc_id = imp.insert_document(conn, record, store_full_text=False)
        imp.insert_articles_and_chunks(conn, doc_id, record, jsonl_file=sink, max_chunk_chars=1800, only_relevant_articles=False)
    conn.commit()
    if con_fts:
        sincronizza_fts(conn)
    conn.close()
    return percorso


def _carica_ricerca_attuale(cartella_tmp: Path):
    """Modulo ``official_sources_retriever`` come era nel commit 50d9060."""

    sorgente = subprocess.run(
        ["git", "show", f"{COMMIT_BASE}:lex/retrieval/official_sources_retriever.py"],
        cwd=RADICE, capture_output=True, text=True, check=True,
    ).stdout
    file = cartella_tmp / "official_sources_retriever_50d9060.py"
    file.write_text(sorgente, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("official_sources_retriever_50d9060", file)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _chiave(riga: dict[str, Any]) -> tuple[str, str]:
    metadata = riga.get("metadata") or {}
    numero = str(metadata.get("numero") or "")
    data = str(metadata.get("data_atto") or riga.get("data") or "")
    codice = codice_da_atto(numero, data, riga.get("titolo"))
    articolo = articolo_normalizzato(str(metadata.get("article_number") or riga.get("articolo_o_chunk") or ""))
    return codice, articolo


def _in_classifica(righe: list[dict[str, Any]]) -> list[tuple[str, str]]:
    classifica: list[tuple[str, str]] = []
    for riga in righe:
        chiave = _chiave(riga)
        if chiave not in classifica:
            classifica.append(chiave)
    return classifica


def metriche(classifiche: list[list[tuple[str, str]]], domande: list[dict[str, Any]]) -> dict[str, float]:
    r5 = r10 = mrr = 0.0
    for classifica, domanda in zip(classifiche, domande):
        attesi = [(a["codice"], a["articolo"]) for a in domanda["attesi"]]
        r5 += sum(1 for a in attesi if a in classifica[:5]) / len(attesi)
        r10 += sum(1 for a in attesi if a in classifica[:10]) / len(attesi)
        posizioni = [classifica.index(a) + 1 for a in attesi if a in classifica]
        mrr += 1.0 / min(posizioni) if posizioni else 0.0
    n = len(domande)
    return {"recall@5": r5 / n, "recall@10": r10 / n, "mrr": mrr / n}


def esegui_banco(cartella_tmp: Path | None = None, embedder: Any = None) -> dict[str, Any]:
    """Esegue il banco e restituisce metriche e classifiche di ogni ricerca.

    Con ``embedder`` (finto o Ollama) costruisce l'indice vettoriale del mini-corpus e misura anche
    la ricerca ``semantica`` (solo vettori) e ``ibrida`` (FTS + vettori, RRF).
    """

    os.environ.setdefault("LEX_RICERCA_SEMANTICA", "0")  # il banco 2A misura la parte lessicale
    domande = carica_domande()
    with tempfile.TemporaryDirectory() as tmp:
        base = cartella_tmp or Path(tmp)
        db = costruisci_db(base / "normattiva_banco.sqlite")
        vecchio = _carica_ricerca_attuale(base)
        inesistente = base / "nessun.jsonl"

        from lex.ricerca_giuridica.ibrida import cerca_normattiva_indicizzata

        ricerche: dict[str, Callable[[str], list[dict[str, Any]]]] = {
            "attuale": lambda q: vecchio.search_normattiva(q, limit=K_MAX, db_path=db, jsonl_path=inesistente),
            "fts": lambda q: cerca_normattiva_indicizzata(q, db, limite=K_MAX) or [],
        }
        if embedder is not None:
            from lex.ricerca_giuridica.ibrida import MotoreRicercaNormattiva
            from lex.ricerca_giuridica.indice_vettoriale import costruisci_indice

            conn_v = sqlite3.connect(str(db))
            try:
                costruisci_indice(conn_v, base / "vettori", embedder, batch=64)
            finally:
                conn_v.close()
            motore = MotoreRicercaNormattiva(db, base / "vettori", embedder=embedder)
            if not motore.stato()["semantica_attiva"]:
                raise RuntimeError(motore.stato()["motivo_semantica"])
            ricerche["semantica"] = lambda q: motore.cerca(q, limite=K_MAX, modalita="semantica")
            ricerche["ibrida"] = lambda q: motore.cerca(q, limite=K_MAX, modalita="ibrida")
        risultati: dict[str, Any] = {}
        for nome, funzione in ricerche.items():
            righe_per_domanda = [funzione(d["domanda"]) for d in domande]
            classifiche = [_in_classifica(righe) for righe in righe_per_domanda]
            risultati[nome] = {
                "metriche": metriche(classifiche, domande),
                "classifiche": classifiche,
                "vigenze": [[str(r.get("vigenza") or "") for r in righe] for righe in righe_per_domanda],
            }
    return {"domande": domande, "ricerche": risultati}


def tabella(esito: dict[str, Any]) -> str:
    righe = [f"Banco fonti Lex: {len(esito['domande'])} domande", "",
             f"{'ricerca':<10}{'recall@5':>10}{'recall@10':>11}{'MRR':>8}"]
    for nome, dati in esito["ricerche"].items():
        m = dati["metriche"]
        righe.append(f"{nome:<10}{m['recall@5']:>10.3f}{m['recall@10']:>11.3f}{m['mrr']:>8.3f}")
    return "\n".join(righe)
