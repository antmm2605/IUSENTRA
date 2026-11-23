"""Passo 1 dell'harness: capire che cosa chiede l'avvocato, prima di qualsiasi ricerca operativa.

Il tipo di richiesta si decide sulla forma della domanda giuridica, non su parole isolate: in un racconto di fatti
«oggi», «termine», «PEC» o «parte» descrivono la vicenda e non chiedono l'elenco delle PEC dello studio.
Tipi: «redazione» (scrivi l'atto), «parere» (cosa fare, rito, giudice, procedibilità), «termine» (entro quando),
«norma» (testo di un articolo), «operativa» (dati dello studio: scadenze, PEC, agenda, clienti).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .norme import piano

# Atti che l'avvocato chiede di redigere (ordine: dal più specifico).
ATTI: tuple[tuple[str, str], ...] = (
    ("opposizione a ordinanza-ingiunzione", r"opposizion\w*.{0,60}ordinanza[- ]ingiunzion|ordinanza[- ]ingiunzion"),
    ("opposizione a decreto ingiuntivo", r"opposizion\w*.{0,60}(?:decreto ingiuntivo|(?<!ordinanza-)(?<!ordinanza )ingiunzione)"),
    ("opposizione a precetto", r"opposizion\w*.{0,60}precett|precett.{0,80}\bopposizion"),
    ("opposizione alla convalida di sfratto", r"opposizion\w*.{0,40}convalida"),
    ("memoria", r"\bmemori[ae]\b"),
    ("ricorso per decreto ingiuntivo", r"ricorso (?:per|di) (?:decreto )?ingiuntiv|(?:decreto|ingiunzione) ingiuntiv|decreto ingiuntivo|ricorso monitorio"),
    ("intimazione di sfratto", r"intimazione di sfratto|sfratto per morosita|atto di sfratto|\bsfratto\b"),
    ("ricorso per separazione o divorzio", r"ricorso (?:per|di) (?:separazione|divorzio)|separazione giudiziale|divorzio giudiziale"),
    ("ricorso nel rito del lavoro", r"ricorso.{0,60}(?:lavor|retribu|licenzia|tfr)|(?:lavor|licenzia).{0,40}\bricorso\b"),
    ("comparsa di costituzione e risposta", r"comparsa(?: di costituzione)?(?: e risposta)?"),
    ("atto di precetto", r"(?:atto di )?precetto"),
    ("atto di appello", r"atto di appello|\bappello\b"),
    ("atto di citazione", r"atto di citazione|\bcitazione\b"),
    ("diffida", r"diffida|messa in mora|costituzione in mora"),
    ("memoria", r"\bmemori[ae]\b"),
    ("ricorso", r"\bricorso\b"),
    ("querela", r"\bquerela\b"),
)
_VERBI_REDAZIONE = (r"\b(?:redig\w*|rediger\w*|scriv\w*|prepar\w*|predispo\w*|stend\w*|compil\w*|imposta\w*|elabor\w*|"
                    r"fammi|mi serve (?:una |la |un )?(?:bozza|atto)|bozza (?:di|del|dell|della|per))\b")
# Una questione si pone con una domanda o una richiesta, non con un'etichetta («Organismo di mediazione attivo»).
_FORMA_DOMANDA = (r"\?|\b(?:qual\w*|quando|quanto|come|cosa|perche|chi|dove|entro|posso|possiamo|puo|devo|dobbiamo|deve|serve|"
                  r"occorre|valuta\w*|indica\w*|dimmi|spiega\w*|calcola\w*|verifica se|e obbligatori|e necessari|vogliamo|vuole)\b")
_PARERE = (r"\bvaluta\w*|come ci difendiamo|come ci muoviamo|come procediamo|come ci opponiamo|possiamo (?:proporre|presentare|impugnare|ricorrere|fare ricorso|opporci)|come (?:difenderci|difenderlo|difenderla|opporci|impugnar\w*|contestar\w*|reagire|muoverci)|"
           r"cosa (?:dobbiamo|possiamo|devo|posso) fare|cosa facciamo|che fare\b|che azion|quale azion|come (?:procedo|posso|devo|agire|recuper\w*|possiamo|dobbiamo|facciamo|procediamo|agiamo|"
           r"tuteliamo|ci muoviamo)|recuperare il credito|cosa (?:posso|possiamo|devo|deve|rischia)|"
           r"posso (?:chiedere|agire|ottenere|recedere|trattenere|sanare)|ha diritto|spett[ao]|e obbligatori|e necessari|"
           r"serve (?:la|il|una|un)\b|occorre|quale giudice|giudice competente|chi e competente|e competente|competen|\brito\b|"
           r"procedibil|mediazione|negoziazione|conviene|in che modo|quando posso|si puo|e possibile|indica la norma|"
           r"che norma|quale norma|sana\w*|cosa prevede|che cosa prevede|\bpuo\b|\bpossono\b|(?:che|quale|quali) tutel\w*|"
           r"possiamo (?:chiedere|fare|ottenere|agire)")
_TERMINE = r"entro quando|termin[ei] (?:per|di|breve|lungo)|entro quanto|quanto tempo|scadenza (?:per|del)|quando scade|\bentro\b.{0,30}\bdevo\b"
_OGGETTI_GIURIDICI = (r"appell|cassazione|opposizion|ricors|querel|impugn|licenzia|precett|delibera|accertamento|provvediment|"
                      r"decreto|sentenz|reclamo|esecuzion|divorzi|separazion|sfratt|contratt|caparra|preliminare|risarciment|"
                      r"locazion|condomin|consumator|lavorator|datore|credit|fattur|canon|deposito cauzional|tar\b|tributar|penale|reato|"
                      r"negoziazion|mediazion|procedibil|competen|giudice|tribunale|\bnorma\b|domanda di pagamento|\brito\b|procediment|"
                      r"mantenim|assegno|affidament|\bfigli|coniug|conduttor|locator|moros|lavor|dipendent|"
                      r"articolo|\bart\.?\s*\d|codice|c\.c\.|c\.p\.c\.|d\.lgs|d\.l\.|legge|tamponat|sinistro|incidente|assicura|"
                      r"\bdanni\b|\bvizi\b|infiltrazion|verbale|multa|diniego|permesso di costruire|eredit|successione|furto|truffa|"
                      r"appalt|installator")
# Richieste sui dati dello studio (restano al percorso operativo).
_OPERATIVA = (r"\b(?:cosa|che cosa|quali|quante|mostra\w*|elenc\w*|dammi|dimmi)\b.{0,40}\b(?:scad\w*|pec|udienz\w*|appuntament\w*|"
              r"agenda|email|messagg\w*|notific\w*|fascicol\w*|client\w*|fattur\w*|preventiv\w*|depositi|ricevut\w*)|"
              r"^(?:pec|scadenze|udienze|agenda|notifiche|email)\b")


# Ricerche nelle fonti ufficiali (allegati, questioni, riforme): restano al percorso delle fonti.
_RICERCA_FONTI = ("allegato ufficiale", "allegato della questione", "allegato collegato", "fonte correttiva", "fonte collegata",
                  "questione penale", "questione civile", "ordinanza di rimessione", "qsp", "contentid=", "fonte ufficiale",
                  "fonti ufficiali", "fonti del modello", "fonte del modello", "gazzetta ufficiale", "correttivo",
                  "riforma civile", "riforma penale", "codice deontologico", "ordinamento forense", "equo compenso")


@dataclass
class Comprensione:
    tipo: str                      # redazione | parere | termine | norma | calcolo | operativa | altro
    atto: str = ""                 # atto da redigere, se chiesto
    racconto: bool = False         # la domanda contiene un racconto di fatti
    giuridica: bool = False        # la domanda pone una questione di diritto
    motivi: list[str] = field(default_factory=list)

    @property
    def per_harness(self) -> bool:
        return self.tipo in {"redazione", "parere", "termine", "norma", "calcolo"}


def atto_richiesto(testo: str) -> str:
    t = piano(testo)
    for nome, espr in ATTI:
        if re.search(espr, t):
            return nome
    return ""


def e_racconto_di_fatti(testo: str) -> bool:
    t = piano(testo)
    date = len(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", t))
    marcatori = sum(1 for m in ("parte assistita", "controparte", "fatti del fascicolo", "richiesta dell avvocato",
                                "il mio cliente", "la mia cliente", "mio assistito", "mia assistita", "convenuto", "attore",
                                "ricorrente", "resistente") if m in t)
    return len(t) >= 280 and (date >= 2 or marcatori >= 2)


def comprendi(testo: str) -> Comprensione:
    t = piano(testo)
    if not t:
        return Comprensione("altro")
    racconto = e_racconto_di_fatti(testo)
    # Nel racconto strutturato la richiesta è la parte fra «Richiesta dell'avvocato» e «Fatti»: atto e verbo si
    # leggono lì, non nei fatti («ricorso per sequestro» nei fatti non è la richiesta di redigere un ricorso).
    m_rich = re.search(r"richiesta dell avvocato\s*:?\s*(.+?)(?:\bfatti del fascicolo\b|$)", t)
    richiesta = m_rich.group(1) if m_rich else t
    atto = atto_richiesto(richiesta)
    verbo = re.search(_VERBI_REDAZIONE, richiesta) is not None
    if re.search(r"\bparere\b|\bconsulenza\b", richiesta) and not re.search(r"(?:redig|prepar|scriv)\w* (?:l |il |la |un |una )?(?:atto|ricorso|citazione|comparsa)", richiesta):
        return Comprensione("parere", atto, racconto, True, ["richiesta di parere"])
    oggetto = re.search(_OGGETTI_GIURIDICI, t) is not None
    parere = re.search(_PARERE, t) is not None
    termine = re.search(_TERMINE, t) is not None
    motivi: list[str] = []
    # La comunicazione allo studio (PEC, email al cliente) resta al percorso delle comunicazioni.
    domanda = re.search(_FORMA_DOMANDA, t) is not None
    fonti_ufficiali = any(tok in t for tok in _RICERCA_FONTI) and not racconto and not termine
    comunicazione = re.search(r"\b(?:pec|email|e-mail|mail|messaggio|whatsapp)\b", t) and not atto and not racconto
    if verbo and atto and not comunicazione:
        motivi.append(f"verbo di redazione e atto «{atto}»")
        return Comprensione("redazione", atto, racconto, True, motivi)
    if re.search(r"(?:cosa|che cosa) (?:prevede|dice|stabilisce)|testo (?:dell|vigente)|leggimi", t) and re.search(r"\bart\.?\s*\d|articolo\s+\d", t) and not racconto:
        return Comprensione("norma", "", False, True, ["richiesta del testo di un articolo"])
    if re.search(r"contributo unificato|\bcalcol\w*|interessi legali|rivalutazione monetaria|quanto (?:e|costa|devo pagare)\b.{0,40}(?:contributo|compenso|interessi)", t) and not racconto:
        return Comprensione("calcolo", atto, False, True, ["calcolo con i motori certi"])
    if fonti_ufficiali:
        return Comprensione("altro", atto, racconto, True, ["ricerca nelle fonti ufficiali"])
    if termine and oggetto and domanda:
        motivi.append("termine riferito a un atto o a un provvedimento")
        return Comprensione("termine", atto, racconto, True, motivi)
    if (parere and domanda and (oggetto or racconto)) or (racconto and re.search(r"\?|richiesta dell avvocato|vogliamo|vuole", t)):
        motivi.append("questione di diritto" + (" con racconto di fatti" if racconto else ""))
        return Comprensione("parere", atto, racconto, True, motivi)
    if re.search(_OPERATIVA, t) and not oggetto:
        return Comprensione("operativa", "", racconto, False, ["richiesta sui dati dello studio"])
    # Ingresso dalla fattispecie: una domanda o una richiesta di redazione entra nell'harness quando i fatti descritti
    # corrispondono a una regola, anche senza le formule di parere o le parole-oggetto degli elenchi.
    if (domanda or verbo) and not comunicazione:
        tipo = "redazione" if verbo else ("termine" if termine else "parere")
        if _fattispecie_riconosciuta(testo, Comprensione(tipo, atto, racconto, True)):
            return Comprensione(tipo, atto, racconto, True, ["fattispecie riconosciuta dai fatti descritti"])
    return Comprensione("altro", atto, racconto, bool(oggetto), motivi)


def _fattispecie_riconosciuta(testo: str, c: Comprensione) -> bool:
    from .fatti import leggi_fatti
    from .fattispecie import scegli

    return scegli(c, leggi_fatti(testo)) is not None


def e_richiesta_giuridica(testo: str) -> bool:
    """Per i router operativi: questa domanda non va deviata verso PEC, scadenze o anagrafiche dello studio."""
    return comprendi(testo).per_harness
