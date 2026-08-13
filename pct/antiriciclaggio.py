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
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

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
    "trasferimento_immobili": "Trasferimento di diritti reali su beni immobili o attivita' economiche",
    "gestione_denaro": "Gestione di denaro, strumenti finanziari o altri beni",
    "gestione_conti": "Apertura o gestione di conti bancari, libretti o conti titoli",
    "apporti_societari": "Organizzazione degli apporti per costituzione/gestione/amministrazione di societa'",
    "costituzione_enti": "Costituzione, gestione o amministrazione di societa', enti, trust o soggetti analoghi",
    "operazione_finanziaria": "Operazione di natura finanziaria in nome o per conto del cliente",
    "operazione_immobiliare": "Operazione di natura immobiliare in nome o per conto del cliente",
}

# Attivita' esclusa dagli obblighi (art. 17 c.7): difesa e consulenza collegata
# a un procedimento giudiziario.
PRESTAZIONE_DIFENSIVA = "difesa_giudiziale"

# Scala CNF dei punteggi per singolo indice (1-5).
PUNTEGGIO_MIN, PUNTEGGIO_MAX = 1, 5
ETICHETTE_PUNTEGGIO = {
    1: "Rischio pressoche' inesistente",
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
        (MacroArea.CLIENTE, "Trasparenza e collaborazione del cliente (identita', origine dei fondi, motivazioni)"),
        (MacroArea.CLIENTE, "Precedenti, indagini o rapporti con soggetti a rischio"),
        (MacroArea.OPERAZIONE, "Coerenza del prezzo e della struttura dell'operazione con gli standard del settore"),
        (MacroArea.OPERAZIONE, "Tracciabilita' dei pagamenti e origine dichiarata dei fondi"),
        (MacroArea.OPERAZIONE, "Idoneita' dell'operazione a occultare la titolarita' di beni"),
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
    """Repository tenant-aware delle schede di adeguata verifica (JSON)."""

    def __init__(self, db_path: str = "./antiriciclaggio/verifiche.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._verifiche: dict[str, AdeguataVerifica] = {}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._verifiche = {
                chiave: AdeguataVerifica.from_dict(valore)
                for chiave, valore in raw.items()
                if isinstance(valore, dict)
            }
        except (OSError, json.JSONDecodeError, ValueError):
            self._verifiche = {}

    def _salva(self) -> None:
        payload = {chiave: verifica.to_dict() for chiave, verifica in self._verifiche.items()}
        self.db_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    # ----------------------------------------------------------------- CRUD
    def nuova(self, **campi: Any) -> AdeguataVerifica:
        verifica = AdeguataVerifica(**campi)
        if not verifica.indici and verifica.in_ambito:
            verifica.indici = griglia_indici_default()
        self._verifiche[verifica.id] = verifica
        self._salva()
        return verifica

    def get(self, verifica_id: str) -> AdeguataVerifica | None:
        return self._verifiche.get(verifica_id)

    def tutte(self) -> list[AdeguataVerifica]:
        return sorted(self._verifiche.values(), key=lambda v: v.creato_il, reverse=True)

    def per_cliente(self, cliente_id: str) -> list[AdeguataVerifica]:
        return [v for v in self.tutte() if v.cliente_id == cliente_id]

    def aggiorna(self, verifica_id: str, **campi: Any) -> AdeguataVerifica | None:
        verifica = self._verifiche.get(verifica_id)
        if verifica is None:
            return None
        aggiornata = AdeguataVerifica.from_dict({**verifica.to_dict(), **campi, "id": verifica.id})
        aggiornata.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._verifiche[verifica.id] = aggiornata
        self._salva()
        return aggiornata

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
        verifica.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return verifica

    def da_rinnovare(self, oggi: date | None = None) -> list[AdeguataVerifica]:
        """Schede con controllo costante scaduto (art. 18 c.1 lett. d)."""

        scadute = []
        for verifica in self.tutte():
            if verifica.stato == StatoVerifica.COMPLETATA.value and verifica.controllo_scaduto(oggi):
                verifica.stato = StatoVerifica.DA_RINNOVARE.value
                scadute.append(verifica)
        if scadute:
            self._salva()
        return scadute
