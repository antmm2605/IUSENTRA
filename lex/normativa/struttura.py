"""Struttura estratta dall'XML ufficiale; espansione circoscritta alla partizione.

Non ricostruisce capi dalla vicinanza numerica né modifica il testo di legge.
La proiezione è pubblica e locale nel database SQLite della biblioteca.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from collections.abc import Callable
from lex.normativa.applicabilita import Applicabilita

LIVELLI = {"book": "libro", "libro": "libro", "part": "parte", "parte": "parte",
           "title": "titolo", "titolo": "titolo", "chapter": "capo", "capo": "capo",
           "section": "sezione", "sezione": "sezione", "subsection": "sottosezione"}


def _nome(node):
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def _contenuto(node, names):
    for child in node:
        if _nome(child) in names:
            return " ".join(" ".join(child.itertext()).split())
    return ""


def percorso_xml(articolo, urn: str, versione: str, xml_sha256: str) -> list[dict]:
    """Identità vincolata a atto/versione/XML e posizione, non solo al titolo."""
    if len(xml_sha256) != 64 or not urn or not versione:
        raise ValueError("Identità XML/versione incompleta")
    int(xml_sha256, 16)
    path = []
    for node in reversed(list(articolo.iterancestors())):
        tipo = LIVELLI.get(_nome(node))
        if not tipo:
            continue
        numero = _contenuto(node, {"num", "numero"})
        rubrica = _contenuto(node, {"heading", "rubrica"})
        if not numero and not rubrica:
            continue  # contenitore XML vuoto: non è un capo dell'intera legge
        location = node.get("eId") or node.get("id") or node.getroottree().getpath(node)
        identity = json.dumps([urn, versione, xml_sha256, location], separators=(",", ":"))
        path.append({"id": hashlib.sha256(identity.encode()).hexdigest(), "tipo": tipo,
                     "numero": numero, "rubrica": rubrica,
                     "localizzatore": location, "xml_sha256": xml_sha256,
                     "urn": urn, "versione": versione})
    return path


def salva_proiezione(conn: sqlite3.Connection, document_id: int, righe: list[dict]) -> int:
    """Solo nel processo di importazione già transazionale; nessuna commit interna."""
    conn.execute("""CREATE TABLE IF NOT EXISTS normative_structure (
        article_id INTEGER NOT NULL, document_id INTEGER NOT NULL, node_id TEXT NOT NULL,
        depth INTEGER NOT NULL, ordinal INTEGER NOT NULL, node_json TEXT NOT NULL,
        PRIMARY KEY(article_id, node_id),
        FOREIGN KEY(article_id) REFERENCES normative_articles(id) ON DELETE CASCADE,
        FOREIGN KEY(document_id) REFERENCES normative_documents(id) ON DELETE CASCADE)""")
    conn.execute("CREATE INDEX IF NOT EXISTS normative_structure_node ON normative_structure(document_id,node_id,ordinal)")
    count = 0
    for ordinal, row in enumerate(righe):
        nodes = row.get("struttura_normativa", [])
        if not nodes:
            continue
        if type(row.get("article_id")) is int:
            found = conn.execute("SELECT id FROM normative_articles WHERE id=? AND document_id=? AND article_number=?",
                                 (row["article_id"], document_id, row["articolo"])).fetchall()
        else:
            found = conn.execute("SELECT id FROM normative_articles WHERE document_id=? AND article_number=?",
                                 (document_id, row["articolo"])).fetchall()
        if len(found) != 1:
            raise ValueError("Articolo ambiguo nella proiezione strutturale")
        article_id = found[0][0]
        for depth, node in enumerate(nodes):
            conn.execute("INSERT OR REPLACE INTO normative_structure VALUES(?,?,?,?,?,?)",
                         (article_id, document_id, node["id"], depth, row.get("ordinal", ordinal),
                          json.dumps(node, ensure_ascii=False, sort_keys=True)))
            count += 1
    return count


def espandi(conn: sqlite3.Connection, articoli: list[int], *, per_partizione=3, massimo=12,
            verifica_applicabilita: Callable[[int], Applicabilita] | None = None) -> dict:
    """Conserva tutti i diretti; aggiunge soltanto vicini nello stesso nodo foglia.

    Limiti alle aggiunte, non alla ricerca diretta. Nessuna scansione del testo.
    Assenza di struttura è esplicita e non attiva vicinanza numerica.
    """
    if not 0 <= per_partizione <= 10 or not 0 <= massimo <= 50 or len(articoli) > 100:
        raise ValueError("Budget di espansione non valido")
    direct = list(dict.fromkeys(articoli))
    if any(type(x) is not int or x < 1 for x in direct):
        raise ValueError("Identità articolo non valida")
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='normative_structure'").fetchone()
    if not exists:
        return {"diretti": direct, "aggiunti": [], "stato": "struttura_assente"}
    added, seen, esclusi = [], set(direct), []
    for article_id in direct:
        leaf = conn.execute("SELECT document_id,node_id,ordinal,node_json FROM normative_structure WHERE article_id=? ORDER BY depth DESC LIMIT 1", (article_id,)).fetchone()
        if not leaf:
            continue
        document, node, ordinal, payload = leaf
        # Libro/titolo da soli non autorizzano ad espandere tutta una legge.
        if json.loads(payload).get("tipo") not in {"capo", "sezione", "sottosezione"}:
            continue
        # Two index-backed bounded ranges; never enumerate an entire chapter.
        rows = conn.execute("SELECT article_id,ordinal FROM normative_structure WHERE document_id=? AND node_id=? AND ordinal<? ORDER BY ordinal DESC LIMIT ?", (document,node,ordinal,per_partizione)).fetchall()
        rows += conn.execute("SELECT article_id,ordinal FROM normative_structure WHERE document_id=? AND node_id=? AND ordinal>? ORDER BY ordinal LIMIT ?", (document,node,ordinal,per_partizione)).fetchall()
        taken = 0
        for ident, position in sorted(rows, key=lambda r: (abs(r[1]-ordinal), r[1])):
            if ident in seen:
                continue
            if taken >= per_partizione or len(added) >= massimo:
                break
            esito = verifica_applicabilita(ident) if verifica_applicabilita else None
            if not isinstance(esito, Applicabilita) or esito.stato != "applicabile":
                esclusi.append({"article_id": ident, "stato": esito.stato if isinstance(esito, Applicabilita) else "da_verificare"})
                continue
            added.append({"article_id": ident, "da_articolo": article_id, "partizione_id": node})
            seen.add(ident);taken += 1
        if len(added) >= massimo:
            break
    return {"diretti": direct, "aggiunti": added, "stato": "espansione_limitata", "esclusi_temporali": esclusi}
