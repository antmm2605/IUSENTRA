"""La mappa della catena del fascicolo, come codice: anelli, dipendenze, meccanismi di riaccensione, eventi.

La catena (richiesta dell'avvocato del 19/11/2026: «nessuna catena si interrompa»):

    documento o PEC → registro delle letture e catalogo → archivio dei fatti → modello della causa →
    Lettura e prossimi passi → scadenziario e agenda → bozze → conto economico → quadro e pannelli pronti

Ogni anello dichiara che cosa legge (altri anelli o fonti), che cosa scrive e quali **meccanismi** lo riaccendono.
Un meccanismo è un pezzo di codice reale che rimette in moto l'anello quando cambia una fonte:

- ``ciclo_letture``: ``RegistroLetture.accoda_evento`` → ``archivio_letture_runtime.leggi_fascicolo`` (consegna ai
  presìdi, rettifiche dei termini riletti, esiti delle udienze, proposte dalla sentenza, Lettura preparata e
  conferma dei termini certi). Lo accendono il documento caricato o cambiato (osservatore dei documenti), la PEC
  collegata (``pec_fascicolo_documenti_runtime``), il testo letto dall'OCR (``_consegna_dopo_ocr``) e le riletture
  notturne per una versione superata dei motori di lettura;
- ``impronta``: i contatori SQL delle fonti del fascicolo (trigger ``pannelli_rev_*``), le tabelle senza fascicolo,
  i file dello studio, il giorno a Roma e la versione (``pct/pannelli_pronti/impronta.py``): il calcolatore dei
  pannelli pronti ricalcola ogni pannello superato;
- ``dopo_lettura``: nello stesso processo a bassa priorità, appena la Lettura o il Conto economico sono ricalcolati
  (``pannelli_pronti_calcolatore.giro``): bozze dei passi e guardiano della catena;
- ``riconvalida_guardiano``: il guardiano rimette in coda il ciclo delle letture quando una voce del catalogo è
  cambiata dopo l'ultima lettura (le scritture di un anello sono a loro volta eventi: i fatti riletti riaccendono
  la consegna ai presìdi nello stesso ciclo);
- ``notte``: la catena notturna (``pct/scheduler_notturno/sequenza.py``) con il giro del guardiano su tutti i
  fascicoli non archiviati;
- ``proiezione_elenco``: la outbox, l'orologio e le regole dell'elenco dei fascicoli (``pct/fascicoli_list_*``).

``lacune(riaccensioni)`` dice, per ogni evento, quali anelli dipendono (anche indirettamente) dalla sua fonte ma non
sono riaccesi da nessun meccanismo che quella fonte mette in moto: è il punto in cui la catena si interrompe.
I test (``tests/test_catena_mappa.py``) confrontano la mappa con il codice vero: tabelle contate dall'impronta,
pannelli del catalogo con le loro dipendenze, chiamate presenti nel ciclo delle letture e nel calcolatore.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

# --- fonti ed eventi ------------------------------------------------------------------------------------------

FONTI = ("documento", "pec", "catalogo", "fatto", "scadenza", "appuntamento", "economia", "decisione", "giorno", "versione")


@dataclass(frozen=True)
class Evento:
    codice: str
    nome: str
    fonte: str
    ingresso: str  # dove entra nel software (funzione o percorso reale)


EVENTI: tuple[Evento, ...] = (
    Evento("documento", "Documento nuovo o cambiato", "documento",
           "pct.fascicoli.GestioneFascicoli.aggiungi_documento → osservatore dei documenti → registro_letture_runtime.documento_aggiornato"),
    Evento("pec_collegata", "PEC collegata al fascicolo", "pec",
           "pec_fascicolo_documenti_runtime (collegamento certo) → RegistroLetture.accoda_evento(prioritario)"),
    Evento("voce_catalogo", "Voce di catalogo assegnata o corretta", "catalogo",
           "document_intelligence (catalogo) e document_catalog_conferma (conferma dell'avvocato)"),
    Evento("fatto_letto", "Fatto letto o riletto", "fatto",
           "archivio_letture_runtime.leggi_fascicolo, registra_lettura_ocr_nell_archivio → _consegna_dopo_ocr"),
    Evento("scadenza", "Scadenza creata, modificata, completata", "scadenza", "pct.scadenziario.GestioneScadenziario"),
    Evento("appuntamento", "Appuntamento o udienza in agenda", "appuntamento", "pct.agenda (tabella appuntamenti)"),
    Evento("parcella_incasso", "Parcella, fattura o incasso", "economia",
           "fatturazione, parcella_incassi_proofs/state, presidio economico delle sentenze"),
    Evento("decisione_avvocato", "Decisione dell'avvocato", "decisione",
           "conferma o scarto di una bozza di scadenza, annullamento della definizione, conferma del catalogo"),
    Evento("cambio_giorno", "Cambio del giorno", "giorno", "pct.pannelli_pronti.impronta.giorno_roma"),
    Evento("versione_regole", "Nuova versione delle regole", "versione",
           "VERSIONE_PANNELLI, VERSIONE_LETTURA, ragionamento.VERSIONE, RESOLVER_VERSION, motori di lettura"),
)
PER_CODICE_EVENTO = {e.codice: e for e in EVENTI}

# --- meccanismi -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Meccanismo:
    codice: str
    descrizione: str
    fonti: tuple[str, ...]
    codice_sorgente: str  # modulo e funzione che lo realizzano


TUTTE = FONTI
MECCANISMI: dict[str, Meccanismo] = {m.codice: m for m in (
    Meccanismo("ciclo_letture", "Ciclo delle letture del fascicolo con la consegna ai presìdi",
               ("documento", "pec", "fatto", "versione"),
               "web.services.archivio_letture_runtime.leggi_fascicolo"),
    Meccanismo("impronta", "Impronta delle fonti e ricalcolo dei pannelli superati", TUTTE,
               "pct.pannelli_pronti.impronta.componenti / web.services.pannelli_pronti_sfondo"),
    Meccanismo("dopo_lettura", "Dopo il ricalcolo della Lettura: bozze e guardiano", TUTTE,
               "web.services.pannelli_pronti_calcolatore.giro"),
    Meccanismo("riconvalida_guardiano", "Il guardiano rimette in coda il ciclo delle letture quando il catalogo è "
               "stato corretto dopo l'ultima lettura", ("catalogo",),
               "web.services.catena_guardiano_runtime._riconvalida_ciclo"),
    Meccanismo("notte", "Giro notturno del guardiano su tutti i fascicoli non archiviati", TUTTE,
               "pct.scheduler_notturno.sequenza (guardiano_catena_notturno)"),
    Meccanismo("proiezione_elenco", "Outbox, orologio e regole dell'elenco dei fascicoli",
               ("documento", "catalogo", "fatto", "scadenza", "appuntamento", "economia", "decisione", "giorno", "versione"),
               "pct.fascicoli_list_query / fascicoli_list_clock / fascicoli_list_rules"),
)}

# --- anelli ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Anello:
    codice: str
    nome: str
    modulo: str
    legge: tuple[str, ...]  # anelli o fonti
    riacceso_da: tuple[str, ...]  # meccanismi
    scrive: tuple[str, ...] = ()  # fonti che l'anello scrive (le scritture riaccendono a loro volta la catena)
    # Che cosa mostra mentre non è ancora ricalcolato: «in_aggiornamento» (il dato precedente con l'avviso),
    # «calcolo_al_momento» (la vista si ricalcola), «in_preparazione» (nessun dato finché non è pronto),
    # «scrittura» (l'anello scrive fonti: non mostra nulla da sé).
    se_superato: str = "scrittura"


ANELLI: tuple[Anello, ...] = (
    Anello("registro_letture", "Registro delle letture", "pct.registro_letture",
           ("documento", "pec"), ("ciclo_letture",)),
    Anello("catalogo", "Catalogo dei documenti", "pct.document_intelligence",
           ("registro_letture",), ("ciclo_letture",), scrive=("catalogo",)),
    Anello("archivio_fatti", "Archivio dei fatti letti", "pct.archivio_letture",
           ("registro_letture", "catalogo"), ("ciclo_letture", "riconvalida_guardiano"), scrive=("fatto",)),
    Anello("consegna_presidi", "Consegna dei fatti a scadenziario e agenda (e rettifiche dei termini riletti)",
           "web.services.consegna_presidi_runtime", ("fatto",), ("ciclo_letture",),
           scrive=("scadenza", "appuntamento")),
    Anello("stato_fascicolo", "Definizione dalla sentenza e stato del fascicolo", "web.services.sentenza_proposte_runtime",
           ("fatto", "catalogo"), ("ciclo_letture", "riconvalida_guardiano"), scrive=("decisione",)),
    Anello("economia_sentenze", "Crediti e spese liquidate dalla sentenza", "web.services.sentenza_economic_runtime",
           ("fatto",), ("ciclo_letture", "notte"), scrive=("economia",)),
    Anello("modello_causa", "Modello della causa (ragionamento)", "pct.ragionamento",
           ("documento", "pec", "catalogo", "fatto", "scadenza", "appuntamento", "economia", "decisione", "giorno", "versione"),
           ("impronta",), se_superato="in_aggiornamento"),
    Anello("lettura", "Lettura e prossimi passi", "pct.fascicolo_lettura",
           ("modello_causa", "documento", "pec", "catalogo", "fatto", "scadenza", "appuntamento", "economia"),
           ("impronta",), se_superato="in_aggiornamento"),
    Anello("allineamento_scadenziario", "Scadenziario allineato al modello (termini certi, adempimenti fatti, termini altrui)",
           "web.services.catena_guardiano_runtime", ("modello_causa", "lettura", "scadenza"),
           ("ciclo_letture", "dopo_lettura", "notte"), scrive=("scadenza",)),
    Anello("agenda_udienze", "Udienze del modello in agenda", "web.services.catena_guardiano_runtime",
           ("modello_causa", "appuntamento"), ("ciclo_letture", "dopo_lettura", "notte"), scrive=("appuntamento",)),
    Anello("conto_economico", "Conto economico", "web.services.conto_economico",
           ("lettura", "economia"), ("impronta",), se_superato="in_aggiornamento"),
    Anello("bozze_passi", "Bozze dei prossimi passi", "pct.bozze_passi",
           # Le bozze sono documenti dell'editor esclusi dal registro delle letture (``e_bozza_del_software``):
           # non riaccendono il ciclo delle letture.
           ("lettura", "conto_economico"), ("dopo_lettura", "notte")),
    Anello("quadro", "Quadro e testata del fascicolo", "pct.fascicolo_quadro",
           ("lettura", "conto_economico", "catalogo", "scadenza", "appuntamento"), ("impronta",),
           se_superato="in_aggiornamento"),
    Anello("pannelli_pronti", "Altri pannelli pronti (scadenze, regia, obblighi, attività, relata...)",
           "web.services.pannelli_pronti_catalogo", ("lettura",), ("impronta",), se_superato="calcolo_al_momento"),
    Anello("elenco_fascicoli", "Elenco dei fascicoli (prossima scadenza, economia)", "pct.fascicoli_list_query",
           ("scadenza", "appuntamento", "catalogo", "economia", "fatto", "giorno", "versione"), ("proiezione_elenco",),
           se_superato="calcolo_al_momento"),
    Anello("guardiano", "Guardiano della catena", "pct.catena.guardiano",
           ("modello_causa", "lettura", "scadenza", "appuntamento", "bozze_passi", "quadro", "conto_economico"),
           ("dopo_lettura", "notte")),
)
PER_CODICE = {a.codice: a for a in ANELLI}

# Le riaccensioni fino alla 2.490.0 (lette nel codice il 19/11/2026): la conferma dei termini certi e la
# riconciliazione degli adempimenti giravano solo nel ciclo delle letture (``prepara_lettura_in_cache``); le udienze
# arrivavano in agenda solo dai fatti consegnati; lo scadenziario non riceveva mai i termini certi calcolati dal
# modello (``pct/ragionamento/allineamento`` non era collegato); la correzione del catalogo da parte dell'avvocato
# non rimetteva in coda il ciclo delle letture (fatti e definizione dalla sentenza restavano quelli della voce
# precedente); non esisteva un guardiano.
RIACCENSIONI_FINO_AL_2490: dict[str, tuple[str, ...]] = {
    **{a.codice: a.riacceso_da for a in ANELLI},
    "archivio_fatti": ("ciclo_letture",),
    "stato_fascicolo": ("ciclo_letture",),
    "allineamento_scadenziario": ("ciclo_letture",),
    "agenda_udienze": ("ciclo_letture",),
    "bozze_passi": ("dopo_lettura",),
    "economia_sentenze": ("ciclo_letture",),
    "guardiano": (),
}


def dipende_da(codice: str) -> frozenset[str]:
    """Le fonti da cui l'anello dipende, anche attraverso gli anelli che legge."""
    visti: set[str] = set()
    fonti: set[str] = set()
    da_vedere = [codice]
    while da_vedere:
        attuale = da_vedere.pop()
        if attuale in visti:
            continue
        visti.add(attuale)
        anello = PER_CODICE.get(attuale)
        if anello is None:
            if attuale in FONTI:
                fonti.add(attuale)
            continue
        for voce in anello.legge:
            if voce in FONTI:
                fonti.add(voce)
            if voce in PER_CODICE:
                da_vedere.append(voce)
    return frozenset(fonti)


def anelli_raggiunti(evento: str, riaccensioni: Mapping[str, Iterable[str]] | None = None) -> frozenset[str]:
    """Gli anelli che un evento riaccende, con le riaccensioni indicate (di default quelle attuali).

    Le scritture di un anello riacceso sono a loro volta eventi (la consegna ai presìdi scrive scadenze, il catalogo
    scrive voci): si segue la catena finché non si aggiunge nulla.
    """
    riaccensioni = {k: tuple(v) for k, v in (riaccensioni or {a.codice: a.riacceso_da for a in ANELLI}).items()}
    fonti = {PER_CODICE_EVENTO[evento].fonte}
    raggiunti: set[str] = set()
    while True:
        nuovi = {codice for codice, meccanismi in riaccensioni.items()
                 if codice not in raggiunti and any(fonti & set(MECCANISMI[m].fonti) for m in meccanismi)}
        if not nuovi:
            return frozenset(raggiunti)
        raggiunti |= nuovi
        for codice in nuovi:
            fonti |= set(PER_CODICE[codice].scrive)


def lacune(riaccensioni: Mapping[str, Iterable[str]] | None = None) -> list[tuple[str, str]]:
    """(evento, anello): l'anello dipende dalla fonte dell'evento ma nessun meccanismo lo riaccende."""
    risultato = []
    for evento in EVENTI:
        raggiunti = anelli_raggiunti(evento.codice, riaccensioni)
        for anello in ANELLI:
            if evento.fonte in dipende_da(anello.codice) and anello.codice not in raggiunti:
                risultato.append((evento.codice, anello.codice))
    return risultato


def ordine_di_ricalcolo() -> list[str]:
    """Gli anelli in ordine di dipendenza: chi legge viene dopo chi è letto (errore se c'è un ciclo)."""
    ordinati: list[str] = []
    restanti = [a.codice for a in ANELLI]
    while restanti:
        pronto = next((c for c in restanti
                       if all(v in ordinati or v not in PER_CODICE or v == c for v in PER_CODICE[c].legge)), None)
        if pronto is None:
            raise ValueError(f"ciclo fra gli anelli: {restanti}")
        ordinati.append(pronto)
        restanti.remove(pronto)
    return ordinati


def descrizione() -> list[dict[str, object]]:
    """La mappa in forma leggibile (pagina del registro dei controlli e rapporto all'avvocato)."""
    return [{
        "codice": a.codice, "nome": a.nome, "modulo": a.modulo, "legge": list(a.legge), "scrive": list(a.scrive),
        "riaccesoDa": [MECCANISMI[m].descrizione for m in a.riacceso_da], "seSuperato": a.se_superato,
        "eventi": [e.nome for e in EVENTI if a.codice in anelli_raggiunti(e.codice)],
    } for a in ANELLI]


__all__ = ["ANELLI", "EVENTI", "FONTI", "MECCANISMI", "PER_CODICE", "RIACCENSIONI_FINO_AL_2490", "Anello", "Evento",
           "Meccanismo", "anelli_raggiunti", "descrizione", "dipende_da", "lacune", "ordine_di_ricalcolo"]
