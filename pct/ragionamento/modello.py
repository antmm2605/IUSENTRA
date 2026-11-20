"""Il modello tipizzato della causa: atti, eventi, termini, fase, conclusioni e dubbi.

Ogni conclusione del ragionamento segue il contratto chiesto dall'avvocato il 10/11/2026:
cosa si è letto (atto, brano, data), norma applicata (articolo, testo vigente, URL Normattiva),
cosa fare, come farlo, perché, stato (fatto con la prova, da fare, non dovuto con il motivo) e
se siamo nei termini (scadenza calcolata secondo la norma, giorni residui, conseguenze e rimedi).
Un campo che non si può stabilire con certezza non resta vuoto: diventa un `Dubbio` che dice
che cosa manca.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

# Chi ha scritto l'atto.
AUTORI = ("giudice", "studio", "controparte", "cancelleria", "terzo", "ignoto")
# Che rapporto ha l'atto con la causa: della causa, o di contorno (precedenti, stragiudiziali, documenti di prova).
APPARTENENZE = ("causa", "contorno")
STATI = ("fatto", "da_fare", "non_dovuto", "dubbio")


@dataclass(frozen=True)
class Fonte:
    """Che cosa si è letto: l'oggetto del fascicolo, il brano e la data dell'atto."""

    oggetto_id: str
    nome: str = ""
    brano: str = ""
    data: str = ""  # ISO, la data dell'atto da cui il fatto nasce
    tipo: str = "documento"  # documento, pec, allegato_pec, fascicolo, economia


@dataclass(frozen=True)
class EventoCausa:
    tipo: str
    data: str
    descrizione: str
    fonte: Fonte
    stato: str


@dataclass
class Atto:
    """Un documento del fascicolo letto come atto processuale."""

    id: str
    nome: str
    natura: str  # dal catalogo: atto_principale, provvedimento, relata, comunicazione, precedente_giurisprudenziale...
    etichetta: str
    autore: str = "ignoto"
    data: str = ""
    rg: str = ""
    appartenenza: str = "causa"
    motivo_appartenenza: str = ""
    dello_studio: bool = False
    testo: str = ""
    copie: list[str] = field(default_factory=list)  # altri oggetti con lo stesso testo (allegati PEC, depositi)
    sentenza: bool = False
    pubblicazione_pat: str = ""


@dataclass
class Udienza:
    data: str  # ISO
    ora: str = ""
    modalita: str = "presenza"  # presenza, note_scritte, remota, ignota
    fonte: Fonte | None = None
    norme: list[str] = field(default_factory=list)


@dataclass
class TermineAssegnato:
    """Un termine letto in un atto: chi è onerato, se è perentorio, per fare che cosa."""

    scadenza: str  # ISO
    adempimento: str
    onerato: str  # noi, controparte, tutte_le_parti, terzo, giudice, ignoto
    perentorio: bool
    fonte: Fonte
    norme: list[str] = field(default_factory=list)
    conseguenza: str = ""
    ora: str = ""
    # Come si conta: «data» (scritta nel provvedimento), «a_ritroso:N:AAAA-MM-GG» (almeno N giorni prima
    # dell'udienza), «da_comunicazione:N» (N giorni dalla comunicazione del provvedimento).
    formula: str = "data"


@dataclass
class Dubbio:
    """Un punto che le fonti non sciolgono: quale dubbio, che cosa manca, dove guardare."""

    codice: str
    testo: str
    manca: str
    fonte: Fonte | None = None


@dataclass
class Termine:
    """Siamo nei termini? La scadenza calcolata secondo la norma."""

    scadenza: str = ""  # ISO
    decorrenza: str = ""  # ISO, il fatto da cui decorre
    evento_decorrenza: str = ""
    computo: str = ""  # come si è contato (art. 155 c.p.c., a ritroso, giorni liberi...)
    sospensione_feriale: str = ""  # «si applica» / «non si applica (norma)»
    perentorio: bool | None = None
    giorni_residui: int | None = None
    scaduto: bool = False
    conseguenze: str = ""
    rimedi: str = ""
    natura: str = ""  # finestra procedurale o attesa minima, quando non è un termine per adempiere
    ora_assegnata: str = ""  # Ora espressa nel provvedimento, distinta dall'orario dell'udienza.
    data_grezza: str = ""  # ISO, data prima degli aggiustamenti del computo.
    fonti_trasmissione: list[str] = field(default_factory=list)  # Originali PEC che contengono il provvedimento.


@dataclass
class Conclusione:
    """Il contratto di uscita: ogni adempimento, passo, obbligo o termine del ragionamento."""

    codice: str
    cosa: str
    letto: Fonte | None
    norme: list[dict[str, Any]]
    come: str
    perche: str
    stato: str  # fatto, da_fare, non_dovuto, dubbio
    prova_o_motivo: str = ""
    termine: Termine | None = None
    template: str = ""
    guida: str = ""
    onerato: str = "noi"
    dubbi: list[Dubbio] = field(default_factory=list)
    motivo_senza_termine: str = ""
    prova_deposito: dict[str, str] = field(default_factory=dict)
    prova_notifica: dict = field(default_factory=dict)

    def come_dizionario(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Contraddizione:
    """Un controllo di coerenza: che cosa non torna e come è stato sciolto."""

    controllo: str
    descrizione: str
    sciolta: bool
    come: str = ""
    fonte: Fonte | None = None


@dataclass
class Rito:
    codice: str  # cognizione, lavoro, monitorio, esecuzione_mobiliare, esecuzione_immobiliare, volontaria_giurisdizione...
    etichetta: str
    fonte: str  # da dove viene (codice oggetto PST, atti)
    codice_oggetto: str = ""
    area: str = ""
    padre: str = ""  # voce padre del codice oggetto PST
    sospensione_feriale: bool = True
    contro_pa: bool = False
    # Perché la sospensione feriale non si applica, con la norma (pct/ragionamento/feriale): vuoto se si applica.
    motivo_feriale: str = ""


@dataclass
class Causa:
    """Il modello completo: una sola lettura giuridica della pratica, letta da tutte le viste."""

    fascicolo_id: str
    rg: str
    ufficio: str
    ruolo_cliente: str  # attore, convenuto, creditore, debitore, ricorrente, resistente, ignoto
    rito: Rito
    atti: list[Atto]
    udienze: list[Udienza]
    termini: list[TermineAssegnato]
    fase: dict[str, Any]
    conclusioni: list[Conclusione]
    contraddizioni: list[Contraddizione]
    dubbi: list[Dubbio]
    economia: dict[str, Any]
    oggi: date
    impronta: str = ""
    versione: str = ""
    percorso: list[EventoCausa] = field(default_factory=list)
    # Le udienze trascorse il cui esito è scritto in un provvedimento del giudice (udienze_esito).
    esiti_udienze: list[dict[str, str]] = field(default_factory=list)
    # I fascicoli collegati della stessa vicenda, con la prova del collegamento (collegamenti).
    collegati: list[dict[str, Any]] = field(default_factory=list)
    # Controparte, suo difensore e valore della causa letti negli atti (parti), per la testata del fascicolo.
    parti: dict[str, Any] = field(default_factory=dict)

    def come_dizionario(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["oggi"] = self.oggi.isoformat()
        for atto in dati["atti"]:
            atto.pop("testo", None)
        return dati


__all__ = [
    "APPARTENENZE", "AUTORI", "STATI", "Atto", "Causa", "Conclusione", "Contraddizione", "Dubbio", "EventoCausa", "Fonte", "Rito",
    "Termine", "TermineAssegnato", "Udienza",
]
