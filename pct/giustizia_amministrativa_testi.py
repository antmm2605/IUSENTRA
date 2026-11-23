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

from pct.riprove_rete import ReteNonDisponibile, scarica_con_riprove

URL_PROVVEDIMENTO = ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema={schema}&nrg={ricorso}"
                     "&nomeFile={numero}_{codice}.html&subDir=Provvedimenti")
# Codice del tipo di provvedimento nel nome del file ufficiale.
# Codice della sentenza nel nome del file: «11» per Consiglio di Stato e CGA, «01» per i TAR (verificati); il catalogo
# OpenGA elenca solo sentenze.
CODICI_TIPO = {"SENTENZA": "11", "SENTENZA BREVE": "11"}
CODICI_TIPO_TAR = {"SENTENZA": "01", "SENTENZA BREVE": "01"}
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
    "CREATE TABLE IF NOT EXISTS sedi_studio (sede TEXT PRIMARY KEY, da TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL DEFAULT '')",
    "CREATE VIRTUAL TABLE IF NOT EXISTS provvedimenti_fts USING fts5(id UNINDEXED, oggetto, testo, "
    "tokenize = 'unicode61 remove_diacritics 2')",
)


# Sigla del TAR nel parametro «schema» (``tar_<sigla>``), per codice di sede del catalogo OpenGA. Verificata il
# 23/11/2026 sul sito con due sentenze del 2025 per ogni sede (57 testi su 58 aperti; l'altro non pubblicato) e
# sui collegamenti della pagina pubblica (``schema=tar_rm``, ``schema=tar_bs``).
SIGLE_TAR = {"001": "lt", "003": "rm", "004": "aq", "005": "pe", "006": "bz", "007": "pz", "008": "cz", "009": "rc",
             "010": "na", "011": "sa", "012": "bo", "013": "pr", "014": "ts", "015": "ge", "016": "mi", "017": "bs",
             "018": "an", "019": "cb", "020": "to", "021": "ba", "022": "le", "023": "ca", "024": "pa", "025": "ct",
             "026": "fi", "027": "tn", "028": "pg", "029": "ao", "030": "ve"}


# Nome della sede come nel catalogo OpenGA: lato server, mai dal testo scritto dall'utente.
NOMI_SEDE = {
    "001": "TAR LAZIO - LATINA", "002": "CdS GIURISDIZIONALE - ROMA", "003": "TAR LAZIO - ROMA",
    "004": "TAR ABRUZZO - L'AQUILA", "005": "TAR ABRUZZO - PESCARA", "006": "TAR TRENTINO ALTO ADIGE - BOLZANO",
    "007": "TAR BASILICATA - POTENZA", "008": "TAR CALABRIA - CATANZARO", "009": "TAR CALABRIA - REGGIO CALABRIA",
    "010": "TAR CAMPANIA - NAPOLI", "011": "TAR CAMPANIA - SALERNO", "012": "TAR EMILIA-ROMAGNA - BOLOGNA",
    "013": "TAR EMILIA-ROMAGNA - PARMA", "014": "TAR FRIULI VENEZIA GIULIA - TRIESTE", "015": "TAR LIGURIA - GENOVA",
    "016": "TAR LOMBARDIA - MILANO", "017": "TAR LOMBARDIA - BRESCIA", "018": "TAR MARCHE - ANCONA",
    "019": "TAR MOLISE - CAMPOBASSO", "020": "TAR PIEMONTE - TORINO", "021": "TAR PUGLIA - BARI",
    "022": "TAR PUGLIA - LECCE", "023": "TAR SARDEGNA - CAGLIARI", "024": "TAR SICILIA - PALERMO",
    "025": "TAR SICILIA - CATANIA", "026": "TAR TOSCANA - FIRENZE", "027": "TAR TRENTINO ALTO ADIGE - TRENTO",
    "028": "TAR UMBRIA - PERUGIA", "029": "TAR VALLE D'AOSTA - AOSTA", "030": "TAR VENETO - VENEZIA",
    "032": "CGA GIURISDIZIONALE - PALERMO",
}
SEDI_VALIDE = frozenset({"002", "032"} | set(SIGLE_TAR))


def schema_sede(sede: str, nome_sede: str) -> str:
    """Il parametro «schema» del sito: «cds» per il Consiglio di Stato, «cgagiur» per il CGA Sicilia, «tar_<sigla>» per i TAR.

    «cgagiur» verificato il 23/11/2026: con «cga» il sito rinvia sempre a /visualizza/404.html (3 su 3), con «cgagiur»
    apre il testo (3 su 3)."""
    nome = nome_sede.upper()
    if "CONSIGLIO DI STATO" in nome or nome.startswith("CDS"):
        return "cds"
    if "CGA" in nome or "GIUSTIZIA AMMINISTRATIVA PER LA REGIONE SICILIANA" in nome:
        return "cgagiur"
    sigla = SIGLE_TAR.get(str(sede))
    return f"tar_{sigla}" if sigla and nome.startswith("TAR") else ""


# Ordine della coda, deciso dall'avvocato il 23/11/2026: Consiglio di Stato, CGA, TAR Calabria (Catanzaro, Reggio
# Calabria) e TAR Lazio (Roma, competenza funzionale inderogabile per molti atti statali, art. 135 c.p.a.), poi i TAR
# delle sedi dei fascicoli dello studio, poi le altre sedi; prima gli ultimi tre anni; le sentenze brevi in fondo.
TAR_PRIORITARI = frozenset({"008", "009", "003"})
ANNI_RECENTI = 3


def priorita(nome_sede: str, sede: str = "", sedi_studio: Iterable[str] = ()) -> int:
    nome = nome_sede.upper()
    if "PLENARIA" in nome:
        return 0
    if "CONSIGLIO DI STATO" in nome or nome.startswith("CDS"):
        return 1
    if "CGA" in nome:
        return 2
    if str(sede) in TAR_PRIORITARI:
        return 3
    if str(sede) in set(sedi_studio):
        return 4
    return 5


def ordine(nome_sede: str, sede: str, tipo: str, anno: int, *, sedi_studio: Iterable[str] = (),
           anno_corrente: int | None = None) -> int:
    """Chiave della coda (minore = prima): breve, ultimi tre anni, priorità della sede."""
    anno_corrente = anno_corrente or datetime.now(timezone.utc).year
    breve = 1 if "BREVE" in str(tipo).upper() else 0
    vecchia = 0 if int(anno) > anno_corrente - ANNI_RECENTI else 1
    return breve * 100 + vecchia * 10 + priorita(nome_sede, sede, sedi_studio)


# Città e regioni nei nomi degli uffici dei fascicoli → sede TAR (la regione indica la sede principale).
_LUOGHI_TAR = (("LATINA", "001"), ("ROMA", "003"), ("AQUILA", "004"), ("PESCARA", "005"), ("BOLZANO", "006"),
               ("POTENZA", "007"), ("BASILICATA", "007"), ("REGGIO CALABRIA", "009"), ("CATANZARO", "008"),
               ("CALABRIA", "008"), ("SALERNO", "011"), ("NAPOLI", "010"), ("CAMPANIA", "010"), ("PARMA", "013"),
               ("BOLOGNA", "012"), ("EMILIA", "012"), ("TRIESTE", "014"), ("FRIULI", "014"), ("GENOVA", "015"),
               ("LIGURIA", "015"), ("BRESCIA", "017"), ("MILANO", "016"), ("LOMBARDIA", "016"), ("ANCONA", "018"),
               ("MARCHE", "018"), ("CAMPOBASSO", "019"), ("MOLISE", "019"), ("TORINO", "020"), ("PIEMONTE", "020"),
               ("LECCE", "022"), ("BARI", "021"), ("PUGLIA", "021"), ("CAGLIARI", "023"), ("SARDEGNA", "023"),
               ("CATANIA", "025"), ("PALERMO", "024"), ("SICILIA", "024"), ("FIRENZE", "026"), ("TOSCANA", "026"),
               ("TRENTO", "027"), ("PERUGIA", "028"), ("UMBRIA", "028"), ("AOSTA", "029"), ("VENEZIA", "030"),
               ("VENETO", "030"), ("LAZIO", "003"), ("ABRUZZO", "004"))


def sedi_dai_fascicoli(uffici: Iterable[str]) -> set[str]:
    """Le sedi TAR degli uffici dei fascicoli («TAR di Reggio Calabria», «Tribunale amministrativo del Veneto»).

    «Tribunale di Taranto» non è un TAR: serve la parola «TAR» intera o «amministrativo»."""
    sedi = set()
    for ufficio in uffici:
        nome = " ".join(str(ufficio or "").upper().split())
        if not (re.search(r"\bTAR\b", nome) or "AMMINISTRATIV" in nome):
            continue
        sede = next((codice for luogo, codice in _LUOGHI_TAR if re.search(rf"\b{luogo}\b", nome)), "")
        if sede:
            sedi.add(sede)
    return sedi


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


def numero_catalogo(anno: int | str, numero: str) -> str:
    """Il numero come nel catalogo OpenGA: anno e cinque cifre («1234/2025» → «202501234»)."""
    cifre = re.sub(r"\D", "", str(numero))
    if not cifre or len(cifre) > 9:
        return ""
    return cifre if len(cifre) == 9 and cifre.startswith(str(anno)) else f"{int(anno)}{int(cifre):05d}"


class ArchivioTestiGA:
    def __init__(self, percorso: str | Path, *, sola_lettura: bool = False):
        self.percorso = Path(percorso)
        self.sola_lettura = sola_lettura
        if not sola_lettura:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connetti()) as conn:
                for istruzione in _SCHEMA:
                    conn.execute(istruzione)
                colonne = {r[1] for r in conn.execute("PRAGMA table_info(provvedimenti)")}
                if "ordine" not in colonne:
                    conn.execute("ALTER TABLE provvedimenti ADD COLUMN ordine INTEGER NOT NULL DEFAULT 99")
                # 1 = voce aggiunta su richiesta (estremi verificati sul testo ufficiale), in attesa del catalogo.
                if "provvisoria" not in colonne:
                    conn.execute("ALTER TABLE provvedimenti ADD COLUMN provvisoria INTEGER NOT NULL DEFAULT 0")
                conn.execute("CREATE INDEX IF NOT EXISTS provvedimenti_ordine ON provvedimenti "
                             "(stato, ordine, anno DESC, numero DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS provvedimenti_estremi ON provvedimenti (anno, numero)")
                # Correzione dello schema del CGA: le voci con «schema=cga» non si aprono mai sul sito.
                conn.execute("UPDATE provvedimenti SET schema='cgagiur', url=replace(url, 'schema=cga&', 'schema=cgagiur&'), "
                             "stato=CASE WHEN stato='non_disponibile' THEN 'da_leggere' ELSE stato END, "
                             "tentativi=CASE WHEN stato='letto' THEN tentativi ELSE 0 END WHERE schema='cga'")
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

    def valore(self, chiave: str) -> str:
        with closing(self._connetti()) as conn:
            riga = conn.execute("SELECT valore FROM meta WHERE chiave=?", (chiave,)).fetchone()
        return str(riga[0]) if riga else ""

    def imposta_valore(self, chiave: str, valore: str) -> None:
        with closing(self._connetti()) as conn:
            conn.execute("INSERT INTO meta (chiave, valore) VALUES (?, ?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore",
                         (chiave, valore))
            conn.commit()

    def sedi_studio(self) -> set[str]:
        with closing(self._connetti()) as conn:
            return {str(r[0]) for r in conn.execute("SELECT sede FROM sedi_studio")}

    def imposta_sedi_studio(self, sedi: Iterable[str], da: str = "") -> None:
        with closing(self._connetti()) as conn:
            conn.execute("DELETE FROM sedi_studio")
            conn.executemany("INSERT INTO sedi_studio (sede, da) VALUES (?, ?)", [(s, da) for s in sorted(set(sedi))])
            conn.commit()

    def riordina(self, *, anno_corrente: int | None = None) -> int:
        """Ricalcola l'ordine della coda con le sedi dello studio registrate."""
        sedi = self.sedi_studio()
        with closing(self._connetti()) as conn:
            righe = conn.execute("SELECT id, nome_sede, sede, tipo, anno, ordine FROM provvedimenti WHERE stato='da_leggere'").fetchall()
            cambi = [(o, r["id"]) for r in righe
                     if (o := ordine(r["nome_sede"], r["sede"], r["tipo"], r["anno"], sedi_studio=sedi, anno_corrente=anno_corrente)) != r["ordine"]]
            conn.executemany("UPDATE provvedimenti SET ordine=? WHERE id=?", cambi)
            conn.commit()
        return len(cambi)

    def carica_estremi(self, righe: Iterable[dict[str, Any]], *, anno_corrente: int | None = None) -> int:
        """Aggiunge gli estremi nuovi dal catalogo OpenGA (solo le sedi con schema verificato)."""
        nuovi = 0
        sedi = self.sedi_studio()
        with closing(self._connetti()) as conn:
            for r in righe:
                schema = schema_sede(str(r["sede"]), str(r["nome_sede"]))
                codice = (CODICI_TIPO_TAR if schema.startswith("tar_") else CODICI_TIPO).get(str(r["tipo"]).upper())
                if not schema or not codice or not str(r.get("ricorso") or "").isdigit():
                    continue
                ident = f"{r['sede']}|{r['tipo']}|{r['anno']}|{r['numero']}"
                url = URL_PROVVEDIMENTO.format(schema=schema, ricorso=r["ricorso"], numero=r["numero"], codice=codice)
                # Il catalogo prevale sulle voci provvisorie aggiunte su richiesta: ne sostituisce gli estremi.
                cur = conn.execute(
                    "INSERT INTO provvedimenti (id, sede, nome_sede, schema, tipo, numero, anno, ricorso, oggetto, "
                    "esito, priorita, url, ordine) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET nome_sede=excluded.nome_sede, schema=excluded.schema, "
                    "ricorso=excluded.ricorso, oggetto=excluded.oggetto, esito=excluded.esito, priorita=excluded.priorita, "
                    "url=excluded.url, ordine=excluded.ordine, provvisoria=0 WHERE provvedimenti.provvisoria=1",
                    (ident, r["sede"], r["nome_sede"], schema, r["tipo"], r["numero"], int(r["anno"]), r["ricorso"],
                     r.get("oggetto") or "", r.get("esito") or "", priorita(str(r["nome_sede"]), str(r["sede"]), sedi), url,
                     ordine(str(r["nome_sede"]), str(r["sede"]), str(r["tipo"]), int(r["anno"]), sedi_studio=sedi,
                            anno_corrente=anno_corrente)))
                nuovi += cur.rowcount
            conn.commit()
            self._assorbi_provvisorie(conn)
        return nuovi

    @staticmethod
    def _assorbi_provvisorie(conn: sqlite3.Connection) -> None:
        """Voci provvisorie con un'altra chiave (per esempio sentenza breve nel catalogo): il testo passa alla voce del
        catalogo e la provvisoria si elimina."""
        for prov in conn.execute("SELECT * FROM provvedimenti WHERE provvisoria=1").fetchall():
            voce = conn.execute("SELECT id, stato, oggetto FROM provvedimenti WHERE provvisoria=0 AND sede=? AND anno=? "
                                "AND numero=?", (prov["sede"], prov["anno"], prov["numero"])).fetchone()
            if voce is None:
                continue
            if voce["stato"] != "letto" and prov["stato"] == "letto" and prov["testo_z"]:
                conn.execute("UPDATE provvedimenti SET stato='letto', testo_z=?, sha256=?, pubblicato_il=?, letto_il=?, "
                             "messaggio='' WHERE id=?", (prov["testo_z"], prov["sha256"], prov["pubblicato_il"],
                                                         prov["letto_il"], voce["id"]))
                conn.execute("DELETE FROM provvedimenti_fts WHERE id=?", (voce["id"],))
                conn.execute("INSERT INTO provvedimenti_fts (id, oggetto, testo) VALUES (?,?,?)",
                             (voce["id"], voce["oggetto"], zlib.decompress(prov["testo_z"]).decode("utf-8")))
            conn.execute("DELETE FROM provvedimenti_fts WHERE id=?", (prov["id"],))
            conn.execute("DELETE FROM provvedimenti WHERE id=?", (prov["id"],))
        conn.commit()

    def da_leggere(self, limite: int = 50, *, esclusi: Iterable[str] = ()) -> list[dict[str, Any]]:
        esclusi = list(esclusi)
        segnaposto = ",".join("?" * len(esclusi)) or "''"
        with closing(self._connetti()) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, url, oggetto FROM provvedimenti WHERE stato='da_leggere' AND tentativi < ? "
                f"AND id NOT IN ({segnaposto}) ORDER BY ordine, anno DESC, numero DESC LIMIT ?",
                (TENTATIVI, *esclusi, limite))]

    def rinvia(self, ident: str, messaggio: str) -> None:
        """Rete non disponibile: la voce resta da leggere senza consumare tentativi (si ritenta al giro dopo)."""
        with closing(self._connetti()) as conn:
            conn.execute("UPDATE provvedimenti SET messaggio=? WHERE id=?", (f"da ritentare: {messaggio}"[:300], ident))
            conn.commit()

    def salva(self, ident: str, testo: str, pubblicato_il: str, oggetto: str) -> None:
        quando = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with closing(self._connetti()) as conn:
            conn.execute("UPDATE provvedimenti SET stato='letto', testo_z=?, sha256=?, pubblicato_il=?, letto_il=?, messaggio='' "
                         "WHERE id=?", (zlib.compress(testo.encode("utf-8"), 6), hashlib.sha256(testo.encode()).hexdigest(),
                                        pubblicato_il, quando, ident))
            conn.execute("DELETE FROM provvedimenti_fts WHERE id=?", (ident,))
            conn.execute("INSERT INTO provvedimenti_fts (id, oggetto, testo) VALUES (?,?,?)", (ident, oggetto, testo))
            conn.commit()

    def provvedimento(self, ident: str) -> dict[str, Any] | None:
        with closing(self._connetti()) as conn:
            riga = conn.execute("SELECT * FROM provvedimenti WHERE id=?", (ident,)).fetchone()
        if riga is None:
            return None
        dati = {k: riga[k] for k in riga.keys() if k != "testo_z"}  # noqa: SIM118 (sqlite3.Row)
        dati["testo"] = zlib.decompress(riga["testo_z"]).decode("utf-8") if riga["testo_z"] else ""
        return dati

    def trova(self, anno: int, numero: str, sedi: Iterable[str] | None = None) -> list[str]:
        """Gli identificativi con anno e numero di sentenza (n. 1234/2025 = «202501234»), nelle sedi indicate."""
        numero = numero_catalogo(anno, numero)
        if not numero:
            return []
        with closing(self._connetti()) as conn:
            righe = [dict(r) for r in conn.execute("SELECT id, sede, tipo FROM provvedimenti WHERE anno=? AND numero=?",
                                                   (int(anno), numero))]
        if sedi is not None:
            sedi = set(sedi)
            righe = [r for r in righe if r["sede"] in sedi]
        # Una sentenza e la sua forma «breve» non hanno lo stesso numero: in ogni sede il numero è unico.
        return [r["id"] for r in righe]

    def salva_provvisoria(self, sede: str, anno: int, numero: str, ricorso: str, testo: str, pubblicato_il: str) -> str:
        """Una sentenza non ancora nel catalogo importato, letta dal sito ufficiale con estremi riscontrati nel testo.

        La voce resta «provvisoria» finché l'importazione del catalogo non la sostituisce."""
        schema = schema_sede(sede, NOMI_SEDE[sede])
        codice = CODICI_TIPO_TAR["SENTENZA"] if schema.startswith("tar_") else CODICI_TIPO["SENTENZA"]
        ident = f"{sede}|SENTENZA|{anno}|{numero}"
        url = URL_PROVVEDIMENTO.format(schema=schema, ricorso=ricorso, numero=numero, codice=codice)
        sedi = self.sedi_studio()
        with closing(self._connetti()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO provvedimenti (id, sede, nome_sede, schema, tipo, numero, anno, ricorso, priorita, url, "
                "ordine, provvisoria) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                (ident, sede, NOMI_SEDE[sede], schema, "SENTENZA", numero, int(anno), ricorso,
                 priorita(NOMI_SEDE[sede], sede, sedi), url, ordine(NOMI_SEDE[sede], sede, "SENTENZA", int(anno), sedi_studio=sedi)))
            conn.commit()
        self.salva(ident, testo, pubblicato_il, "")
        return ident

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


TEMPO_SU_RICHIESTA = 15.0


def leggi_subito(archivio: ArchivioTestiGA, ident: str, *, scarica: Callable[..., Any],
                 tempo_massimo: float = TEMPO_SU_RICHIESTA) -> dict[str, Any]:
    """Il testo di un provvedimento chiesto ora dall'avvocato: dall'archivio o, se manca, subito dal sito ufficiale.

    Esito: ``{"ok", "testo", "fonte", "url", "messaggio"}``; il testo letto si salva nell'archivio per le volte dopo."""
    voce = archivio.provvedimento(ident)
    if voce is None:
        return {"ok": False, "testo": "", "url": "", "messaggio": "Provvedimento non riconosciuto: mancano sede, numero o ricorso."}
    if voce["stato"] == "letto" and voce["testo"]:
        return {"ok": True, "testo": voce["testo"], "url": voce["url"], "fonte": "archivio", "pubblicato_il": voce["pubblicato_il"], "messaggio": ""}
    try:
        risposta = scarica(voce["url"], timeout=tempo_massimo)
    except Exception as exc:  # rete o tempo scaduto: si riprova al giro dopo, l'avvocato lo sa subito
        archivio.errore(ident, f"{type(exc).__name__}: {exc}")
        return {"ok": False, "testo": "", "url": voce["url"],
                "messaggio": f"Il sito della Giustizia amministrativa non ha risposto entro {tempo_massimo:.0f} secondi: "
                             "riprova fra poco o apri il testo sul sito ufficiale."}
    if int(getattr(risposta, "status_code", 200)) == 404 or "/404" in str(getattr(risposta, "url", "") or ""):
        archivio.errore(ident, "pagina del provvedimento non trovata sul sito (404)", definitivo=True)
        return {"ok": False, "testo": "", "url": voce["url"],
                "messaggio": "Il testo di questa sentenza non è pubblicato sul sito della Giustizia amministrativa "
                             "(può essere recente o non ancora depositato in forma pubblica)."}
    testo, pubblicato = testo_della_pagina(risposta.content or b"")
    if int(getattr(risposta, "status_code", 200)) != 200 or len(testo) < 300 or "REPUBBLICA ITALIANA" not in testo.upper():
        archivio.errore(ident, "la pagina non contiene il testo del provvedimento")
        return {"ok": False, "testo": "", "url": voce["url"],
                "messaggio": "La pagina del sito non contiene il testo della sentenza: aprila sul sito ufficiale."}
    archivio.salva(ident, testo, pubblicato, voce["oggetto"])
    return {"ok": True, "testo": testo, "url": voce["url"], "fonte": "sito ufficiale, letto ora", "pubblicato_il": pubblicato, "messaggio": ""}


def scarica_ufficiale(url: str, *, timeout: float = TEMPO_SU_RICHIESTA):
    import requests

    return requests.get(url, timeout=(min(5.0, timeout), timeout), allow_redirects=True,
                        headers={"User-Agent": "IUSENTRA archivio giurisprudenza (consultazione professionale)"})


def sedi_dell_organo(organo: str) -> set[str] | None:
    """Le sedi del catalogo per l'organo scritto dall'avvocato; ``None`` se l'organo non è indicato."""
    nome = " ".join(str(organo or "").upper().split())
    if not nome:
        return None
    if "CONSIGLIO DI STATO" in nome or re.search(r"\bCDS\b|CONS\.? ?STATO", nome):
        return {"002"}
    if "CGA" in nome or "GIUSTIZIA AMMINISTRATIVA PER LA REGIONE SICILIANA" in nome or "CONSIGLIO DI GIUSTIZIA" in nome:
        return {"032"}
    sedi = sedi_dai_fascicoli([nome])
    if sedi:
        # «TAR Calabria» indica la sede di Catanzaro; «Reggio Calabria» è la sezione staccata, già distinta.
        return sedi
    return set(SIGLE_TAR) if re.search(r"\bTAR\b|AMMINISTRATIV", nome) else None


def estremi_nel_testo(testo: str, numero: str, ricorso: str) -> bool:
    """Il testo ufficiale riporta il numero della sentenza («N. 01731/2025 REG.PROV.COLL.») e del ricorso (« REG.RIC.»)."""
    def presente(valore: str, registro: str) -> bool:
        return bool(re.search(rf"N\.\s*0*{int(valore[4:])}/{valore[:4]}\s*{registro}", testo))
    return (len(numero) == 9 and len(ricorso) == 9 and ricorso.isdigit()
            and presente(numero, r"REG\.?\s*PROV\.?\s*COLL") and presente(ricorso, r"REG\.?\s*RIC"))


def estremi_dal_catalogo(catalogo: str | Path | None, anno: int, numero: str, sedi: set[str] | None) -> list[dict[str, Any]]:
    """Le sentenze con quell'anno e numero nel catalogo OpenGA (sola lettura); vuoto se il catalogo non c'è."""
    if not catalogo or not Path(catalogo).is_file():
        return []
    conn = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        righe = [dict(r) for r in conn.execute(
            "SELECT sede, nome_sede, tipo, numero, anno, ricorso, oggetto, esito_originale AS esito FROM righe "
            "WHERE anno=? AND numero=? AND tipo LIKE 'SENTENZA%'", (int(anno), numero))]
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [r for r in righe if sedi is None or str(r["sede"]) in sedi]


def _esito(messaggio: str, **altro: Any) -> dict[str, Any]:
    return {"ok": False, "testo": "", "url": "", "messaggio": messaggio, **altro}


def testo_su_richiesta(archivio: ArchivioTestiGA, *, anno: int | str, numero: str, organo: str = "", sede: str = "",
                       ricorso: str = "", scarica: Callable[..., Any] | None = None, catalogo: str | Path | None = None,
                       tempo_massimo: float = TEMPO_SU_RICHIESTA, **_ignorati: Any) -> dict[str, Any]:
    """Il testo di una sentenza amministrativa chiesta ora (ricerca, fascicolo, Lex), letta subito se manca.

    Sede, nome della sede e schema si ricavano lato server. Una sentenza assente dall'archivio entra solo se è nel
    catalogo OpenGA o se il testo scaricato dal sito ufficiale riporta gli stessi numeri di sentenza e di ricorso;
    altrimenti non si scrive nulla."""
    try:
        anno = int(str(anno).strip())
    except ValueError:
        return _esito("Anno della sentenza non valido.")
    numero9 = numero_catalogo(anno, numero)
    if not numero9 or not 1990 <= anno <= 2100:
        return _esito("Numero o anno della sentenza non validi.")
    sede = str(sede or "").strip()
    sedi_organo = sedi_dell_organo(organo)
    if sede:
        if sede not in SEDI_VALIDE:
            return _esito("Sede non riconosciuta: indica il Consiglio di Stato, il CGA o un TAR.")
        if sedi_organo is not None and sede not in sedi_organo:
            return _esito(f"L'organo indicato non corrisponde alla sede {NOMI_SEDE[sede]}: controlla gli estremi.")
        sedi: set[str] | None = {sede}
    else:
        sedi = sedi_organo
    scarica = scarica or scarica_ufficiale
    trovati = archivio.trova(anno, numero9, sedi)
    if not trovati:
        dal_catalogo = estremi_dal_catalogo(catalogo, anno, numero9, sedi)
        if ricorso:
            dal_catalogo = [r for r in dal_catalogo if str(r["ricorso"]) == str(ricorso)] or dal_catalogo
        if dal_catalogo:
            archivio.carica_estremi(dal_catalogo)
            trovati = archivio.trova(anno, numero9, sedi)
    if not trovati and sedi and len(sedi) == 1 and str(ricorso).isdigit() and len(str(ricorso)) == 9:
        return _leggi_provvisoria(archivio, next(iter(sedi)), anno, numero9, str(ricorso), scarica, tempo_massimo)
    if not trovati:
        return _esito(f"La sentenza n. {numero}/{anno} non è nel catalogo della Giustizia amministrativa importato: "
                      "controlla numero, anno e sede, oppure cercala sul sito ufficiale.")
    if len(trovati) > 1:
        return _esito(f"Il n. {numero}/{anno} esiste in {len(trovati)} sedi: indica il TAR (per esempio «TAR Lazio»).",
                      candidati=trovati)
    return {"id": trovati[0], **leggi_subito(archivio, trovati[0], scarica=scarica, tempo_massimo=tempo_massimo)}


def _leggi_provvisoria(archivio: ArchivioTestiGA, sede: str, anno: int, numero: str, ricorso: str,
                       scarica: Callable[..., Any], tempo_massimo: float) -> dict[str, Any]:
    """Estremi non ancora nel catalogo: si scarica dal sito e si salva solo se il testo riporta gli stessi numeri."""
    schema = schema_sede(sede, NOMI_SEDE[sede])
    codice = CODICI_TIPO_TAR["SENTENZA"] if schema.startswith("tar_") else CODICI_TIPO["SENTENZA"]
    url = URL_PROVVEDIMENTO.format(schema=schema, ricorso=ricorso, numero=numero, codice=codice)
    try:
        risposta = scarica(url, timeout=tempo_massimo)
    except Exception:  # rete o tempo scaduto: nessuna scrittura
        return _esito(f"Il sito della Giustizia amministrativa non ha risposto entro {tempo_massimo:.0f} secondi: "
                      "riprova fra poco o apri il testo sul sito ufficiale.", url=url)
    if int(getattr(risposta, "status_code", 200)) != 200 or "/404" in str(getattr(risposta, "url", "") or ""):
        return _esito("Il testo di questa sentenza non è pubblicato sul sito della Giustizia amministrativa con questi "
                      "estremi: controlla numero, anno, sede e numero di ricorso.", url=url)
    testo, pubblicato = testo_della_pagina(risposta.content or b"")
    if "REPUBBLICA ITALIANA" not in testo.upper() or not estremi_nel_testo(testo, numero, ricorso):
        return _esito("La pagina del sito non riporta gli estremi indicati (numero di sentenza e di ricorso): "
                      "non è stata salvata.", url=url)
    ident = archivio.salva_provvisoria(sede, anno, numero, ricorso, testo, pubblicato)
    return {"ok": True, "id": ident, "testo": testo, "url": url, "fonte": "sito ufficiale, letto ora",
            "pubblicato_il": pubblicato, "messaggio": ""}


def leggi(archivio: ArchivioTestiGA, *, scarica: Callable[[str], Any], tempo_massimo: float, pausa: float = PAUSA,
          dormi: Callable[[float], None] = time.sleep) -> dict[str, int]:
    """Legge i testi in coda per al più ``tempo_massimo`` secondi."""
    fine = time.monotonic() + tempo_massimo
    esito = {"letti": 0, "errori": 0, "da_ritentare": 0}
    rinviati: set[str] = set()
    while time.monotonic() < fine:
        coda = archivio.da_leggere(limite=20, esclusi=rinviati)
        if not coda:
            break
        for voce in coda:
            if time.monotonic() >= fine:
                break
            try:
                # Timeout ed errori di rete: due riprove con attesa crescente, poi la voce resta da ritentare.
                risposta = scarica_con_riprove(scarica, voce["url"], dormi=dormi)
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
            except ReteNonDisponibile as exc:
                # Sito lento o irraggiungibile anche dopo le riprove: da ritentare, si passa alla successiva.
                archivio.rinvia(voce["id"], str(exc))
                rinviati.add(voce["id"])
                esito["da_ritentare"] += 1
            except Exception as exc:
                archivio.errore(voce["id"], f"{type(exc).__name__}: {exc}")
                esito["errori"] += 1
            if pausa:
                dormi(pausa)
    return esito


__all__ = ["NOMI_SEDE", "SEDI_VALIDE", "URL_PROVVEDIMENTO", "ArchivioTestiGA", "estremi_dal_catalogo", "estremi_nel_testo", "leggi", "leggi_subito", "numero_catalogo", "ordine", "scarica_ufficiale",
           "sedi_dai_fascicoli", "sedi_dell_organo", "testo_della_pagina", "testo_su_richiesta"]
