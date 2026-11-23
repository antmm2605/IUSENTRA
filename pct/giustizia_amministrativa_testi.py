"""Testo integrale dei provvedimenti della Giustizia amministrativa, dal sito ufficiale, a partire dal catalogo OpenGA.

OpenGA (open data della Giustizia amministrativa, CKAN ``openga.giustizia-amministrativa.it``) pubblica gli estremi
dei provvedimenti (sede, tipo, numero, anno, numero di ricorso, oggetto, esito) ma non il testo. Il testo integrale
è pubblico sul sito istituzionale, all'indirizzo del provvedimento (verificato il 21/11/2026 su Cons. Stato, sez.
VI, sent. n. 1731/2020, ricorso 4232/2019):

    https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema=<sede>&nrg=<ricorso>&nomeFile=<numero>_<tipo>.html&subDir=Provvedimenti

Qui si tiene un archivio proprio (SQLite con indice full-text): gli estremi si caricano dal catalogo OpenGA, poi si
legge il testo un provvedimento alla volta, con pausa fra le richieste, dai più recenti, prima Consiglio di Stato e
Adunanza plenaria. Ogni provvedimento ha il suo stato (da leggere, letto, non disponibile) e i tentativi: la lettura
riprende sempre da dove si era fermata. Si salva il testo della pagina ufficiale, senza aggiunte, con l'indirizzo.
"""
from __future__ import annotations

import hashlib
import html
import re
import sqlite3
import time
import zlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

URL_PROVVEDIMENTO = ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema={schema}&nrg={ricorso}"
                     "&nomeFile={numero}_{codice}.html&subDir=Provvedimenti")
# Codice del tipo di provvedimento nel nome del file ufficiale.
# Verificato per le sentenze (anche brevi) di Consiglio di Stato e CGA; il catalogo OpenGA elenca solo sentenze.
CODICI_TIPO = {"SENTENZA": "11", "SENTENZA BREVE": "11"}
PAUSA = 2.0
TENTATIVI = 3

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS provvedimenti (
        id TEXT PRIMARY KEY, sede TEXT NOT NULL, nome_sede TEXT NOT NULL, schema TEXT NOT NULL, tipo TEXT NOT NULL,
        numero TEXT NOT NULL, anno INTEGER NOT NULL, ricorso TEXT NOT NULL, oggetto TEXT NOT NULL DEFAULT '',
        esito TEXT NOT NULL DEFAULT '', priorita INTEGER NOT NULL DEFAULT 9, url TEXT NOT NULL,
        stato TEXT NOT NULL DEFAULT 'da_leggere', tentativi INTEGER NOT NULL DEFAULT 0, messaggio TEXT NOT NULL DEFAULT '',
        testo_z BLOB, sha256 TEXT NOT NULL DEFAULT '', pubblicato_il TEXT NOT NULL DEFAULT '', letto_il TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS provvedimenti_coda ON provvedimenti (stato, priorita, anno DESC, numero DESC)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS provvedimenti_fts USING fts5(id UNINDEXED, oggetto, testo, "
    "tokenize = 'unicode61 remove_diacritics 2')",
)


def schema_sede(sede: str, nome_sede: str) -> str:
    """Il parametro «schema» del sito: «cds» per il Consiglio di Stato, «cga» per il CGA Sicilia, altrimenti il TAR."""
    nome = nome_sede.upper()
    if "CONSIGLIO DI STATO" in nome or nome.startswith("CDS"):
        return "cds"
    if "CGA" in nome or "GIUSTIZIA AMMINISTRATIVA PER LA REGIONE SICILIANA" in nome:
        return "cga"
    return ""  # TAR: lo schema per sede si aggiunge quando verificato sul sito


def priorita(nome_sede: str) -> int:
    nome = nome_sede.upper()
    if "PLENARIA" in nome:
        return 0
    if "CONSIGLIO DI STATO" in nome or nome.startswith("CDS"):
        return 1
    if "CGA" in nome:
        return 2
    return 5


def testo_della_pagina(contenuto: bytes) -> tuple[str, str]:
    """(testo, data di pubblicazione gg/mm/aaaa) dalla pagina HTML del provvedimento."""
    grezzo = contenuto.decode("utf-8", errors="replace")
    grezzo = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", grezzo)
    grezzo = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", grezzo)
    testo = html.unescape(re.sub(r"<[^>]+>", " ", grezzo))
    righe = [" ".join(r.split()) for r in testo.split("\n")]
    testo = "\n".join(r for r in righe if r)
    pubblicato = re.search(r"Pubblicato il (\d{2}/\d{2}/\d{4})", testo)
    return testo, pubblicato.group(1) if pubblicato else ""


class ArchivioTestiGA:
    def __init__(self, percorso: str | Path, *, sola_lettura: bool = False):
        self.percorso = Path(percorso)
        self.sola_lettura = sola_lettura
        if not sola_lettura:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connetti()) as conn:
                for istruzione in _SCHEMA:
                    conn.execute(istruzione)
                conn.commit()

    def _connetti(self) -> sqlite3.Connection:
        if self.sola_lettura:
            conn = sqlite3.connect(f"file:{self.percorso}?mode=ro", uri=True, timeout=30)
            conn.row_factory = sqlite3.Row
            return conn
        conn = sqlite3.connect(str(self.percorso), timeout=120)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def carica_estremi(self, righe: Iterable[dict[str, Any]]) -> int:
        """Aggiunge gli estremi nuovi dal catalogo OpenGA (solo le sedi con schema verificato)."""
        nuovi = 0
        with closing(self._connetti()) as conn:
            for r in righe:
                schema = schema_sede(str(r["sede"]), str(r["nome_sede"]))
                codice = CODICI_TIPO.get(str(r["tipo"]).upper())
                if not schema or not codice or not str(r.get("ricorso") or "").isdigit():
                    continue
                ident = f"{r['sede']}|{r['tipo']}|{r['anno']}|{r['numero']}"
                url = URL_PROVVEDIMENTO.format(schema=schema, ricorso=r["ricorso"], numero=r["numero"], codice=codice)
                cur = conn.execute(
                    "INSERT OR IGNORE INTO provvedimenti (id, sede, nome_sede, schema, tipo, numero, anno, ricorso, oggetto, "
                    "esito, priorita, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ident, r["sede"], r["nome_sede"], schema, r["tipo"], r["numero"], int(r["anno"]), r["ricorso"],
                     r.get("oggetto") or "", r.get("esito") or "", priorita(str(r["nome_sede"])), url))
                nuovi += cur.rowcount
            conn.commit()
        return nuovi

    def da_leggere(self, limite: int = 50) -> list[dict[str, Any]]:
        with closing(self._connetti()) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, url, oggetto FROM provvedimenti WHERE stato='da_leggere' AND tentativi < ? "
                "ORDER BY priorita, anno DESC, numero DESC LIMIT ?", (TENTATIVI, limite))]

    def salva(self, ident: str, testo: str, pubblicato_il: str, oggetto: str) -> None:
        quando = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with closing(self._connetti()) as conn:
            conn.execute("UPDATE provvedimenti SET stato='letto', testo_z=?, sha256=?, pubblicato_il=?, letto_il=?, messaggio='' "
                         "WHERE id=?", (zlib.compress(testo.encode("utf-8"), 6), hashlib.sha256(testo.encode()).hexdigest(),
                                        pubblicato_il, quando, ident))
            conn.execute("DELETE FROM provvedimenti_fts WHERE id=?", (ident,))
            conn.execute("INSERT INTO provvedimenti_fts (id, oggetto, testo) VALUES (?,?,?)", (ident, oggetto, testo))
            conn.commit()

    def errore(self, ident: str, messaggio: str, *, definitivo: bool = False) -> None:
        with closing(self._connetti()) as conn:
            conn.execute("UPDATE provvedimenti SET tentativi=tentativi+1, messaggio=?, stato=? WHERE id=?",
                         (messaggio[:300], "non_disponibile" if definitivo else "da_leggere", ident))
            conn.commit()

    def conteggi(self) -> dict[str, int]:
        with closing(self._connetti()) as conn:
            return {str(r[0]): int(r[1]) for r in conn.execute("SELECT stato, COUNT(*) FROM provvedimenti GROUP BY stato")}

    def cerca(self, domanda: str, limite: int = 10) -> list[dict[str, Any]]:
        """Provvedimenti con testo che contengono le parole (frasi fra virgolette), i più pertinenti per primi."""
        from pct.gazzetta.archivio import espressione_fts

        espressione = espressione_fts(domanda)[0]
        if not espressione:
            return []
        with closing(self._connetti()) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT p.id, p.nome_sede, p.tipo, p.numero, p.anno, p.ricorso, p.oggetto, p.pubblicato_il, p.url, "
                "snippet(provvedimenti_fts, 2, '«', '»', ' … ', 24) AS brano FROM provvedimenti_fts f "
                "JOIN provvedimenti p ON p.id = f.id WHERE provvedimenti_fts MATCH ? ORDER BY bm25(provvedimenti_fts, 0, 3, 1) "
                "LIMIT ?", (espressione, limite))]


def leggi(archivio: ArchivioTestiGA, *, scarica: Callable[[str], Any], tempo_massimo: float, pausa: float = PAUSA,
          dormi: Callable[[float], None] = time.sleep) -> dict[str, int]:
    """Legge i testi in coda per al più ``tempo_massimo`` secondi."""
    fine = time.monotonic() + tempo_massimo
    esito = {"letti": 0, "errori": 0}
    while time.monotonic() < fine:
        coda = archivio.da_leggere(limite=20)
        if not coda:
            break
        for voce in coda:
            if time.monotonic() >= fine:
                break
            try:
                risposta = scarica(voce["url"])
                codice = int(getattr(risposta, "status_code", 200))
                # Il sito risponde a un provvedimento inesistente con un rinvio a «/visualizza/404.html».
                if codice == 404 or "/404" in str(getattr(risposta, "url", "") or ""):
                    archivio.errore(voce["id"], "pagina del provvedimento non trovata sul sito (404)", definitivo=True)
                    esito["errori"] += 1
                elif codice != 200:
                    archivio.errore(voce["id"], f"risposta {codice}")
                    esito["errori"] += 1
                else:
                    testo, pubblicato = testo_della_pagina(risposta.content or b"")
                    if len(testo) < 300 or "REPUBBLICA ITALIANA" not in testo.upper():
                        archivio.errore(voce["id"], "la pagina non contiene il testo del provvedimento")
                        esito["errori"] += 1
                    else:
                        archivio.salva(voce["id"], testo, pubblicato, voce["oggetto"])
                        esito["letti"] += 1
            except Exception as exc:  # rete: si riprova al giro dopo
                archivio.errore(voce["id"], f"{type(exc).__name__}: {exc}")
                esito["errori"] += 1
            if pausa:
                dormi(pausa)
    return esito


__all__ = ["ArchivioTestiGA", "URL_PROVVEDIMENTO", "leggi", "testo_della_pagina"]
