"""La materia e il rito del fascicolo dai suoi dati certi.

Un fascicolo giudiziale si riconosce da ciò che lo studio o il portale hanno
già registrato: il tipo di fascicolo, l'ufficio giudiziario, la sezione, il
registro telematico (SICID, SIECIC, SIGP, PAT, PTT) e l'atto introduttivo
riconosciuto dal catalogo documentale. Ogni dato dichiara le materie con cui è
compatibile e, quando la indica, la materia stessa:

- la sezione «Lavoro e previdenza» e il ricorso ex art. 414 c.p.c. indicano il
  rito del lavoro (artt. 409, 413, 414 c.p.c.);
- l'atto di citazione davanti al Tribunale indica il processo ordinario di
  cognizione (art. 163 c.p.c.), davanti al giudice di pace il rito dell'art.
  316 c.p.c.;
- il ricorso al TAR indica il processo amministrativo (artt. 40-41 c.p.a.);
- il ricorso per separazione o divorzio indica il rito delle persone, dei
  minorenni e delle famiglie (art. 473-bis c.p.c.);
- l'ufficio (Tribunale, giudice di pace, TAR, Corte di giustizia tributaria)
  restringe le materie compatibili (artt. 7 e 9 c.p.c.; art. 2 D.Lgs.
  104/2010; art. 2 D.Lgs. 546/1992).

Il rito si imposta da solo solo quando almeno due dati indicano la stessa
materia, nessuno la contraddice e il rito è fissato da un dato preciso (atto
introduttivo, sezione o ufficio specializzato). Altrimenti resta una proposta
da confermare, con le sole alternative della stessa materia.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .profili_rito import RITO_ESECUZIONE, RITO_FAMIGLIA, RITO_LAVORO, RITO_ORDINARIO, RITO_SEMPLIFICATO, RITO_TAR

LAVORO = "lavoro"
FAMIGLIA = "famiglia"
CIVILE = "civile"
GDP = "giudice_di_pace"
AMMINISTRATIVO = "amministrativo"
TRIBUTARIO = "tributario"
PENALE = "penale"
STRAGIUDIZIALE = "stragiudiziale"

ETICHETTE_MATERIA = {
    LAVORO: "lavoro e previdenza",
    FAMIGLIA: "persone, minorenni e famiglie",
    CIVILE: "civile",
    GDP: "giudice di pace",
    AMMINISTRATIVO: "amministrativo",
    TRIBUTARIO: "tributario",
    PENALE: "penale",
    STRAGIUDIZIALE: "stragiudiziale",
}

# Le materie specializzate della giurisdizione civile: indicate insieme a «civile», prevale la specializzata.
_SPECIALIZZATE_CIVILI = {LAVORO, FAMIGLIA, GDP}
_GIURISDIZIONE_ORDINARIA = frozenset({CIVILE, LAVORO, FAMIGLIA, PENALE})

PROFILO_GDP = "PROC_SIGP_GDP_001"
PROFILO_TRIBUTARIO = "PROC_TRIB_RIC_002"


@dataclass(frozen=True)
class Indizio:
    """Un dato certo del fascicolo: da dove viene e quali materie ammette."""

    fonte: str
    compatibili: frozenset[str]
    indica: str = ""
    rito: str = ""


@dataclass
class DatiCerti:
    indizi: list[Indizio] = field(default_factory=list)
    materia: str = ""
    rito: str = ""
    discordanti: bool = False
    giudiziale: bool = False

    @property
    def materie_possibili(self) -> set[str]:
        insiemi = [indizio.compatibili for indizio in self.indizi if indizio.compatibili]
        if not insiemi:
            return set()
        comuni = set(insiemi[0]).intersection(*insiemi[1:])
        return comuni

    @property
    def fonti(self) -> list[str]:
        return [indizio.fonte for indizio in self.indizi]

    @property
    def concordi(self) -> int:
        return sum(1 for indizio in self.indizi if indizio.indica == self.materia)

    @property
    def automatico(self) -> bool:
        return bool(self.materia and self.rito and not self.discordanti and self.concordi >= 2)

    def spiegazione(self) -> str:
        fonti = "; ".join(self.fonti) or "nessun dato del procedimento"
        if self.automatico:
            return f"Profilo impostato dai dati certi del fascicolo: {fonti}."
        if self.discordanti:
            return f"Dati del fascicolo discordanti ({fonti}): scegli il rito fra quelli compatibili."
        if self.rito == RITO_ESECUZIONE:
            return (f"Atto di precetto o di pignoramento nel fascicolo ({fonti}): la pratica è un'esecuzione forzata davanti "
                    "al giudice ordinario dell'esecuzione, qualunque sia il giudice che ha emesso il titolo (artt. 474 ss. "
                    "c.p.c.; art. 115 c.p.a. per le sentenze amministrative): conferma il profilo dell'esecuzione.")
        if self.materia:
            etichetta = ETICHETTE_MATERIA.get(self.materia, self.materia)
            return (f"Materia {etichetta} dai dati del fascicolo ({fonti}), ma il rito non è fissato da un atto introduttivo, "
                    "da una sezione o da un codice oggetto: conferma il rito fra quelli della stessa materia.")
        if self.indizi:
            return f"Dati del fascicolo insufficienti a stabilire la materia ({fonti})."
        return ("Profilo non determinabile: il fascicolo non ha una materia (tipo di fascicolo), un ufficio giudiziario, "
                "una sezione, un registro o un atto introduttivo catalogato da cui dedurre il rito.")


def _piatto(valore: Any) -> str:
    testo = unicodedata.normalize("NFD", str(valore or "").casefold())
    testo = "".join(carattere for carattere in testo if unicodedata.category(carattere) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", testo)).strip()


def _valore(sorgente: Any, *nomi: str) -> str:
    for nome in nomi:
        grezzo = sorgente.get(nome) if isinstance(sorgente, dict) else getattr(sorgente, nome, None)
        grezzo = getattr(grezzo, "value", grezzo)
        testo = str(grezzo or "").strip()
        if testo:
            return testo
    return ""


_TIPI = {
    "LAVORO": Indizio("tipo fascicolo Lavoro", frozenset({LAVORO}), LAVORO),
    "FAMIGLIA": Indizio("tipo fascicolo Famiglia", frozenset({FAMIGLIA}), FAMIGLIA),
    "CIVILE": Indizio("tipo fascicolo Civile", frozenset({CIVILE, LAVORO, FAMIGLIA, GDP}), CIVILE),
    "AMMINISTRATIVO": Indizio("tipo fascicolo Amministrativo", frozenset({AMMINISTRATIVO}), AMMINISTRATIVO),
    "TRIBUTARIO": Indizio("tipo fascicolo Tributario", frozenset({TRIBUTARIO}), TRIBUTARIO),
    "PENALE": Indizio("tipo fascicolo Penale", frozenset({PENALE}), PENALE),
}

# (espressione sul nome dell'ufficio, materie compatibili, materia indicata). L'ordine conta: dal più specifico.
_UFFICI: tuple[tuple[str, frozenset[str], str], ...] = (
    (r"\btribunale per i minorenni\b", frozenset({FAMIGLIA, PENALE}), ""),
    (r"\btribunale di sorveglianza\b|\bprocura\b|\bcorte d ?assise\b|\bgip\b", frozenset({PENALE}), PENALE),
    (r"\bgiudice di pace\b", frozenset({GDP, PENALE}), GDP),
    (r"\btar\b|\btribunale amministrativo\b|\bconsiglio di stato\b", frozenset({AMMINISTRATIVO}), AMMINISTRATIVO),
    (r"\bcorte di giustizia tributaria\b|\bcommissione tributaria\b", frozenset({TRIBUTARIO}), TRIBUTARIO),
    (r"\btribunale\b|\bcorte d ?appello\b", _GIURISDIZIONE_ORDINARIA, ""),
)

_SEZIONI: tuple[tuple[str, frozenset[str], str], ...] = (
    (r"\blavoro\b|\bprevidenza\b", frozenset({LAVORO}), LAVORO),
    (r"\bfamiglia\b|\bpersone\b|\bminorenni\b", frozenset({FAMIGLIA}), FAMIGLIA),
    (r"\bpenale\b|\bgip\b|\bgup\b|\bdibattimento\b|\briesame\b", frozenset({PENALE}), PENALE),
)

_REGISTRI: tuple[tuple[str, frozenset[str], str], ...] = (
    (r"\bsicid\b", frozenset({CIVILE, LAVORO, FAMIGLIA}), ""),
    (r"\bsigp\b", frozenset({GDP}), GDP),
    (r"\bsicp\b|\bpdp\b", frozenset({PENALE}), PENALE),
    (r"\bpat\b|\bsiga\b", frozenset({AMMINISTRATIVO}), AMMINISTRATIVO),
    (r"\bptt\b|\bsigit\b", frozenset({TRIBUTARIO}), TRIBUTARIO),
)

_TITOLI_ESECUTIVI = frozenset({CIVILE, LAVORO, FAMIGLIA, GDP, AMMINISTRATIVO, TRIBUTARIO})

# Atti introduttivi riconosciuti dal catalogo documentale (etichetta della voce) → materia e rito.
ATTI_INTRODUTTIVI: dict[str, tuple[frozenset[str], str, str, str]] = {
    "ricorso in materia di lavoro (art. 414 c.p.c.)": (frozenset({LAVORO}), LAVORO, RITO_LAVORO, "art. 414 c.p.c."),
    "ricorso in materia di previdenza e assistenza (art. 442 c.p.c.)": (frozenset({LAVORO}), LAVORO, RITO_LAVORO, "art. 442 c.p.c."),
    "atto di citazione": (frozenset({CIVILE, GDP}), CIVILE, RITO_ORDINARIO, "art. 163 c.p.c."),
    "ricorso nel procedimento semplificato di cognizione": (frozenset({CIVILE}), CIVILE, RITO_SEMPLIFICATO, "art. 281-undecies c.p.c."),
    "ricorso per separazione o divorzio": (frozenset({FAMIGLIA}), FAMIGLIA, RITO_FAMIGLIA, "art. 473-bis.12 c.p.c."),
    "ricorso per modifica delle condizioni": (frozenset({FAMIGLIA}), FAMIGLIA, RITO_FAMIGLIA, "art. 473-bis.12 c.p.c."),
    "ricorso per affidamento e mantenimento dei figli": (frozenset({FAMIGLIA}), FAMIGLIA, RITO_FAMIGLIA, "art. 473-bis.12 c.p.c."),
    "ricorso al tar": (frozenset({AMMINISTRATIVO}), AMMINISTRATIVO, RITO_TAR, "artt. 40 e 41 c.p.a."),
    "ricorso tributario": (frozenset({TRIBUTARIO}), TRIBUTARIO, PROFILO_TRIBUTARIO, "D.Lgs. 546/1992"),
    # Il titolo esecutivo può venire da ogni giurisdizione (sentenza civile, del lavoro, del TAR: art. 115 c.p.a.),
    # ma precetto e pignoramento aprono sempre l'esecuzione forzata davanti al giudice ordinario.
    "atto di precetto": (_TITOLI_ESECUTIVI, "", RITO_ESECUZIONE, "artt. 474 e 480 c.p.c."),
    "atto di pignoramento": (_TITOLI_ESECUTIVI, "", RITO_ESECUZIONE, "artt. 491 e 543 c.p.c."),
}
_ATTI_ESECUTIVI_NEL_NOME = re.compile(r"\b(atto di precetto|atto di pignoramento)\b")

# Il rito che la materia assume quando un dato specializzato (sezione, ufficio) la fissa senza atto introduttivo.
_RITO_DI_MATERIA = {LAVORO: RITO_LAVORO, GDP: PROFILO_GDP, AMMINISTRATIVO: RITO_TAR, TRIBUTARIO: PROFILO_TRIBUTARIO}


def _primo(regole: tuple[tuple[str, frozenset[str], str], ...], testo: str) -> tuple[frozenset[str], str] | None:
    piatto = _piatto(testo)
    for espressione, compatibili, indica in regole:
        if re.search(espressione, piatto):
            return compatibili, indica
    return None


def _registro_del_profilo_deposito(fascicolo: Any) -> str:
    profilo = getattr(fascicolo, "profilo_deposito", None) if not isinstance(fascicolo, dict) else fascicolo.get("profilo_deposito")
    if not isinstance(profilo, dict):
        return ""
    return _valore(profilo, "registro", "registro_operativo", "registry")


def _etichette_documenti(fascicolo: Any, etichette: Iterable[str]) -> list[str]:
    elenco = [str(etichetta or "") for etichetta in etichette or ()]
    documenti = fascicolo.get("documenti") if isinstance(fascicolo, dict) else getattr(fascicolo, "documenti", None)
    for documento in list(documenti or []):
        if _valore(documento, "tipo").upper() == "CITAZIONE":
            elenco.append("Atto di citazione")
        trovato = _ATTI_ESECUTIVI_NEL_NOME.search(_piatto(_valore(documento, "nome", "nome_file")))
        if trovato:
            elenco.append(trovato.group(1).capitalize())
    return elenco


def deduci_dati_certi(fascicolo: Any, etichette: Iterable[str] = ()) -> DatiCerti:
    """Gli indizi certi del fascicolo, la materia che ne segue e, se fissato, il rito."""
    esito = DatiCerti()
    if fascicolo is None:
        return esito
    tipo = _valore(fascicolo, "tipo", "tipo_fascicolo").upper()
    if tipo in _TIPI:
        esito.indizi.append(_TIPI[tipo])

    ufficio = _valore(fascicolo, "tribunale", "ufficio_giudiziario", "ufficio")
    trovato = _primo(_UFFICI, ufficio) if ufficio else None
    if trovato:
        esito.giudiziale = True
        esito.indizi.append(Indizio(f"ufficio {ufficio}", trovato[0], trovato[1]))

    for campo in ("sezione", "ruolo_sezione"):
        sezione = _valore(fascicolo, campo)
        trovato = _primo(_SEZIONI, sezione) if sezione else None
        if trovato:
            esito.indizi.append(Indizio(f"sezione {sezione}", trovato[0], trovato[1]))
            break

    registro = (_valore(fascicolo, "tipo_registro", "registro_portale", "registro_operativo")
                or _registro_del_profilo_deposito(fascicolo))
    trovato = _primo(_REGISTRI, registro) if registro else None
    if trovato:
        esito.giudiziale = True
        esito.indizi.append(Indizio(f"registro {registro.upper()}", trovato[0], trovato[1]))

    visti: set[str] = set()
    for etichetta in _etichette_documenti(fascicolo, etichette):
        chiave = etichetta.strip().casefold()
        atto = ATTI_INTRODUTTIVI.get(chiave)
        if not atto or chiave in visti:
            continue
        visti.add(chiave)
        compatibili, indica, rito, norma = atto
        natura = "atto esecutivo" if rito == RITO_ESECUZIONE else "atto introduttivo"
        esito.indizi.append(Indizio(f"{natura} «{etichetta.strip()}» ({norma})", compatibili, indica, rito))

    _decidi(esito)
    return esito


def _decidi(esito: DatiCerti) -> None:
    possibili = esito.materie_possibili
    if esito.indizi and not possibili and any(indizio.compatibili for indizio in esito.indizi):
        esito.discordanti = True
        return
    indicate = {indizio.indica for indizio in esito.indizi if indizio.indica and indizio.indica in possibili}
    if indicate & _SPECIALIZZATE_CIVILI:
        indicate.discard(CIVILE)
    if len(indicate) > 1:
        esito.discordanti = True
        return
    if len(indicate) == 1:
        esito.materia = next(iter(indicate))
    elif len(possibili) == 1:
        esito.materia = next(iter(possibili))
    if not esito.materia:
        return
    # Gli indizi che indicano «civile» concordano con la specializzata che li precisa (tipo Civile + sezione Lavoro).
    if esito.materia in _SPECIALIZZATE_CIVILI:
        esito.indizi = [
            Indizio(indizio.fonte, indizio.compatibili, esito.materia, indizio.rito) if indizio.indica == CIVILE else indizio
            for indizio in esito.indizi
        ]
    riti = {indizio.rito for indizio in esito.indizi if indizio.rito and esito.materia in indizio.compatibili}
    if esito.materia == GDP:
        esito.rito = PROFILO_GDP  # davanti al giudice di pace la citazione segue l'art. 316 c.p.c.
    elif len(riti) == 1:
        esito.rito = next(iter(riti))
    elif len(riti) > 1:
        esito.discordanti = True
    elif esito.materia in _RITO_DI_MATERIA and esito.giudiziale:
        esito.rito = _RITO_DI_MATERIA[esito.materia]


def materia_del_profilo(profile: Any) -> str:
    """La materia di un profilo del catalogo, per proporre solo alternative pertinenti."""
    canale = str(getattr(profile, "channel", "") or "").upper()
    tipo = str(getattr(profile, "fascicolo_type", "") or "").upper()
    if canale == "PCT_LAVORO" or tipo == "LAVORO":
        return LAVORO
    if canale in {"SIGP_GDP", "PST_GDP"}:
        return GDP
    if tipo == "FAMIGLIA":
        return FAMIGLIA
    if canale == "PAT_AMMINISTRATIVO" or tipo == "AMMINISTRATIVO":
        return AMMINISTRATIVO
    if canale == "PTT_TRIBUTARIO" or tipo == "TRIBUTARIO":
        return TRIBUTARIO
    if canale == "PDP_PENALE" or tipo == "PENALE":
        return PENALE
    if tipo == "CIVILE":
        return CIVILE
    return STRAGIUDIZIALE


__all__ = [
    "AMMINISTRATIVO", "ATTI_INTRODUTTIVI", "CIVILE", "DatiCerti", "FAMIGLIA", "GDP", "Indizio", "LAVORO", "PENALE",
    "STRAGIUDIZIALE", "TRIBUTARIO", "deduci_dati_certi", "materia_del_profilo",
]
