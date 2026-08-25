"""Adeguata verifica della clientela antiriciclaggio per studi legali.

Base normativa: D.Lgs. 231/2007 (artt. 3 c.4 lett. c ambito professionisti;
17-19 adeguata verifica; 20 titolare effettivo; 23 semplificata; 24-25
rafforzata; 31-32 conservazione decennale; 42 astensione) come modificato dai
D.Lgs. 90/2017 e 125/2019; Regole tecniche CNF ex art. 11 c.2 approvate il
20/09/2019 e documento CNF «Criteri e metodologie» (copia versionata in
``docs/specs/ministero/fonti_ufficiali/2026-08-13/``; sintesi operativa in
``docs/specs/ministero/ANTIRICICLAGGIO_CNF_231_2007_2026-08-13.md``).

Il modello CNF e' esemplificativo: macro-aree cliente / operazione / area
geografica, punteggi 1-5 per indice, somma complessiva; le soglie numeriche
NON sono fissate dal CNF, quindi qui sono una prassi di studio configurabile e
il livello calcolato e' sempre un suggerimento — la decisione finale resta
all'avvocato, con motivazione in caso di scostamento (fail-closed: nessun
automatismo sostituisce la valutazione professionale).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pct.transactional_outbox import OutboxEvent, enqueue, ensure_outbox_schema

FONTE_NORMATIVA = (
    "D.Lgs. 231/2007 artt. 17-25, 31; Regole tecniche CNF 20/09/2019; "
    "CNF Criteri e metodologie (fonte versionata 2026-08-13)"
)

# Conservazione ex artt. 31-32 D.Lgs. 231/2007.
ANNI_CONSERVAZIONE = 10


class LivelloVerifica(str, Enum):
    SEMPLIFICATA = "SEMPLIFICATA"  # art. 23 (basso rischio)
    ORDINARIA = "ORDINARIA"        # artt. 18-19
    RAFFORZATA = "RAFFORZATA"      # artt. 24-25 (rischio elevato, PEP, paesi terzi)


class StatoVerifica(str, Enum):
    BOZZA = "BOZZA"
    COMPLETATA = "COMPLETATA"
    DA_RINNOVARE = "DA_RINNOVARE"  # controllo costante scaduto (art. 18 c.1 lett. d)
    FUORI_AMBITO = "FUORI_AMBITO"  # prestazione esclusa (art. 17 c.7 difesa in giudizio)


class MacroArea(str, Enum):
    """Macro-aree degli indici di rischio (CNF Criteri e metodologie)."""

    CLIENTE = "CLIENTE"
    OPERAZIONE = "OPERAZIONE"  # tipologia servizi/operazioni e metodi di pagamento
    AREA_GEOGRAFICA = "AREA_GEOGRAFICA"


# Prestazioni in ambito ex art. 3 c.4 lett. c D.Lgs. 231/2007 (catalogo chiuso).
PRESTAZIONI_IN_AMBITO: dict[str, str] = {
    "trasferimento_immobili": "Trasferimento di diritti reali su beni immobili o attività economiche",
    "gestione_denaro": "Gestione di denaro, strumenti finanziari o altri beni",
    "gestione_conti": "Apertura o gestione di conti bancari, libretti o conti titoli",
    "apporti_societari": "Organizzazione degli apporti per costituzione/gestione/amministrazione di società",
    "costituzione_enti": "Costituzione, gestione o amministrazione di società, enti, trust o soggetti analoghi",
    "operazione_finanziaria": "Operazione di natura finanziaria in nome o per conto del cliente",
    "operazione_immobiliare": "Operazione di natura immobiliare in nome o per conto del cliente",
}

# Attivita' esclusa dagli obblighi (art. 17 c.7): difesa e consulenza collegata
# a un procedimento giudiziario.
PRESTAZIONE_DIFENSIVA = "difesa_giudiziale"

# Scala CNF dei punteggi per singolo indice (1-5).
PUNTEGGIO_MIN, PUNTEGGIO_MAX = 1, 5
ETICHETTE_PUNTEGGIO = {
    1: "Rischio pressoché inesistente",
    2: "Rischio basso",
    3: "Rischio medio/moderato",
    4: "Rischio moderato/alto",
    5: "Rischio elevato e palese",
}

# Soglie di DEFAULT sulla media dei punteggi (1-5). Prassi di studio
# configurabile, NON valori imposti dal CNF (il documento lascia le soglie
# alla procedura di ciascuno studio). Prudenziali: la semplificata scatta solo
# con media molto bassa, la rafforzata gia' da rischio moderato/alto.
SOGLIA_SEMPLIFICATA_DEFAULT = 1.5   # media <= 1.5 → suggerita semplificata
SOGLIA_RAFFORZATA_DEFAULT = 3.5     # media >= 3.5 → suggerita rafforzata

# Rinnovo del controllo costante per livello (prassi configurabile, mesi).
MESI_CONTROLLO_COSTANTE_DEFAULT = {
    LivelloVerifica.SEMPLIFICATA: 36,
    LivelloVerifica.ORDINARIA: 24,
    LivelloVerifica.RAFFORZATA: 12,
}


@dataclass
class IndiceRischio:
    """Un indice della griglia di profilatura (CNF, punteggio 1-5)."""

    macro_area: str
    descrizione: str
    punteggio: int = 1
    note: str = ""

    def normalizzato(self) -> int:
        try:
            valore = int(self.punteggio)
        except (TypeError, ValueError):
            return PUNTEGGIO_MIN
        return min(PUNTEGGIO_MAX, max(PUNTEGGIO_MIN, valore))


@dataclass
class TitolareEffettivo:
    """Titolare effettivo ex art. 20 D.Lgs. 231/2007."""

    nome: str = ""
    codice_fiscale: str = ""
    criterio: str = ""  # proprieta_diretta_25 | proprieta_indiretta_25 | controllo_voti | rappresentanza_legale | coincide_con_cliente
    note: str = ""


@dataclass
class AdeguataVerifica:
    """Scheda di adeguata verifica di un cliente (art. 18 D.Lgs. 231/2007)."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    cliente_id: str = ""
    lead_id: str = ""  # collegamento esplicito all'intake, quando esiste
    fascicolo_id: str = ""
    prestazione: str = ""  # chiave di PRESTAZIONI_IN_AMBITO o PRESTAZIONE_DIFENSIVA
    descrizione_prestazione: str = ""
    scopo_natura: str = ""  # scopo e natura del rapporto (art. 18 c.1 lett. c)
    cliente_pep: bool = False  # persona politicamente esposta (art. 1 c.2 lett. dd)
    paese_alto_rischio: bool = False  # paese terzo ad alto rischio (art. 24)
    titolare_effettivo: Optional[TitolareEffettivo] = None
    indici: list[IndiceRischio] = field(default_factory=list)
    livello_scelto: str = ""  # scelta finale dell'avvocato
    motivazione_scostamento: str = ""  # obbligatoria se diversa dal suggerito
    stato: str = StatoVerifica.BOZZA.value
    operatore: str = ""
    data_verifica: str = ""  # ISO date della conferma
    scadenza_controllo: str = ""  # ISO date del rinnovo controllo costante
    fine_rapporto: str = ""  # ISO date cessazione (per conservazione decennale)
    fonte_normativa: str = FONTE_NORMATIVA
    note: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # ----------------------------------------------------------------- ambito
    @property
    def in_ambito(self) -> bool:
        """False per l'attivita' difensiva pura (art. 17 c.7)."""

        return self.prestazione != PRESTAZIONE_DIFENSIVA

    # ------------------------------------------------------------ valutazione
    @property
    def punteggio_totale(self) -> int:
        return sum(indice.normalizzato() for indice in self.indici)

    @property
    def punteggio_medio(self) -> float:
        if not self.indici:
            return 0.0
        return round(self.punteggio_totale / len(self.indici), 2)

    def livello_suggerito(
        self,
        *,
        soglia_semplificata: float = SOGLIA_SEMPLIFICATA_DEFAULT,
        soglia_rafforzata: float = SOGLIA_RAFFORZATA_DEFAULT,
    ) -> LivelloVerifica:
        """Suggerimento dalla griglia CNF + fattori normativi obbligatori.

        PEP o paese terzo ad alto rischio → sempre rafforzata (artt. 24-25:
        qui non e' prassi ma obbligo). Per il resto decide la media della
        griglia con le soglie di studio.
        """

        if self.cliente_pep or self.paese_alto_rischio:
            return LivelloVerifica.RAFFORZATA
        media = self.punteggio_medio
        if not self.indici:
            return LivelloVerifica.ORDINARIA
        if media >= soglia_rafforzata:
            return LivelloVerifica.RAFFORZATA
        if media <= soglia_semplificata:
            return LivelloVerifica.SEMPLIFICATA
        return LivelloVerifica.ORDINARIA

    # ------------------------------------------------------------ conservazione
    @property
    def conservazione_fino_al(self) -> str:
        """Termine di conservazione decennale ex art. 31 (dalla cessazione)."""

        base = self.fine_rapporto or self.data_verifica
        if not base:
            return ""
        try:
            inizio = date.fromisoformat(base[:10])
        except ValueError:
            return ""
        try:
            return inizio.replace(year=inizio.year + ANNI_CONSERVAZIONE).isoformat()
        except ValueError:  # 29 febbraio
            return inizio.replace(month=2, day=28, year=inizio.year + ANNI_CONSERVAZIONE).isoformat()

    def controllo_scaduto(self, oggi: date | None = None) -> bool:
        if not self.scadenza_controllo:
            return False
        try:
            scadenza = date.fromisoformat(self.scadenza_controllo[:10])
        except ValueError:
            return False
        return (oggi or date.today()) > scadenza

    # ------------------------------------------------------------- serializzazione
    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["in_ambito"] = self.in_ambito
        dati["punteggio_totale"] = self.punteggio_totale
        dati["punteggio_medio"] = self.punteggio_medio
        dati["livello_suggerito"] = self.livello_suggerito().value
        dati["conservazione_fino_al"] = self.conservazione_fino_al
        return dati

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "AdeguataVerifica":
        dati = dict(dati)
        for chiave in ("in_ambito", "punteggio_totale", "punteggio_medio", "livello_suggerito", "conservazione_fino_al"):
            dati.pop(chiave, None)
        titolare = dati.get("titolare_effettivo")
        if isinstance(titolare, dict):
            dati["titolare_effettivo"] = TitolareEffettivo(
                **{k: v for k, v in titolare.items() if k in TitolareEffettivo.__dataclass_fields__}
            )
        indici = dati.get("indici")
        if isinstance(indici, list):
            dati["indici"] = [
                IndiceRischio(**{k: v for k, v in riga.items() if k in IndiceRischio.__dataclass_fields__})
                for riga in indici
                if isinstance(riga, dict)
            ]
        return cls(**{k: v for k, v in dati.items() if k in cls.__dataclass_fields__})


def griglia_indici_default() -> list[IndiceRischio]:
    """Griglia iniziale con le 3 macro-aree del documento CNF (esemplificativa)."""

    voci = [
        (MacroArea.CLIENTE, "Identificazione del titolare effettivo e della struttura del cliente"),
        (MacroArea.CLIENTE, "Trasparenza e collaborazione del cliente (identità, origine dei fondi, motivazioni)"),
        (MacroArea.CLIENTE, "Precedenti, indagini o rapporti con soggetti a rischio"),
        (MacroArea.OPERAZIONE, "Coerenza del prezzo e della struttura dell'operazione con gli standard del settore"),
        (MacroArea.OPERAZIONE, "Tracciabilità dei pagamenti e origine dichiarata dei fondi"),
        (MacroArea.OPERAZIONE, "Idoneità dell'operazione a occultare la titolarità di beni"),
        (MacroArea.AREA_GEOGRAFICA, "Paesi delle parti: sanzioni, embarghi, presidi antiriciclaggio, corruzione"),
    ]
    return [IndiceRischio(macro_area=area.value, descrizione=testo, punteggio=1) for area, testo in voci]


def scadenza_controllo_costante(
    livello: LivelloVerifica,
    *,
    dal_giorno: date | None = None,
    mesi_per_livello: dict[LivelloVerifica, int] | None = None,
) -> str:
    """Data proposta per il rinnovo del controllo costante (prassi di studio)."""

    inizio = dal_giorno or date.today()
    mesi = (mesi_per_livello or MESI_CONTROLLO_COSTANTE_DEFAULT).get(livello, 24)
    return (inizio + timedelta(days=round(mesi * 30.44))).isoformat()


class GestioneAntiriciclaggio:
    """Adeguata verifica tenant-aware, con SQL come unica fonte operativa.

    ``verifiche.json`` viene letto solo per la migrazione iniziale e scritto
    come mirror rigenerabile dopo il commit SQL.  In questo modo una scheda
    AML, i suoi rinnovi, l'evidenza di screening e l'outbox restano atomici
    nel ``studio.db`` del tenant (o nel backend PostgreSQL equivalente).
    """

    _SCREENING_OUTCOMES = {
        "NON_ESEGUITO",
        "NESSUN_RISCONTRO",
        "POTENZIALE_RISCONTRO",
        "NON_DISPONIBILE",
        "ERRORE",
    }

    def __init__(
        self,
        db_path: str = "./antiriciclaggio/verifiche.json",
        *,
        studio_db: Any | None = None,
        tenant_id: str = "studio-locale",
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_id = str(tenant_id or "studio-locale").strip() or "studio-locale"
        self.studio_db = studio_db or self._default_studio_db()
        self._ensure_sql_schema()
        self._bootstrap_sql_from_legacy_mirror()
        self._verifiche = self._load_sql()

    @property
    def source_of_truth(self) -> str:
        return str(getattr(self.studio_db, "backend_kind", "sqlite") or "sqlite")

    def _default_studio_db(self) -> Any:
        from pct.storage import StudioDB

        if self.db_path.parent.name.lower() == "antiriciclaggio":
            return StudioDB.from_data_path(str(self.db_path))
        return StudioDB.get(str(self.db_path.parent / "studio.db"))

    @staticmethod
    def _json(value: Any, default: Any) -> Any:
        if isinstance(value, type(default)):
            return value
        if value in (None, ""):
            return default
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError):
            return default
        return parsed if isinstance(parsed, type(default)) else default

    @staticmethod
    def _row_value(row: Any, key: str, default: Any = "") -> Any:
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if value is None else value

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _ensure_sql_schema(self) -> None:
        filename = "20260824_crm_intake_postgres.sql" if self.source_of_truth == "postgresql" else "20260824_crm_intake.sql"
        script = (Path(__file__).with_name("sql") / filename).read_text(encoding="utf-8")
        if self.source_of_truth == "postgresql":
            with self.studio_db.raw_conn.cursor() as cursor:
                cursor.execute(script)
            self.studio_db.raw_conn.commit()
            ensure_outbox_schema(self.studio_db.conn)
            self.studio_db.raw_conn.commit()
            return
        self.studio_db.conn.executescript(script)
        ensure_outbox_schema(self.studio_db.conn)
        self.studio_db.conn.commit()

    def _commit(self) -> None:
        (getattr(self.studio_db, "raw_conn", None) or self.studio_db.conn).commit()

    def _rollback(self) -> None:
        (getattr(self.studio_db, "raw_conn", None) or self.studio_db.conn).rollback()

    def _load_legacy_mirror(self) -> dict[str, AdeguataVerifica]:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return {}
        return {
            str(key): AdeguataVerifica.from_dict(value)
            for key, value in raw.items()
            if isinstance(value, dict)
        }

    def _load_sql(self) -> dict[str, AdeguataVerifica]:
        rows = self.studio_db.conn.execute(
            "SELECT * FROM aml_verifications ORDER BY creato_il DESC, id DESC"
        ).fetchall()
        result: dict[str, AdeguataVerifica] = {}
        for row in rows:
            payload = self._json(self._row_value(row, "dati_json", "{}"), {})
            payload.update({
                "id": self._row_value(row, "id"),
                "cliente_id": self._row_value(row, "cliente_id"),
                "lead_id": self._row_value(row, "lead_id"),
                "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "prestazione": self._row_value(row, "prestazione"),
                "descrizione_prestazione": self._row_value(row, "descrizione_prestazione"),
                "scopo_natura": self._row_value(row, "scopo_natura"),
                "cliente_pep": bool(self._row_value(row, "cliente_pep", False)),
                "paese_alto_rischio": bool(self._row_value(row, "paese_alto_rischio", False)),
                "titolare_effettivo": self._json(self._row_value(row, "titolare_effettivo_json", "{}"), {}),
                "indici": self._json(self._row_value(row, "indici_json", "[]"), []),
                "livello_scelto": self._row_value(row, "livello_scelto"),
                "motivazione_scostamento": self._row_value(row, "motivazione_scostamento"),
                "stato": self._row_value(row, "stato", StatoVerifica.BOZZA.value),
                "operatore": self._row_value(row, "operatore"),
                "data_verifica": self._row_value(row, "data_verifica"),
                "scadenza_controllo": self._row_value(row, "scadenza_controllo"),
                "fine_rapporto": self._row_value(row, "fine_rapporto"),
                "fonte_normativa": self._row_value(row, "fonte_normativa", FONTE_NORMATIVA),
                "note": self._row_value(row, "note"),
                "creato_il": self._row_value(row, "creato_il"),
                "modificato_il": self._row_value(row, "modificato_il"),
            })
            verifica = AdeguataVerifica.from_dict(payload)
            result[verifica.id] = verifica
        return result

    def _bootstrap_sql_from_legacy_mirror(self) -> None:
        existing = self.studio_db.conn.execute("SELECT 1 FROM aml_verifications LIMIT 1").fetchone()
        if existing:
            return
        legacy = self._load_legacy_mirror()
        if not legacy:
            return
        try:
            for verifica in legacy.values():
                self._write_verifica(verifica, enqueue_event=False)
            self._commit()
        except Exception:
            self._rollback()
            raise

    def _write_legacy_mirror(self) -> None:
        self.db_path.write_text(
            json.dumps({key: verifica.to_dict() for key, verifica in self._verifiche.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def _write_verifica(self, verifica: AdeguataVerifica, *, event_type: str = "", enqueue_event: bool = True) -> int:
        current = self.studio_db.conn.execute(
            "SELECT versione FROM aml_verifications WHERE id = ?", (verifica.id,)
        ).fetchone()
        version = int(self._row_value(current, "versione", 0) or 0) + 1
        payload = verifica.to_dict()
        titolare = verifica.titolare_effettivo
        if isinstance(titolare, TitolareEffettivo):
            titolare = asdict(titolare)
        elif not isinstance(titolare, dict):
            titolare = {}
        indici = [asdict(indice) for indice in verifica.indici]
        self.studio_db.conn.execute(
            """
            INSERT INTO aml_verifications (
                id, cliente_id, lead_id, fascicolo_id, prestazione, descrizione_prestazione,
                scopo_natura, cliente_pep, paese_alto_rischio, titolare_effettivo_json,
                indici_json, livello_scelto, motivazione_scostamento, stato, operatore,
                data_verifica, scadenza_controllo, fine_rapporto, fonte_normativa, note,
                versione, creato_il, modificato_il, dati_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                cliente_id = excluded.cliente_id, lead_id = excluded.lead_id,
                fascicolo_id = excluded.fascicolo_id, prestazione = excluded.prestazione,
                descrizione_prestazione = excluded.descrizione_prestazione,
                scopo_natura = excluded.scopo_natura, cliente_pep = excluded.cliente_pep,
                paese_alto_rischio = excluded.paese_alto_rischio,
                titolare_effettivo_json = excluded.titolare_effettivo_json,
                indici_json = excluded.indici_json, livello_scelto = excluded.livello_scelto,
                motivazione_scostamento = excluded.motivazione_scostamento,
                stato = excluded.stato, operatore = excluded.operatore,
                data_verifica = excluded.data_verifica, scadenza_controllo = excluded.scadenza_controllo,
                fine_rapporto = excluded.fine_rapporto, fonte_normativa = excluded.fonte_normativa,
                note = excluded.note, versione = excluded.versione,
                modificato_il = excluded.modificato_il, dati_json = excluded.dati_json
            """,
            (
                verifica.id, verifica.cliente_id, verifica.lead_id, verifica.fascicolo_id,
                verifica.prestazione, verifica.descrizione_prestazione, verifica.scopo_natura,
                bool(verifica.cliente_pep), bool(verifica.paese_alto_rischio),
                json.dumps(titolare, ensure_ascii=False), json.dumps(indici, ensure_ascii=False),
                verifica.livello_scelto, verifica.motivazione_scostamento, verifica.stato,
                verifica.operatore, verifica.data_verifica, verifica.scadenza_controllo,
                verifica.fine_rapporto, verifica.fonte_normativa, verifica.note, version,
                verifica.creato_il, verifica.modificato_il, json.dumps(payload, ensure_ascii=False),
            ),
        )
        if event_type and enqueue_event:
            enqueue(
                self.studio_db.conn,
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="aml_verification",
                    aggregate_id=verifica.id,
                    aggregate_version=version,
                    event_type=event_type,
                    idempotency_key=f"aml:{verifica.id}:{version}:{event_type}",
                    payload={"verifica_id": verifica.id, "cliente_id": verifica.cliente_id, "stato": verifica.stato},
                    actor_id=verifica.operatore or "sistema",
                ),
            )
        return version

    def _record_audit(self, verifica: AdeguataVerifica, event_type: str, message: str, payload: dict[str, Any]) -> None:
        self.studio_db.conn.execute(
            """
            INSERT INTO aml_audit (id, verifica_id, event_type, actor, message, payload_json, creato_il)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex, verifica.id, event_type, verifica.operatore,
                message, json.dumps(payload, ensure_ascii=False), self._now(),
            ),
        )

    def _persist(self, verifica: AdeguataVerifica, *, event_type: str, message: str) -> AdeguataVerifica:
        try:
            self._write_verifica(verifica, event_type=event_type)
            self._record_audit(verifica, event_type, message, {"stato": verifica.stato})
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._verifiche[verifica.id] = verifica
        self._write_legacy_mirror()
        return verifica

    def _salva(self) -> None:
        """Compatibilità per aggiornamenti manuali della griglia nei moduli esistenti.

        Il salvataggio resta SQL-first e registra un audit esplicito, non un
        write diretto del mirror JSON.
        """

        try:
            for verifica in self._verifiche.values():
                self._write_verifica(verifica, event_type="AML_MANUAL_SAVE")
                self._record_audit(verifica, "AML_MANUAL_SAVE", "Aggiornata griglia AML nel repository SQL.", {})
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._write_legacy_mirror()

    # ----------------------------------------------------------------- CRUD
    def nuova(self, **campi: Any) -> AdeguataVerifica:
        verifica = AdeguataVerifica(**{key: value for key, value in campi.items() if key in AdeguataVerifica.__dataclass_fields__})
        if not verifica.cliente_id:
            raise ValueError("La scheda AML richiede il cliente collegato.")
        if not verifica.indici and verifica.in_ambito:
            verifica.indici = griglia_indici_default()
        return self._persist(verifica, event_type="AML_VERIFICATION_CREATED", message="Creata scheda di adeguata verifica.")

    def get(self, verifica_id: str) -> AdeguataVerifica | None:
        return self._verifiche.get(verifica_id)

    def tutte(self) -> list[AdeguataVerifica]:
        return sorted(self._verifiche.values(), key=lambda v: v.creato_il, reverse=True)

    def per_cliente(self, cliente_id: str) -> list[AdeguataVerifica]:
        return [v for v in self.tutte() if v.cliente_id == cliente_id]

    def per_lead(self, lead_id: str) -> list[AdeguataVerifica]:
        return [v for v in self.tutte() if v.lead_id == lead_id]

    def aggiorna(self, verifica_id: str, **campi: Any) -> AdeguataVerifica | None:
        verifica = self._verifiche.get(verifica_id)
        if verifica is None:
            return None
        aggiornata = AdeguataVerifica.from_dict({**verifica.to_dict(), **campi, "id": verifica.id})
        aggiornata.modificato_il = self._now()
        return self._persist(aggiornata, event_type="AML_VERIFICATION_UPDATED", message="Aggiornata scheda di adeguata verifica.")

    def completa(
        self,
        verifica_id: str,
        *,
        livello_scelto: LivelloVerifica | str,
        operatore: str,
        motivazione_scostamento: str = "",
        oggi: date | None = None,
    ) -> AdeguataVerifica:
        """Conferma dell'avvocato: fissa livello, data, scadenza controllo.

        Se il livello scelto e' meno rigoroso del suggerito serve una
        motivazione (fail-closed: lo scostamento senza motivazione e' errore).
        PEP/paese ad alto rischio non possono scendere sotto la rafforzata
        (obbligo artt. 24-25, non prassi).
        """

        verifica = self._verifiche.get(verifica_id)
        if verifica is None:
            raise KeyError(f"Adeguata verifica {verifica_id} non trovata.")
        if not verifica.in_ambito:
            raise ValueError(
                "Prestazione difensiva ex art. 17 c.7: fuori dagli obblighi di "
                "adeguata verifica, la scheda resta FUORI_AMBITO."
            )
        scelto = LivelloVerifica(str(livello_scelto))
        suggerito = verifica.livello_suggerito()
        rigore = {
            LivelloVerifica.SEMPLIFICATA: 0,
            LivelloVerifica.ORDINARIA: 1,
            LivelloVerifica.RAFFORZATA: 2,
        }
        if (verifica.cliente_pep or verifica.paese_alto_rischio) and scelto != LivelloVerifica.RAFFORZATA:
            raise ValueError(
                "Cliente PEP o paese terzo ad alto rischio: la verifica rafforzata "
                "e' un obbligo (artt. 24-25 D.Lgs. 231/2007), non e' derogabile."
            )
        if rigore[scelto] < rigore[suggerito] and not motivazione_scostamento.strip():
            raise ValueError(
                f"Il livello scelto ({scelto.value}) e' meno rigoroso del suggerito "
                f"({suggerito.value}): serve una motivazione professionale."
            )
        giorno = oggi or date.today()
        verifica.livello_scelto = scelto.value
        verifica.motivazione_scostamento = motivazione_scostamento.strip()
        verifica.operatore = operatore
        verifica.data_verifica = giorno.isoformat()
        verifica.scadenza_controllo = scadenza_controllo_costante(scelto, dal_giorno=giorno)
        verifica.stato = StatoVerifica.COMPLETATA.value
        verifica.modificato_il = self._now()
        return self._persist(
            verifica,
            event_type="AML_VERIFICATION_COMPLETED",
            message="Adeguata verifica confermata dall'avvocato con livello e rinnovo tracciati.",
        )

    def da_rinnovare(self, oggi: date | None = None) -> list[AdeguataVerifica]:
        """Schede con controllo costante scaduto (art. 18 c.1 lett. d)."""

        scadute = []
        for verifica in self.tutte():
            if verifica.stato == StatoVerifica.COMPLETATA.value and verifica.controllo_scaduto(oggi):
                verifica.stato = StatoVerifica.DA_RINNOVARE.value
                verifica.modificato_il = self._now()
                scadute.append(verifica)
        for verifica in scadute:
            self._persist(
                verifica,
                event_type="AML_RENEWAL_DUE",
                message="Controllo costante scaduto: la scheda richiede riesame professionale.",
            )
        return scadute

    # ------------------------------------------------------ fonti e screening
    def registra_evidenza_screening(
        self,
        verifica_id: str,
        *,
        provider_key: str,
        source_url: str,
        source_version: str = "",
        snapshot_hash: str = "",
        subject_label: str = "",
        outcome: str,
        matches: list[dict[str, Any]] | None = None,
        checked_by: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Registra una prova di screening senza fingere un provider.

        Un esito positivo o negativo è ammissibile solo se accompagnato dalla
        fonte ufficiale e dall'hash dello snapshot usato; un provider non
        raggiungibile resta ``NON_DISPONIBILE`` e non può essere trasformato
        silenziosamente in ``NESSUN_RISCONTRO``.
        """

        verifica = self._verifiche.get(verifica_id)
        if verifica is None:
            raise KeyError(f"Adeguata verifica {verifica_id} non trovata.")
        normalized_outcome = str(outcome or "").strip().upper()
        if normalized_outcome not in self._SCREENING_OUTCOMES:
            raise ValueError("Esito screening non valido.")
        provider = str(provider_key or "").strip()
        url = str(source_url or "").strip()
        if not provider or not url:
            raise ValueError("Provider e fonte ufficiale sono obbligatori per lo screening.")
        if normalized_outcome in {"NESSUN_RISCONTRO", "POTENZIALE_RISCONTRO"} and not str(snapshot_hash or "").strip():
            raise ValueError("Un esito di screening richiede l'hash dello snapshot della fonte consultata.")
        checked_at = self._now()
        evidence = {
            "id": uuid.uuid4().hex,
            "verifica_id": verifica.id,
            "provider_key": provider,
            "source_url": url,
            "source_version": str(source_version or "").strip(),
            "snapshot_hash": str(snapshot_hash or "").strip(),
            "subject_label": str(subject_label or "").strip(),
            "outcome": normalized_outcome,
            "matches": [dict(item) for item in (matches or []) if isinstance(item, dict)],
            "checked_by": str(checked_by or verifica.operatore or "").strip(),
            "checked_at": checked_at,
            "note": str(note or "").strip(),
        }
        try:
            self.studio_db.conn.execute(
                """
                INSERT INTO aml_screening_evidence (
                    id, verifica_id, provider_key, source_url, source_version,
                    snapshot_hash, subject_label, outcome, matches_json,
                    checked_by, checked_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence["id"], evidence["verifica_id"], evidence["provider_key"], evidence["source_url"],
                    evidence["source_version"], evidence["snapshot_hash"], evidence["subject_label"], evidence["outcome"],
                    json.dumps(evidence["matches"], ensure_ascii=False), evidence["checked_by"], evidence["checked_at"], evidence["note"],
                ),
            )
            self._record_audit(
                verifica,
                "AML_SCREENING_RECORDED",
                f"Registrato screening {provider}: {normalized_outcome}.",
                {"provider": provider, "outcome": normalized_outcome, "snapshot_hash": evidence["snapshot_hash"]},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return evidence

    def evidenze_screening(self, verifica_id: str) -> list[dict[str, Any]]:
        rows = self.studio_db.conn.execute(
            "SELECT * FROM aml_screening_evidence WHERE verifica_id = ? ORDER BY checked_at DESC, id DESC",
            (verifica_id,),
        ).fetchall()
        return [
            {
                "id": self._row_value(row, "id"),
                "provider_key": self._row_value(row, "provider_key"),
                "source_url": self._row_value(row, "source_url"),
                "source_version": self._row_value(row, "source_version"),
                "snapshot_hash": self._row_value(row, "snapshot_hash"),
                "subject_label": self._row_value(row, "subject_label"),
                "outcome": self._row_value(row, "outcome"),
                "matches": self._json(self._row_value(row, "matches_json", "[]"), []),
                "checked_by": self._row_value(row, "checked_by"),
                "checked_at": self._row_value(row, "checked_at"),
                "note": self._row_value(row, "note"),
            }
            for row in rows
        ]

    def audit(self, verifica_id: str) -> list[dict[str, Any]]:
        rows = self.studio_db.conn.execute(
            "SELECT * FROM aml_audit WHERE verifica_id = ? ORDER BY creato_il DESC, id DESC",
            (verifica_id,),
        ).fetchall()
        return [
            {
                "id": self._row_value(row, "id"),
                "event_type": self._row_value(row, "event_type"),
                "actor": self._row_value(row, "actor"),
                "message": self._row_value(row, "message"),
                "payload": self._json(self._row_value(row, "payload_json", "{}"), {}),
                "creato_il": self._row_value(row, "creato_il"),
            }
            for row in rows
        ]
