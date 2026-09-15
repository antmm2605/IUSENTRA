"""Persistenza del registro delle letture (SQLite tenant-aware o PostgreSQL).

Whitelist di tabelle, colonne, filtri e ordinamenti: nessun identificatore
interpolato dall'esterno. Il repository non legge file né avvia letture: dice
che cosa manca e registra che cosa è stato fatto.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .consegne import COLONNE_CONSEGNE, ConsegneMixin
from .fatti_repository import COLONNE_FATTI, FattiMixin
from .lettori import LETTORI, etichetta_lettore, livello_lettore, tipi_lettore, versione_lettore
from .modello import (
    GRAVITA,
    STATI_ANOMALIA,
    STATI_LETTURA,
    TIPI,
    Anomalia,
    Lettura,
    Oggetto,
    StatoFascicolo,
    StatoLettore,
    impronta_inventario,
    impronta_oggetto,
)

SCHEMA_SQLITE = Path(__file__).resolve().parent.parent / "sql" / "20260915_registro_letture.sql"
SCHEMA_POSTGRES = Path(__file__).resolve().parent.parent / "sql" / "20260915_registro_letture_postgres.sql"

TABELLE = ("letture_oggetti", "letture", "letture_fascicoli", "letture_viste", "letture_anomalie", "letture_fatti", "letture_consegne")
_TABELLA_SQL = {tabella: f'"{tabella}"' for tabella in TABELLE}
COLONNE: dict[str, tuple[str, ...]] = {
    "letture_oggetti": (
        "id", "tenant_id", "fascicolo_id", "tipo", "oggetto_id", "nome", "sha256", "sha256_archivio",
        "dimensione", "cliente", "numero_rg", "anno_rg", "origine", "data_oggetto", "presente",
        "censito_il", "aggiornato_il", "rimosso_il",
    ),
    "letture": (
        "id", "tenant_id", "fascicolo_id", "tipo", "oggetto_id", "sha256", "lettore", "versione_lettore",
        "stato", "esito_json", "durata_ms", "letto_il", "aggiornato_il",
    ),
    "letture_fascicoli": (
        "id", "tenant_id", "fascicolo_id", "lettore", "versione_lettore", "impronta", "oggetti_totali",
        "oggetti_letti", "stato", "esito_json", "aggiornato_il",
    ),
    "letture_viste": ("id", "tenant_id", "fascicolo_id", "utente_id", "impronta", "inventario_json", "visto_il"),
    "letture_anomalie": (
        "id", "tenant_id", "fascicolo_id", "tipo", "oggetto_id", "sha256", "lettore", "campo", "valore_letto",
        "valore_proposto", "valore_confermato", "contesto", "motivo", "codice", "gravita", "stato", "creata_il",
        "risolta_il", "risolta_da",
    ),
    "letture_fatti": COLONNE_FATTI,
    "letture_consegne": COLONNE_CONSEGNE,
}
_COLONNA_SQL = {colonna: f'"{colonna}"' for colonne in COLONNE.values() for colonna in colonne}
_FILTRI_SQL = {
    "tenant_id = ? AND fascicolo_id = ?": '"tenant_id" = ? AND "fascicolo_id" = ?',
    "tenant_id = ? AND fascicolo_id = ? AND presente = 1": '"tenant_id" = ? AND "fascicolo_id" = ? AND "presente" = 1',
    "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?": '"tenant_id" = ? AND "fascicolo_id" = ? AND "tipo" = ? AND "oggetto_id" = ?',
    "tenant_id = ? AND tipo = ? AND sha256_archivio = ?": '"tenant_id" = ? AND "tipo" = ? AND "sha256_archivio" = ?',
    "tenant_id = ? AND fascicolo_id = ? AND lettore = ?": '"tenant_id" = ? AND "fascicolo_id" = ? AND "lettore" = ?',
    "tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND lettore = ?": '"tenant_id" = ? AND "tipo" = ? AND "oggetto_id" = ? AND "sha256" = ? AND "lettore" = ?',
    "tenant_id = ? AND fascicolo_id = ? AND utente_id = ?": '"tenant_id" = ? AND "fascicolo_id" = ? AND "utente_id" = ?',
    "tenant_id = ? AND fascicolo_id = ? AND stato = ?": '"tenant_id" = ? AND "fascicolo_id" = ? AND "stato" = ?',
    "tenant_id = ? AND id = ?": '"tenant_id" = ? AND "id" = ?',
    "tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND lettore = ? AND campo = ? AND valore_letto = ?": '"tenant_id" = ? AND "tipo" = ? AND "oggetto_id" = ? AND "sha256" = ? AND "lettore" = ? AND "campo" = ? AND "valore_letto" = ?',
}
_ORDINI_SQL = {
    "aggiornato_il DESC": '"aggiornato_il" DESC',
    "creata_il DESC": '"creata_il" DESC',
    "tipo, nome": '"tipo", "nome"',
}


class RegistroLettureError(ValueError):
    """Errore controllato del registro delle letture."""


def _adesso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _nuovo_id(prefisso: str) -> str:
    return f"{prefisso}_{uuid.uuid4().hex}"


def _json(valore: Any) -> str:
    return json.dumps(valore if valore is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _carica_json(valore: Any, default: Any) -> Any:
    testo = str(valore or "").strip()
    if not testo:
        return default
    try:
        return json.loads(testo)
    except (TypeError, ValueError):
        return default


def _riga(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        return dict(row)
    except Exception:
        return {}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _tipo(valore: str) -> str:
    tipo = _testo(valore)
    if tipo not in TIPI:
        raise RegistroLettureError("Tipo di oggetto non valido.")
    return tipo


def _lettore(valore: str) -> str:
    lettore = _testo(valore)
    if lettore not in LETTORI:
        raise RegistroLettureError("Lettore non censito nel registro.")
    return lettore


class RegistroLetture(FattiMixin, ConsegneMixin):
    """Il registro delle letture di uno studio (con l'archivio dei fatti letti dai motori)."""

    def __init__(self, db_path: str | Path = "", *, postgres_dsn: str = "") -> None:
        self.postgres_dsn = _testo(postgres_dsn)
        self.backend_kind = "postgres" if self.postgres_dsn else "sqlite"
        self.db_path = Path(db_path or "./data/intelligence/registro_letture.db")
        self._pg: PostgresRepositoryBackend | None = None
        if self.postgres_dsn:
            self._pg = PostgresRepositoryBackend(self.postgres_dsn, SCHEMA_POSTGRES)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.executescript(SCHEMA_SQLITE.read_text(encoding="utf-8"))

    # ---- primitive ---------------------------------------------------------

    @staticmethod
    def _adesso() -> str:
        return _adesso()

    @staticmethod
    def _nuovo_id(prefisso: str) -> str:
        return _nuovo_id(prefisso)

    def connection(self):
        if self._pg is not None:
            return self._pg.connection()
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def close(self) -> None:
        if self._pg is not None:
            self._pg.close()

    @staticmethod
    def _tabella(tabella: str) -> str:
        sql = _TABELLA_SQL.get(tabella)
        if not sql:
            raise RegistroLettureError("Tabella non valida.")
        return sql

    @staticmethod
    def _colonne(tabella: str, valori: dict[str, Any]) -> tuple[str, ...]:
        ammesse = COLONNE.get(tabella) or ()
        if not ammesse or any(colonna not in ammesse for colonna in valori):
            raise RegistroLettureError("Colonna non valida.")
        return tuple(colonna for colonna in ammesse if colonna in valori)

    @staticmethod
    def _filtro(filtro: str) -> str:
        sql = _FILTRI_SQL.get(filtro)
        if sql is None:
            raise RegistroLettureError("Filtro non valido.")
        return sql

    def _seleziona(self, tabella: str, filtro: str, parametri: Iterable[Any], *, ordine: str = "") -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {self._tabella(tabella)} WHERE {self._filtro(filtro)}"
        if ordine:
            ordine_sql = _ORDINI_SQL.get(ordine)
            if ordine_sql is None:
                raise RegistroLettureError("Ordinamento non valido.")
            sql += f" ORDER BY {ordine_sql}"
        with self.connection() as conn:
            righe = conn.execute(sql, tuple(parametri)).fetchall()
        return [_riga(riga) for riga in righe]

    def _inserisci(self, conn: Any, tabella: str, valori: dict[str, Any]) -> None:
        colonne = self._colonne(tabella, valori)
        nomi = ", ".join(_COLONNA_SQL[colonna] for colonna in colonne)
        segnaposto = ", ".join("?" for _ in colonne)
        conn.execute(f"INSERT INTO {self._tabella(tabella)} ({nomi}) VALUES ({segnaposto})", tuple(valori[colonna] for colonna in colonne))

    def _aggiorna(self, conn: Any, tabella: str, valori: dict[str, Any], filtro: str, parametri: Iterable[Any]) -> None:
        if not valori:
            return
        colonne = self._colonne(tabella, valori)
        assegnazioni = ", ".join(f"{_COLONNA_SQL[colonna]} = ?" for colonna in colonne)
        conn.execute(
            f"UPDATE {self._tabella(tabella)} SET {assegnazioni} WHERE {self._filtro(filtro)}",
            (*(valori[colonna] for colonna in colonne), *tuple(parametri)),
        )

    def _elimina(self, conn: Any, tabella: str, filtro: str, parametri: Iterable[Any]) -> None:
        conn.execute(f"DELETE FROM {self._tabella(tabella)} WHERE {self._filtro(filtro)}", tuple(parametri))

    # ---- inventario --------------------------------------------------------

    def registra_inventario(self, tenant_id: str, fascicolo_id: str, oggetti: Iterable[Oggetto], *, tipi: Iterable[str] | None = None) -> dict[str, int]:
        """Allinea l'inventario del fascicolo: nuovi, cambiati, invariati, rimossi.

        `tipi` limita l'allineamento ai tipi passati (es. solo documenti): gli
        oggetti di altri tipi già censiti non vengono toccati.
        """
        tenant = _testo(tenant_id)
        fascicolo = _testo(fascicolo_id)
        adesso = _adesso()
        elenco = list(oggetti)
        tipi_gestiti = set(_tipo(tipo) for tipo in (tipi if tipi is not None else {o.tipo for o in elenco}))
        esistenti = {
            (riga["tipo"], riga["oggetto_id"]): riga
            for riga in self._seleziona("letture_oggetti", "tenant_id = ? AND fascicolo_id = ?", (tenant, fascicolo))
        }
        conteggi = {"nuovi": 0, "cambiati": 0, "invariati": 0, "rimossi": 0, "ripristinati": 0}
        visti: set[tuple[str, str]] = set()
        with self.connection() as conn:
            for oggetto in elenco:
                tipo = _tipo(oggetto.tipo)
                chiave = (tipo, _testo(oggetto.oggetto_id))
                if not chiave[1]:
                    continue
                visti.add(chiave)
                valori = {
                    "nome": _testo(oggetto.nome),
                    "sha256": _testo(oggetto.sha256).lower(),
                    "sha256_archivio": _testo(oggetto.sha256_archivio).lower(),
                    "dimensione": int(oggetto.dimensione or 0),
                    "cliente": _testo(oggetto.cliente),
                    "numero_rg": _testo(oggetto.numero_rg),
                    "anno_rg": _testo(oggetto.anno_rg),
                    "origine": _testo(oggetto.origine),
                    "data_oggetto": _testo(oggetto.data_oggetto),
                    "presente": 1,
                    "rimosso_il": "",
                }
                riga = esistenti.get(chiave)
                if riga is None:
                    conteggi["nuovi"] += 1
                    self._inserisci(conn, "letture_oggetti", {
                        "id": _nuovo_id("ogg"), "tenant_id": tenant, "fascicolo_id": fascicolo, "tipo": tipo,
                        "oggetto_id": chiave[1], "censito_il": adesso, "aggiornato_il": adesso, **valori,
                    })
                    continue
                if not int(riga.get("presente") or 0):
                    conteggi["ripristinati"] += 1
                elif impronta_oggetto(riga) != impronta_oggetto(valori):
                    conteggi["cambiati"] += 1
                else:
                    conteggi["invariati"] += 1
                    # Solo i metadati leggeri (nome, cliente, ruolo) possono essere cambiati.
                    if all(str(riga.get(k) or "") == str(v) for k, v in valori.items() if k not in {"presente", "rimosso_il"}):
                        continue
                self._aggiorna(conn, "letture_oggetti", {**valori, "aggiornato_il": adesso},
                               "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?", (tenant, fascicolo, tipo, chiave[1]))
            for chiave, riga in esistenti.items():
                if chiave in visti or chiave[0] not in tipi_gestiti or not int(riga.get("presente") or 0):
                    continue
                conteggi["rimossi"] += 1
                self._aggiorna(conn, "letture_oggetti", {"presente": 0, "rimosso_il": adesso, "aggiornato_il": adesso},
                               "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?", (tenant, fascicolo, chiave[0], chiave[1]))
        return conteggi

    def oggetti(self, tenant_id: str, fascicolo_id: str, *, solo_presenti: bool = True) -> list[Oggetto]:
        filtro = "tenant_id = ? AND fascicolo_id = ? AND presente = 1" if solo_presenti else "tenant_id = ? AND fascicolo_id = ?"
        return [self._oggetto(riga) for riga in self._seleziona("letture_oggetti", filtro, (_testo(tenant_id), _testo(fascicolo_id)), ordine="tipo, nome")]

    @staticmethod
    def _oggetto(riga: dict[str, Any]) -> Oggetto:
        return Oggetto(
            tipo=str(riga.get("tipo") or ""), oggetto_id=str(riga.get("oggetto_id") or ""), nome=str(riga.get("nome") or ""),
            sha256=str(riga.get("sha256") or ""), sha256_archivio=str(riga.get("sha256_archivio") or ""),
            dimensione=int(riga.get("dimensione") or 0), origine=str(riga.get("origine") or ""),
            data_oggetto=str(riga.get("data_oggetto") or ""), cliente=str(riga.get("cliente") or ""),
            numero_rg=str(riga.get("numero_rg") or ""), anno_rg=str(riga.get("anno_rg") or ""),
            presente=bool(int(riga.get("presente") or 0)),
        )

    def oggetto(self, tenant_id: str, fascicolo_id: str, tipo: str, oggetto_id: str) -> Oggetto | None:
        righe = self._seleziona("letture_oggetti", "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?", (_testo(tenant_id), _testo(fascicolo_id), _tipo(tipo), _testo(oggetto_id)))
        return self._oggetto(righe[0]) if righe else None

    def rimuovi_oggetto(self, tenant_id: str, fascicolo_id: str, tipo: str, oggetto_id: str) -> bool:
        adesso = _adesso()
        with self.connection() as conn:
            self._aggiorna(conn, "letture_oggetti", {"presente": 0, "rimosso_il": adesso, "aggiornato_il": adesso},
                           "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?", (_testo(tenant_id), _testo(fascicolo_id), _tipo(tipo), _testo(oggetto_id)))
        return True

    # ---- impronte del contenuto (evita di decifrare per ricalcolare) -----------

    def impronta_contenuto(self, tenant_id: str, tipo: str, sha256_archivio: str) -> str:
        """L'impronta in chiaro già nota per un file conservato; vuota se mai letta."""
        archivio = _testo(sha256_archivio).lower()
        if not archivio:
            return ""
        for riga in self._seleziona("letture_oggetti", "tenant_id = ? AND tipo = ? AND sha256_archivio = ?", (_testo(tenant_id), _tipo(tipo), archivio)):
            sha = _testo(riga.get("sha256")).lower()
            if sha and sha != archivio:
                return sha
        return ""

    def registra_impronta_contenuto(self, tenant_id: str, fascicolo_id: str, tipo: str, oggetto_id: str, *, sha256: str, sha256_archivio: str, dimensione: int = 0) -> None:
        adesso = _adesso()
        valori = {"sha256": _testo(sha256).lower(), "sha256_archivio": _testo(sha256_archivio).lower(), "aggiornato_il": adesso}
        if dimensione:
            valori["dimensione"] = int(dimensione)
        with self.connection() as conn:
            self._aggiorna(conn, "letture_oggetti", valori, "tenant_id = ? AND fascicolo_id = ? AND tipo = ? AND oggetto_id = ?",
                           (_testo(tenant_id), _testo(fascicolo_id), _tipo(tipo), _testo(oggetto_id)))

    # ---- letture -----------------------------------------------------------

    def letture(self, tenant_id: str, fascicolo_id: str, *, lettore: str = "") -> list[Lettura]:
        if lettore:
            righe = self._seleziona("letture", "tenant_id = ? AND fascicolo_id = ? AND lettore = ?", (_testo(tenant_id), _testo(fascicolo_id), _lettore(lettore)))
        else:
            righe = self._seleziona("letture", "tenant_id = ? AND fascicolo_id = ?", (_testo(tenant_id), _testo(fascicolo_id)))
        return [self._lettura(riga) for riga in righe]

    @staticmethod
    def _lettura(riga: dict[str, Any]) -> Lettura:
        return Lettura(
            tipo=str(riga.get("tipo") or ""), oggetto_id=str(riga.get("oggetto_id") or ""), sha256=str(riga.get("sha256") or ""),
            lettore=str(riga.get("lettore") or ""), versione_lettore=str(riga.get("versione_lettore") or ""),
            stato=str(riga.get("stato") or ""), esito=_carica_json(riga.get("esito_json"), {}),
            durata_ms=int(riga.get("durata_ms") or 0), letto_il=str(riga.get("letto_il") or ""),
        )

    def da_leggere(self, tenant_id: str, fascicolo_id: str, lettore: str, *, versione: str | None = None, oggetti: Iterable[Oggetto] | None = None, tipi: Iterable[str] | None = None) -> list[Oggetto]:
        """Gli oggetti presenti che il lettore non ha ancora letto con l'impronta e la versione correnti."""
        lettore = _lettore(lettore)
        versione_corrente = versione if versione is not None else versione_lettore(lettore)
        elenco = list(oggetti) if oggetti is not None else self.oggetti(tenant_id, fascicolo_id)
        tipi_ammessi = {_tipo(t) for t in tipi} if tipi else None
        letti = {
            (l.tipo, l.oggetto_id, l.sha256): l for l in self.letture(tenant_id, fascicolo_id, lettore=lettore)
        }
        mancanti: list[Oggetto] = []
        for oggetto in elenco:
            if not oggetto.presente or (tipi_ammessi and oggetto.tipo not in tipi_ammessi):
                continue
            lettura = letti.get((oggetto.tipo, oggetto.oggetto_id, oggetto.impronta))
            if lettura is None or lettura.stato in {"errore", "in_corso"}:
                mancanti.append(oggetto)
            elif lettura.stato == "letto" and versione_corrente and lettura.versione_lettore != versione_corrente:
                mancanti.append(oggetto)
        return mancanti

    def segna_letto(self, tenant_id: str, fascicolo_id: str, oggetto: Oggetto, lettore: str, *, versione: str | None = None, stato: str = "letto", esito: dict[str, Any] | None = None, durata_ms: int = 0) -> Lettura:
        lettore = _lettore(lettore)
        if stato not in STATI_LETTURA:
            raise RegistroLettureError("Stato di lettura non valido.")
        versione_corrente = versione if versione is not None else versione_lettore(lettore)
        tenant = _testo(tenant_id)
        adesso = _adesso()
        chiave = (tenant, _tipo(oggetto.tipo), _testo(oggetto.oggetto_id), oggetto.impronta, lettore)
        with self.connection() as conn:
            esistente = conn.execute(
                f"SELECT id FROM {self._tabella('letture')} WHERE {self._filtro('tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND lettore = ?')}",
                chiave,
            ).fetchone()
            valori = {
                "fascicolo_id": _testo(fascicolo_id), "versione_lettore": str(versione_corrente or ""), "stato": stato,
                "esito_json": _json(esito or {}), "durata_ms": int(durata_ms or 0), "letto_il": adesso, "aggiornato_il": adesso,
            }
            if esistente:
                self._aggiorna(conn, "letture", valori, "tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND lettore = ?", chiave)
            else:
                self._inserisci(conn, "letture", {
                    "id": _nuovo_id("let"), "tenant_id": tenant, "tipo": chiave[1], "oggetto_id": chiave[2], "sha256": chiave[3], "lettore": lettore, **valori,
                })
        return Lettura(tipo=chiave[1], oggetto_id=chiave[2], sha256=chiave[3], lettore=lettore, versione_lettore=str(versione_corrente or ""), stato=stato, esito=dict(esito or {}), durata_ms=int(durata_ms or 0), letto_il=adesso)

    def segna_letti(self, tenant_id: str, fascicolo_id: str, oggetti: Iterable[Oggetto], lettore: str, *, versione: str | None = None, stato: str = "letto", esito: dict[str, Any] | None = None) -> int:
        conteggio = 0
        for oggetto in oggetti:
            self.segna_letto(tenant_id, fascicolo_id, oggetto, lettore, versione=versione, stato=stato, esito=esito)
            conteggio += 1
        return conteggio

    # ---- stato del fascicolo per lettore -------------------------------------

    def impronta_fascicolo(self, tenant_id: str, fascicolo_id: str, lettore: str) -> dict[str, Any]:
        righe = self._seleziona("letture_fascicoli", "tenant_id = ? AND fascicolo_id = ? AND lettore = ?", (_testo(tenant_id), _testo(fascicolo_id), _lettore(lettore)))
        return righe[0] if righe else {}

    def fascicolo_invariato(self, tenant_id: str, fascicolo_id: str, lettore: str, impronta: str, *, versione: str | None = None) -> bool:
        """Vero se il lettore ha già completato il fascicolo con questa impronta e questa versione."""
        riga = self.impronta_fascicolo(tenant_id, fascicolo_id, lettore)
        if not riga or str(riga.get("stato") or "") != "completa":
            return False
        versione_corrente = versione if versione is not None else versione_lettore(_lettore(lettore))
        return _testo(riga.get("impronta")) == _testo(impronta) and (not versione_corrente or str(riga.get("versione_lettore") or "") == versione_corrente)

    def segna_fascicolo(self, tenant_id: str, fascicolo_id: str, lettore: str, *, impronta: str, oggetti_totali: int, oggetti_letti: int, stato: str = "completa", versione: str | None = None, esito: dict[str, Any] | None = None) -> None:
        lettore = _lettore(lettore)
        if stato not in {"completa", "parziale", "errore"}:
            raise RegistroLettureError("Stato del fascicolo non valido.")
        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        valori = {
            "versione_lettore": str(versione if versione is not None else versione_lettore(lettore)), "impronta": _testo(impronta),
            "oggetti_totali": int(oggetti_totali), "oggetti_letti": int(oggetti_letti), "stato": stato, "esito_json": _json(esito or {}), "aggiornato_il": _adesso(),
        }
        with self.connection() as conn:
            esistente = conn.execute(
                f"SELECT id FROM {self._tabella('letture_fascicoli')} WHERE {self._filtro('tenant_id = ? AND fascicolo_id = ? AND lettore = ?')}", (tenant, fascicolo, lettore)
            ).fetchone()
            if esistente:
                self._aggiorna(conn, "letture_fascicoli", valori, "tenant_id = ? AND fascicolo_id = ? AND lettore = ?", (tenant, fascicolo, lettore))
            else:
                self._inserisci(conn, "letture_fascicoli", {"id": _nuovo_id("lf"), "tenant_id": tenant, "fascicolo_id": fascicolo, "lettore": lettore, **valori})

    def stato_fascicolo(self, tenant_id: str, fascicolo_id: str, *, lettori: Iterable[str] | None = None) -> StatoFascicolo:
        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        oggetti = self.oggetti(tenant, fascicolo)
        letture = self.letture(tenant, fascicolo)
        per_chiave: dict[tuple[str, str, str, str], Lettura] = {(l.tipo, l.oggetto_id, l.sha256, l.lettore): l for l in letture}
        elenco_lettori = [_lettore(l) for l in (lettori if lettori is not None else LETTORI)]
        stati: list[StatoLettore] = []
        per_oggetto: list[dict[str, Any]] = []
        stato_oggetti: dict[tuple[str, str], dict[str, str]] = {(o.tipo, o.oggetto_id): {} for o in oggetti}
        tutto_letto = True
        impronta_corrente = impronta_inventario(oggetti)
        for lettore in elenco_lettori:
            versione = versione_lettore(lettore)
            letti = errori = mancanti = 0
            ultima = ""
            tipi = set(tipi_lettore(lettore))
            propri = [o for o in oggetti if o.tipo in tipi]
            if livello_lettore(lettore) == "fascicolo":
                # Il lettore esamina il fascicolo intero: conta l'impronta dell'ultimo giro completo.
                riga = self.impronta_fascicolo(tenant, fascicolo, lettore)
                impronta_propria = impronta_inventario(propri)
                completa = bool(riga) and str(riga.get("stato") or "") == "completa" and _testo(riga.get("impronta")) in {impronta_propria, impronta_corrente} and (not versione or str(riga.get("versione_lettore") or "") == versione)
                if propri and not completa:
                    tutto_letto = False
                ultima = str(riga.get("aggiornato_il") or "") if riga else ""
                stati.append(StatoLettore(lettore=lettore, etichetta=etichetta_lettore(lettore), versione=versione, letti=len(propri) if completa else 0, da_leggere=0 if completa or not propri else len(propri), errori=0, ultima_lettura=ultima, completa=completa or not propri))
                for oggetto in propri:
                    stato_oggetti[(oggetto.tipo, oggetto.oggetto_id)][lettore] = "letto" if completa else "da_leggere"
                continue
            for oggetto in propri:
                lettura = per_chiave.get((oggetto.tipo, oggetto.oggetto_id, oggetto.impronta, lettore))
                if lettura is None:
                    stato = "da_leggere"
                    mancanti += 1
                elif lettura.stato == "letto" and versione and lettura.versione_lettore != versione:
                    stato = "da_rileggere"
                    mancanti += 1
                elif lettura.stato == "letto":
                    stato = "letto"
                    letti += 1
                    ultima = max(ultima, lettura.letto_il)
                elif lettura.stato == "non_leggibile":
                    stato = "non_leggibile"
                    letti += 1
                else:
                    stato = lettura.stato
                    errori += 1 if lettura.stato == "errore" else 0
                    mancanti += 1 if lettura.stato == "in_corso" else 0
                stato_oggetti[(oggetto.tipo, oggetto.oggetto_id)][lettore] = stato
            completa = mancanti == 0 and errori == 0
            if propri and not completa:
                tutto_letto = False
            stati.append(StatoLettore(lettore=lettore, etichetta=etichetta_lettore(lettore), versione=versione, letti=letti, da_leggere=mancanti, errori=errori, ultima_lettura=ultima, completa=completa))
        for oggetto in oggetti:
            per_oggetto.append({**oggetto.to_dict(), "letture": dict(stato_oggetti[(oggetto.tipo, oggetto.oggetto_id)])})
        anomalie = len(self.anomalie(tenant, fascicolo, stato="aperta"))
        return StatoFascicolo(fascicolo_id=fascicolo, impronta=impronta_inventario(oggetti), oggetti=len(oggetti), lettori=stati, per_oggetto=per_oggetto, anomalie_aperte=anomalie, tutto_letto=tutto_letto)

    # ---- viste dell'avvocato ---------------------------------------------------

    def novita_e_segna_visto(self, tenant_id: str, fascicolo_id: str, utente_id: str, *, segna: bool = True) -> dict[str, Any]:
        """Che cosa è nuovo o cambiato dall'ultima apertura di questo utente; poi registra la vista."""
        tenant, fascicolo, utente = _testo(tenant_id), _testo(fascicolo_id), _testo(utente_id)
        oggetti = self.oggetti(tenant, fascicolo)
        righe = self._seleziona("letture_viste", "tenant_id = ? AND fascicolo_id = ? AND utente_id = ?", (tenant, fascicolo, utente))
        precedente = righe[0] if righe else {}
        visti = {}
        for voce in _carica_json(precedente.get("inventario_json"), []) or []:
            if isinstance(voce, dict):
                visti[(str(voce.get("tipo") or ""), str(voce.get("oggetto_id") or ""))] = str(voce.get("impronta") or "")
        nuovi = [o.to_dict() for o in oggetti if (o.tipo, o.oggetto_id) not in visti]
        cambiati = [o.to_dict() for o in oggetti if (o.tipo, o.oggetto_id) in visti and visti[(o.tipo, o.oggetto_id)] != o.impronta]
        presenti = {(o.tipo, o.oggetto_id) for o in oggetti}
        rimossi = [{"tipo": tipo, "oggetto_id": oggetto_id} for (tipo, oggetto_id) in visti if (tipo, oggetto_id) not in presenti]
        prima_vista = not precedente
        if segna:
            inventario = [{"tipo": o.tipo, "oggetto_id": o.oggetto_id, "impronta": o.impronta} for o in oggetti]
            valori = {"impronta": impronta_inventario(oggetti), "inventario_json": _json(inventario), "visto_il": _adesso()}
            with self.connection() as conn:
                if precedente:
                    self._aggiorna(conn, "letture_viste", valori, "tenant_id = ? AND fascicolo_id = ? AND utente_id = ?", (tenant, fascicolo, utente))
                else:
                    self._inserisci(conn, "letture_viste", {"id": _nuovo_id("vis"), "tenant_id": tenant, "fascicolo_id": fascicolo, "utente_id": utente, **valori})
        return {
            "prima_vista": prima_vista,
            "visto_il": str(precedente.get("visto_il") or ""),
            "nuovi": [] if prima_vista else nuovi,
            "cambiati": cambiati,
            "rimossi": rimossi,
        }

    # ---- anomalie -------------------------------------------------------------

    def registra_anomalie(self, tenant_id: str, fascicolo_id: str, oggetto: Oggetto, lettore: str, anomalie: Iterable[dict[str, Any]]) -> list[Anomalia]:
        """Registra le anomalie di una lettura; quelle già presenti (stesso campo e valore) restano com'erano."""
        lettore = _lettore(lettore)
        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        registrate: list[Anomalia] = []
        adesso = _adesso()
        with self.connection() as conn:
            for voce in anomalie:
                campo = _testo(voce.get("campo"))
                valore = _testo(voce.get("valore_letto"))
                gravita = _testo(voce.get("gravita")) or "media"
                if gravita not in GRAVITA or not campo:
                    continue
                chiave = (tenant, _tipo(oggetto.tipo), _testo(oggetto.oggetto_id), oggetto.impronta, lettore, campo, valore)
                esistente = conn.execute(
                    f"SELECT * FROM {self._tabella('letture_anomalie')} WHERE {self._filtro('tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND lettore = ? AND campo = ? AND valore_letto = ?')}",
                    chiave,
                ).fetchone()
                if esistente:
                    registrate.append(self._anomalia(_riga(esistente)))
                    continue
                riga = {
                    "id": _nuovo_id("ano"), "tenant_id": tenant, "fascicolo_id": fascicolo, "tipo": chiave[1], "oggetto_id": chiave[2],
                    "sha256": chiave[3], "lettore": lettore, "campo": campo, "valore_letto": valore,
                    "valore_proposto": _testo(voce.get("valore_proposto")), "valore_confermato": "", "contesto": _testo(voce.get("contesto"))[:300],
                    "motivo": _testo(voce.get("motivo")) or "Dato da verificare.", "codice": _testo(voce.get("codice")) or "generica",
                    "gravita": gravita, "stato": "aperta", "creata_il": adesso, "risolta_il": "", "risolta_da": "",
                }
                self._inserisci(conn, "letture_anomalie", riga)
                registrate.append(self._anomalia(riga))
        return registrate

    @staticmethod
    def _anomalia(riga: dict[str, Any]) -> Anomalia:
        return Anomalia(
            id=str(riga.get("id") or ""), tipo=str(riga.get("tipo") or ""), oggetto_id=str(riga.get("oggetto_id") or ""),
            sha256=str(riga.get("sha256") or ""), lettore=str(riga.get("lettore") or ""), campo=str(riga.get("campo") or ""),
            valore_letto=str(riga.get("valore_letto") or ""), valore_proposto=str(riga.get("valore_proposto") or ""),
            contesto=str(riga.get("contesto") or ""), motivo=str(riga.get("motivo") or ""), codice=str(riga.get("codice") or ""),
            gravita=str(riga.get("gravita") or ""), stato=str(riga.get("stato") or ""), valore_confermato=str(riga.get("valore_confermato") or ""),
            creata_il=str(riga.get("creata_il") or ""), risolta_il=str(riga.get("risolta_il") or ""), risolta_da=str(riga.get("risolta_da") or ""),
        )

    def anomalie(self, tenant_id: str, fascicolo_id: str, *, stato: str = "") -> list[Anomalia]:
        if stato:
            if stato not in STATI_ANOMALIA:
                raise RegistroLettureError("Stato anomalia non valido.")
            righe = self._seleziona("letture_anomalie", "tenant_id = ? AND fascicolo_id = ? AND stato = ?", (_testo(tenant_id), _testo(fascicolo_id), stato), ordine="creata_il DESC")
        else:
            righe = self._seleziona("letture_anomalie", "tenant_id = ? AND fascicolo_id = ?", (_testo(tenant_id), _testo(fascicolo_id)), ordine="creata_il DESC")
        return [self._anomalia(riga) for riga in righe]

    def risolvi_anomalia(self, tenant_id: str, anomalia_id: str, *, esito: str, utente_id: str, valore: str = "") -> Anomalia:
        """`confermata` (il dato letto è giusto), `corretta` (con il valore giusto) o `ignorata`."""
        if esito not in {"confermata", "corretta", "ignorata"}:
            raise RegistroLettureError("Esito non valido.")
        tenant = _testo(tenant_id)
        righe = self._seleziona("letture_anomalie", "tenant_id = ? AND id = ?", (tenant, _testo(anomalia_id)))
        if not righe:
            raise RegistroLettureError("Anomalia non trovata.")
        riga = righe[0]
        valore_confermato = _testo(valore) if esito == "corretta" else (_testo(riga.get("valore_letto")) if esito == "confermata" else "")
        if esito == "corretta" and not valore_confermato:
            raise RegistroLettureError("Per correggere serve il valore giusto.")
        valori = {"stato": esito, "valore_confermato": valore_confermato, "risolta_il": _adesso(), "risolta_da": _testo(utente_id)}
        with self.connection() as conn:
            self._aggiorna(conn, "letture_anomalie", valori, "tenant_id = ? AND id = ?", (tenant, _testo(anomalia_id)))
        anomalia = self._anomalia({**riga, **valori})
        try:
            self.allinea_fatti_da_anomalia(tenant, anomalia, utente_id=_testo(utente_id))
        except Exception:
            pass
        return anomalia

    def chiudi_anomalie_superate(self, tenant_id: str, fascicolo_id: str, *, contesto: dict[str, Any]) -> list[Anomalia]:
        """Chiude le anomalie aperte che le regole correnti non produrrebbero più.

        La chiusura è registrata, non cancellata: resta il valore letto, il
        contesto e il motivo che dichiara quale regola l'ha superata, con
        l'autore «riconvalida automatica» per distinguerla da una decisione
        dell'avvocato.
        """
        from .riconvalida import AUTORE_RICONVALIDA, anomalie_superate

        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        chiuse: list[Anomalia] = []
        adesso = _adesso()
        superate = anomalie_superate(self.anomalie(tenant, fascicolo, stato="aperta"), contesto=contesto)
        if not superate:
            return chiuse
        with self.connection() as conn:
            for anomalia, motivo in superate:
                valori = {"stato": "ignorata", "motivo": motivo[:600], "risolta_il": adesso, "risolta_da": AUTORE_RICONVALIDA}
                self._aggiorna(conn, "letture_anomalie", valori, "tenant_id = ? AND id = ?", (tenant, anomalia.id))
                chiuse.append(self._anomalia({**anomalia.to_dict(), **valori}))
        return chiuse

    def correzioni(self, tenant_id: str, fascicolo_id: str) -> dict[tuple[str, str, str], str]:
        """Le correzioni dell'avvocato: (oggetto_id, campo, valore_letto) → valore giusto."""
        esito: dict[tuple[str, str, str], str] = {}
        for anomalia in self.anomalie(tenant_id, fascicolo_id):
            if anomalia.stato in {"corretta", "confermata"} and anomalia.valore_confermato:
                esito[(anomalia.oggetto_id, anomalia.campo, anomalia.valore_letto)] = anomalia.valore_confermato
        return esito

    def statistiche(self) -> dict[str, int]:
        conteggi: dict[str, int] = {}
        with self.connection() as conn:
            for tabella in TABELLE:
                riga = conn.execute(f"SELECT COUNT(*) AS n FROM {self._tabella(tabella)}").fetchone()
                conteggi[tabella] = int(_riga(riga).get("n") or 0)
        return conteggi


__all__ = ["COLONNE", "RegistroLetture", "RegistroLettureError", "SCHEMA_POSTGRES", "SCHEMA_SQLITE", "TABELLE"]
