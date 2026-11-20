"""Il guardiano della catena: controlli di coerenza di un fascicolo, puri e deterministici.

Riceve ciò che il fascicolo mostra (Lettura con il modello della causa, scadenze, agenda, stato, quadro, bozze,
impronte dei pannelli salvati) e restituisce le incoerenze. Ogni incoerenza dice che cosa non torna, perché (con la
norma) e quale **regola la ripara** (``riparazione``); senza regola diventa un avviso per l'avvocato. Le righe scritte
o prese in carico dall'avvocato non si riparano mai: si segnalano.

Regole (fonte certa + lettura certa = dato definitivo; le decisioni dell'avvocato non si toccano):

- un termine certo che grava sullo studio (art. 152 c.p.c.) ha la sua scadenza aperta, con la stessa data e la norma;
- il termine della controparte (es. costituzione del convenuto, artt. 166 e 416 c.p.c.) non è un adempimento dello
  studio: la proposta automatica si scarta;
- una scadenza automatica che il provvedimento successivo ha spostato si annulla (il termine nuovo si registra);
- l'«opposizione» registrata come termine nel giorno di un'udienza fissata è l'udienza, non un termine;
- ogni udienza futura del modello è in agenda, con la modalità disposta dal giudice (artt. 127-bis e 127-ter c.p.c.);
- nessun prossimo passo per un adempimento fatto con la prova;
- lo stato del fascicolo segue la causa: niente «Definito» con un'udienza futura o senza una decisione; niente
  «In corso» con una sentenza passata in giudicato (art. 324 c.p.c.; art. 2909 c.c.) e il credito incassato;
- il quadro dice lo stesso prossimo passo della Lettura;
- ogni pannello mostrato è calcolato sulle fonti attuali (impronta uguale), altrimenti è «in aggiornamento»;
- le bozze corrispondono ai passi aperti.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable, Iterable

VERSIONE = "2026.11.19.guardiano.v1"

# Marcatore delle scadenze che il guardiano scrive dal modello della causa.
MARCATORE = "RAGIONAMENTO:"
SEGNI_AUTOMATICI = ("ARCHIVIO_FATTO:", "PEC_TERMINE_PROPOSTO:", "PEC_AUDIT:", "UDIENZA_DERIVATA:", "SENTENZA_327:",
                    MARCATORE, "Obbligo di notifica letto dal documento", "IUSENTRA_")
# Dubbi che rendono incerto il computo del termine (gli stessi di pct/fascicolo_lettura/termini_certi.py).
DUBBI_DEL_COMPUTO = frozenset({"destinazione_notifica_ignota", "pronuncia_ignota", "udienza_ignota",
                               "comunicazione_non_trovata", "parte_onerata_ignota", "adempimento_generico",
                               "decorrenza_ignota"})
ONERATI_STUDIO = frozenset({"noi", "tutte_le_parti"})
# Le nature con cui la Lettura qualifica un termine per adempiere (pct/fascicolo_lettura/ragionamento._termine).
NATURE_DEL_TERMINE = frozenset({"perentorio", "ordinatorio", "non qualificato", ""})
# Fasi in cui la causa è certamente pendente (atto introduttivo, udienza fissata): «Definito» qui va verificato. Le altre
# fasi (provvedimenti presenti, esecutiva...) non bastano a dirlo: un'estinzione o una conciliazione non sono una
# sentenza riconosciuta dal modello (misura del 19/11/2026, fascicolo con provvedimento di estinzione).
FASI_DI_CAUSA_PENDENTE = frozenset({"preparatoria", "atto_introduttivo_presente", "atto_introduttivo_depositato",
                                    "udienza_fissata"})
# Fasi del modello (pct/ragionamento/fase.py) che portano una decisione della causa o un titolo definitivo.
STATI_DECISIONE = frozenset({"decisa", "giudicato_da_verificare", "decreto_esecutivo", "decreto_notificato",
                             "istanza_esecutorieta", "precetto_notificato"})
_RE_DATA_IT = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# Regole di riparazione (eseguite da web/services/catena_guardiano_runtime.py).
CREA_SCADENZA = "crea_scadenza_dal_modello"
CONFERMA_BOZZA = "conferma_termini_certi"
SCARTA_BOZZA = "scarta_bozza_automatica"
ANNULLA_SCADENZA = "annulla_scadenza_automatica"
CREA_UDIENZA = "crea_udienza_dal_modello"
AGGIORNA_MODALITA = "aggiorna_modalita_udienza"
RICONCILIA_ADEMPIMENTI = "riconcilia_adempimenti"
RICALCOLO = "ricalcolo_pannelli"
PREPARA_BOZZE = "prepara_bozze"
RICONVALIDA_CICLO = "riconvalida_ciclo_letture"
AGGIORNA_NORMA = "aggiorna_norma_scadenza"
# I pannelli che portano i dati della catena (gli stessi che il calcolatore prepara per primi).
PANNELLI_DELLA_CATENA = frozenset({"lettura", "passaggi", "conto-economico", "quadro", "obblighi-notifica", "scadenze"})
RIPARAZIONI = (AGGIORNA_NORMA, CREA_SCADENZA, CONFERMA_BOZZA, SCARTA_BOZZA, ANNULLA_SCADENZA, CREA_UDIENZA, AGGIORNA_MODALITA,
               RICONCILIA_ADEMPIMENTI, RICALCOLO, PREPARA_BOZZE, RICONVALIDA_CICLO)


@dataclass
class Incoerenza:
    codice: str
    descrizione: str
    perche: str
    norma: str = ""
    riparazione: str = ""  # vuota: non riparabile da sola → avviso
    dati: dict[str, Any] = field(default_factory=dict)

    @property
    def chiave(self) -> str:
        """Identità stabile dell'incoerenza nel fascicolo (stesso problema → stessa chiave a ogni giro)."""
        base = "|".join([self.codice, *(f"{k}={self.dati[k]}" for k in sorted(self.dati) if k in _CHIAVE)])
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]

    def come_dizionario(self) -> dict[str, Any]:
        return {**asdict(self), "chiave": self.chiave}


_CHIAVE = ("codice_conclusione", "data", "scadenza_id", "appuntamento_id", "pannello", "bozza", "stato_fascicolo")


@dataclass
class StatoFascicolo:
    """Ciò che il fascicolo mostra adesso (dizionari semplici: dai payload salvati o scritti a mano nei test)."""

    fascicolo_id: str
    oggi: date
    lettura: dict[str, Any] | None = None  # la Lettura (payload «lettura»), None se non pronta
    scadenze: list[dict[str, Any]] = field(default_factory=list)  # id, titolo, data, stato, note, responsabile
    appuntamenti: list[dict[str, Any]] = field(default_factory=list)  # id, tipo, data, stato, note, modalita
    stato_fascicolo: str = ""  # IN_CORSO, DEFINITO, SOSPESO, ARCHIVIATO...
    credito_incassato: bool | None = None
    quadro: dict[str, Any] | None = None
    bozze: list[dict[str, Any]] = field(default_factory=list)  # chiave, stato, passi [{azione}]
    pannelli: list[dict[str, Any]] = field(default_factory=list)  # pannello, salvata, attesa, tentata
    # Voci del catalogo decise o corrette dopo l'ultimo ciclo delle letture: documento, voce, quando.
    catalogo_dopo_letture: list[dict[str, Any]] = field(default_factory=list)
    # Il modello riconosce gli atti dello studio dai nomi degli avvocati nelle Impostazioni: senza, la parte onerata
    # di un termine non è certa (un ricorso dello studio sembrerebbe della controparte).
    studio_con_avvocati: bool = True
    # Rilettura del testo del provvedimento: (documento_id, codice) → date che il testo assegna (pct/catena/rilettura).
    # Si chiama solo quando due fonti del software danno date diverse per lo stesso termine.
    rileggi: Callable[[str, str], list[str] | None] | None = None


# --- utilità ---------------------------------------------------------------------------------------------------

def _t(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def iso(valore: Any) -> str:
    testo = _t(valore)
    m = _RE_DATA_IT.match(testo[:10])
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return testo[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", testo) else ""


def data_it(valore: Any) -> str:
    giorno = iso(valore)
    return f"{giorno[8:10]}/{giorno[5:7]}/{giorno[:4]}" if giorno else ""


def automatica(scadenza: dict[str, Any]) -> bool:
    """Scritta dal software e mai presa in carico da una persona dello studio.

    Il responsabile conta come decisione dell'avvocato solo se è un utente dello studio (``responsabile_umano``,
    calcolato dalla raccolta sugli utenti): i lavori automatici scrivono come responsabile «scheduler», «ripasso-2484»,
    «document-presidio-backfill»... (misura del 19/11/2026). Senza l'informazione, ogni responsabile è una persona.
    """
    note = str(scadenza.get("note") or "")
    responsabile = _t(scadenza.get("id_utente_responsabile"))
    umano = bool(scadenza["responsabile_umano"]) if "responsabile_umano" in scadenza else bool(responsabile)
    return any(s in note for s in SEGNI_AUTOMATICI) and not umano


def _stato(riga: dict[str, Any]) -> str:
    return _t(riga.get("stato")).upper()


def _aperta(riga: dict[str, Any]) -> bool:
    return _stato(riga) in {"APERTO", "BOZZA", ""}


def codice_scadenza(scadenza: dict[str, Any]) -> str:
    """Il codice dell'adempimento di una scadenza: marcatore del guardiano o regole della Lettura."""
    note = str(scadenza.get("note") or "")
    m = re.search(re.escape(MARCATORE) + r"([a-z0-9_]+)", note)
    if m:
        return m.group(1)
    from pct.fascicolo_lettura.termini_certi import codice_della_bozza

    return codice_della_bozza({"titolo": scadenza.get("titolo"), "note": note,
                               "codice_proposta": scadenza.get("codice_proposta")})


def _ragionamento(stato: StatoFascicolo) -> dict[str, Any]:
    return ((stato.lettura or {}).get("ragionamento") or {}) if isinstance(stato.lettura, dict) else {}


def _conclusioni(stato: StatoFascicolo) -> list[dict[str, Any]]:
    return [c for c in _ragionamento(stato).get("conclusioni") or [] if isinstance(c, dict)]


def _norma(voce: dict[str, Any]) -> str:
    return "; ".join(_t(n.get("norma")) for n in voce.get("norme") or [] if _t(n.get("norma")))


def _onerato(voce: dict[str, Any]) -> str:
    return _t(voce.get("onerato_codice") or voce.get("onerato"))


def termine_certo_dello_studio(voce: dict[str, Any], oggi: date) -> str:
    """La scadenza (ISO) se la conclusione è un termine certo, futuro o di oggi, che grava sullo studio."""
    termine = voce.get("termine") or {}
    giorno = iso(termine.get("scadenza_iso") or termine.get("scadenza"))
    if voce.get("stato") != "da_fare" or _onerato(voce) not in ONERATI_STUDIO or not giorno or giorno < oggi.isoformat():
        return ""
    if _t(termine.get("natura")) not in NATURE_DEL_TERMINE:
        return ""  # finestra procedurale o attesa minima: non è un termine per adempiere
    if {d.get("codice") for d in voce.get("dubbi") or []} & DUBBI_DEL_COMPUTO:
        return ""
    if not ((voce.get("letto") or {}).get("documento_id") or (voce.get("letto") or {}).get("oggetto_id")):
        return ""
    return giorno


# --- controlli -------------------------------------------------------------------------------------------------

def controlla_termini(stato: StatoFascicolo) -> list[Incoerenza]:
    """Termini certi dello studio ↔ scadenziario; termini della controparte e termini superati."""
    if not stato.studio_con_avvocati:
        if any(termine_certo_dello_studio(v, stato.oggi) or _onerato(v) == "controparte" for v in _conclusioni(stato)):
            return [Incoerenza(
                "studio_senza_avvocati", "la parte onerata dei termini non si può verificare",
                "nelle Impostazioni dello studio manca il nome dell'avvocato: il software non distingue gli atti dello "
                "studio da quelli della controparte, quindi non registra né scarta termini da solo", "", "",
                {"codice_conclusione": "studio"})]
        return []
    esito: list[Incoerenza] = []
    aperte = [s for s in stato.scadenze if _aperta(s)]
    certi: dict[str, str] = {}
    for voce in _conclusioni(stato):
        giorno = termine_certo_dello_studio(voce, stato.oggi)
        if not giorno:
            continue
        codice = voce.get("codice") or ""
        certi.setdefault(codice, giorno)
        stesse = [s for s in aperte if iso(s.get("data")) == giorno and codice_scadenza(s) in {codice, ""}]
        confermate = [s for s in stesse if _stato(s) == "APERTO" and codice_scadenza(s) == codice] or [
            s for s in stesse if _stato(s) == "APERTO"]
        dati = {"codice_conclusione": codice, "data": giorno, "norma": _norma(voce), "cosa": voce.get("cosa"),
                "documento": (voce.get("letto") or {}).get("documento"),
                "documento_id": (voce.get("letto") or {}).get("documento_id"), "onerato": _onerato(voce),
                "perentorio": (voce.get("termine") or {}).get("natura") == "perentorio"}
        # Le scadenze scritte dal guardiano stesso con un calcolo precedente si annullano come superate (sotto).
        altre = [s for s in aperte if automatica(s) and codice_scadenza(s) == codice and iso(s.get("data")) != giorno
                 and MARCATORE not in str(s.get("note") or "")]
        if altre:
            decisione = _decidi_sul_testo(stato, voce, dati, giorno, altre, bool(confermate or stesse))
            if decisione is not None:
                esito.extend(decisione)
                continue
        if confermate:
            doppie = [s for s in stesse if _stato(s) == "BOZZA" and automatica(s) and codice_scadenza(s) == codice]
            if doppie:
                esito.append(Incoerenza(
                    "proposta_doppia", f"la proposta «{_t(doppie[0].get('titolo'))}» ripete un termine già nello scadenziario",
                    f"«{_t(confermate[0].get('titolo'))}» del {data_it(giorno)} è già aperta: la proposta doppia si scarta",
                    dati["norma"], SCARTA_BOZZA, {"scadenza_id": doppie[0].get("id"), "data": giorno, "codice_conclusione": codice}))
            nostra = next((s for s in confermate if MARCATORE + codice in str(s.get("note") or "") and automatica(s)), None)
            norma_scritta = next((r[len("Norma: "):] for r in str((nostra or {}).get("note") or "").splitlines()
                                  if r.startswith("Norma: ")), None)
            if nostra is not None and norma_scritta is not None and norma_scritta.strip() != dati["norma"]:
                esito.append(Incoerenza(
                    "norma_diversa", f"la scadenza «{_t(nostra.get('titolo'))}» cita una norma diversa dal modello",
                    f"scritta: «{norma_scritta}»; il modello applica oggi «{dati['norma']}»", dati["norma"], AGGIORNA_NORMA,
                    {**dati, "scadenza_id": nostra.get("id")}))
            continue
        bozze = [s for s in stesse if _stato(s) == "BOZZA"]
        if bozze:
            automatiche = [s for s in bozze if automatica(s)]
            esito.append(Incoerenza(
                "termine_certo_in_bozza", f"«{voce.get('cosa')}» entro il {data_it(giorno)} è ancora una proposta da confermare",
                f"il termine è letto nel provvedimento «{dati['documento']}» e calcolato dal modello: fonte certa e lettura "
                "certa rendono il dato definitivo", dati["norma"], CONFERMA_BOZZA if automatiche else "",
                {**dati, "scadenza_id": (automatiche or bozze)[0].get("id")}))
            continue
        esito.append(Incoerenza(
            "termine_certo_senza_scadenza", f"«{voce.get('cosa')}» entro il {data_it(giorno)} non è nello scadenziario",
            f"il modello lo ricava da «{dati['documento']}»; un termine dello studio senza scadenza aperta può scadere "
            "senza avviso", dati["norma"], CREA_SCADENZA, dati))
    for scadenza in aperte:
        codice, giorno = codice_scadenza(scadenza), iso(scadenza.get("data"))
        if codice and codice in certi and certi[codice] != giorno and MARCATORE in str(scadenza.get("note") or "") \
                and automatica(scadenza):
            esito.append(Incoerenza(
                "scadenza_superata", f"la scadenza «{_t(scadenza.get('titolo'))}» del {data_it(giorno)} è superata",
                f"il modello calcola oggi lo stesso adempimento al {data_it(certi[codice])}", "",
                ANNULLA_SCADENZA, {"scadenza_id": scadenza.get("id"), "data": giorno, "codice_conclusione": codice}))
    esito.extend(_termini_della_controparte(stato, aperte))
    esito.extend(_opposizioni_che_sono_udienze(stato, aperte))
    return esito


def _decidi_sul_testo(stato: StatoFascicolo, voce: dict[str, Any], dati: dict[str, Any], giorno: str,
                      altre: list[dict[str, Any]], presente: bool) -> list[Incoerenza] | None:
    """Due fonti, due date per lo stesso termine: decide il testo del provvedimento (regola della certezza).

    Testo che conferma il modello → le altre proposte automatiche si annullano (e la scadenza si crea se manca);
    testo che conferma l'altra data → il modello va corretto, avviso; testo ambiguo o illeggibile → scadenza alla
    data anteriore con l'avviso «due date».
    """
    documento_id = str(dati.get("documento_id") or "")
    try:
        lette = stato.rileggi(documento_id, dati["codice_conclusione"]) if stato.rileggi and documento_id else None
    except Exception:  # testo illeggibile: si tratta come ambiguo, mai un controllo che si ferma
        lette = None
    lette = sorted(set(lette or []))
    altra = sorted(iso(s.get("data")) for s in altre)[0]
    esito: list[Incoerenza] = []
    if lette == [giorno]:
        for s in altre:
            esito.append(Incoerenza(
                "data_smentita_dal_testo", f"«{_t(s.get('titolo'))}» del {data_it(s.get('data'))} non è la data del provvedimento",
                f"il testo di «{dati['documento']}» porta il {data_it(giorno)}", dati["norma"],
                SCARTA_BOZZA if _stato(s) == "BOZZA" else ANNULLA_SCADENZA,
                {"scadenza_id": s.get("id"), "data": iso(s.get("data")), "codice_conclusione": dati["codice_conclusione"]}))
        if not presente:
            esito.append(Incoerenza(
                "termine_certo_senza_scadenza", f"«{voce.get('cosa')}» entro il {data_it(giorno)} non è nello scadenziario",
                f"riletto il testo di «{dati['documento']}»: la data è il {data_it(giorno)}", dati["norma"], CREA_SCADENZA, dati))
        return esito
    if len(lette) == 1 and lette[0] in {iso(s.get("data")) for s in altre}:
        return [Incoerenza(
            "modello_smentito_dal_testo", f"il modello calcola il {data_it(giorno)}, il provvedimento porta il {data_it(lette[0])}",
            f"riletto il testo di «{dati['documento']}»: resta valida la scadenza del {data_it(lette[0])}; il calcolo del "
            "modello va corretto", dati["norma"], "", {**dati, "data": lette[0]})]
    anteriore = min(giorno, altra)
    gia_aperta = (presente and anteriore == giorno) or any(
        iso(s.get("data")) == anteriore and _stato(s) == "APERTO" for s in altre)
    motivo = "il testo porta date diverse" if len(lette) > 1 else "il testo non è leggibile o non dice la data"
    # Riparazione (la data anteriore nello scadenziario) e, sempre, l'avviso per l'avvocato.
    return [Incoerenza(
        "due_date", f"due date: {data_it(giorno)[:5]} contro {data_it(altra)[:5]}, {motivo}",
        f"per «{voce.get('cosa')}» il modello e un'altra fonte del software non concordano: si registra la data "
        f"anteriore, il {data_it(anteriore)}, e la verifica resta all'avvocato", dati["norma"],
        "" if gia_aperta else CREA_SCADENZA, {**dati, "data": anteriore, "altra_data": altra, "avviso_anche": True})]


def _termini_della_controparte(stato: StatoFascicolo, aperte: list[dict[str, Any]]) -> list[Incoerenza]:
    esito = []
    altrui = {}
    for voce in _conclusioni(stato):
        giorno = iso((voce.get("termine") or {}).get("scadenza_iso") or (voce.get("termine") or {}).get("scadenza"))
        if _onerato(voce) == "controparte" and giorno:
            altrui.setdefault((voce.get("codice"), giorno), voce)
    for scadenza in aperte:
        voce = altrui.get((codice_scadenza(scadenza), iso(scadenza.get("data"))))
        if voce is None:
            continue
        auto = automatica(scadenza)
        riparazione = (SCARTA_BOZZA if _stato(scadenza) == "BOZZA" else ANNULLA_SCADENZA) if auto else ""
        esito.append(Incoerenza(
            "termine_della_controparte", f"«{_t(scadenza.get('titolo'))}» è un termine della controparte, non dello studio",
            f"{voce.get('cosa')}: grava sulla controparte (letto in «{(voce.get('letto') or {}).get('documento', '')}»)"
            + ("" if auto else "; la scadenza è dell'avvocato e resta com'è"), _norma(voce), riparazione,
            {"scadenza_id": scadenza.get("id"), "data": iso(scadenza.get("data")), "codice_conclusione": voce.get("codice")}))
    return esito


def _udienze(stato: StatoFascicolo) -> list[dict[str, Any]]:
    risultato = []
    for u in _ragionamento(stato).get("udienze") or []:
        giorno = iso(u.get("data"))
        if giorno:
            modalita = _t(u.get("modalita")).lower()
            codice = "note_scritte" if "note" in modalita else "remota" if "remot" in modalita else "presenza"
            risultato.append({**u, "iso": giorno, "modalita_codice": codice})
    return risultato


def _opposizioni_che_sono_udienze(stato: StatoFascicolo, aperte: list[dict[str, Any]]) -> list[Incoerenza]:
    giorni_udienza = {u["iso"] for u in _udienze(stato) if u["modalita_codice"] != "note_scritte"}
    esito = []
    for scadenza in aperte:
        giorno = iso(scadenza.get("data"))
        if "opposizion" in _t(scadenza.get("titolo")).lower() and giorno in giorni_udienza:
            auto = automatica(scadenza)
            esito.append(Incoerenza(
                "opposizione_e_udienza", f"«{_t(scadenza.get('titolo'))}» del {data_it(giorno)} è l'udienza fissata, non un termine",
                "il provvedimento fissa in quel giorno l'udienza: il termine per l'opposizione decorre dalla notifica "
                "o comunicazione dell'atto, non dall'udienza", "art. 641 c.p.c.; art. 617 c.p.c.",
                (SCARTA_BOZZA if _stato(scadenza) == "BOZZA" else ANNULLA_SCADENZA) if auto else "",
                {"scadenza_id": scadenza.get("id"), "data": giorno}))
    return esito


def controlla_agenda(stato: StatoFascicolo) -> list[Incoerenza]:
    """Ogni udienza futura del modello in agenda, con la modalità disposta dal giudice."""
    esito = []
    udienze_agenda = [a for a in stato.appuntamenti
                      if _t(a.get("tipo")).upper() == "UDIENZA" and _stato(a) not in {"ANNULLATO", "RINVIATO"}]
    chiuse = [a for a in stato.appuntamenti if _t(a.get("tipo")).upper() == "UDIENZA" and _stato(a) in {"ANNULLATO", "RINVIATO"}]
    # Art. 127-ter c.p.c.: il giorno di scadenza del termine per le note vale come udienza; la scadenza aperta delle
    # note dello stesso giorno è la stessa udienza (pct/agenda_eventi_equivalenti.py).
    note_aperte = {iso(s.get("data")) for s in stato.scadenze if _aperta(s) and codice_scadenza(s) == "note_127ter"}
    for u in _udienze(stato):
        if u["iso"] < stato.oggi.isoformat():
            continue
        dati = {"data": u["iso"], "ora": u.get("ora") or "", "modalita": u["modalita_codice"],
                "documento": u.get("documento"), "documento_id": u.get("documento_id")}
        stesse = [a for a in udienze_agenda if iso(a.get("data") or a.get("data_ora")) == u["iso"]]
        if not stesse and u["modalita_codice"] == "note_scritte" and u["iso"] in note_aperte:
            continue
        annullate = [a for a in chiuse if iso(a.get("data") or a.get("data_ora")) == u["iso"]]
        if not stesse and annullate:
            # Annullata o rinviata in agenda: può essere una decisione o un provvedimento successivo; non si ricrea.
            esito.append(Incoerenza(
                "udienza_annullata_in_agenda", f"l'udienza del {data_it(u['iso'])} risulta {_stato(annullate[0]).lower()} in agenda",
                f"il modello la legge fissata in «{u.get('documento', '')}»: verificare il provvedimento successivo di rinvio "
                "o di revoca", "", "", {**dati, "appuntamento_id": annullate[0].get("id")}))
            continue
        if not stesse:
            esito.append(Incoerenza(
                "udienza_non_in_agenda", f"l'udienza del {data_it(u['iso'])} non è in agenda",
                f"fissata con «{u.get('documento', '')}»: senza appuntamento l'udienza non compare nel calendario dello studio",
                "art. 175 c.p.c.", CREA_UDIENZA, dati))
            continue
        modalita_agenda = _t(stesse[0].get("modalita")).lower()
        if u["modalita_codice"] == "note_scritte" and modalita_agenda != "note_scritte":
            auto = any(s in str(stesse[0].get("note") or "") for s in SEGNI_AUTOMATICI)
            esito.append(Incoerenza(
                "modalita_udienza_diversa", f"l'udienza del {data_it(u['iso'])} in agenda non dice che è sostituita da note scritte",
                f"«{u.get('documento', '')}» dispone la trattazione scritta: non si va in aula, si depositano le note",
                "art. 127-ter c.p.c.", AGGIORNA_MODALITA if auto else "",
                {**dati, "appuntamento_id": stesse[0].get("id")}))
    return esito


def _norm(testo: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _t(testo).lower()).strip()


def controlla_passi(stato: StatoFascicolo) -> list[Incoerenza]:
    """Nessun prossimo passo per un adempimento fatto con la prova; scadenze aperte di un adempimento provato."""
    lettura = stato.lettura or {}
    fatti = [c for c in _conclusioni(stato) if c.get("stato") == "fatto" and (c.get("prova_deposito") or c.get("prova_notifica"))]
    if not fatti:
        return []
    passi = {_norm(p.get("azione")) for p in lettura.get("prossimi_passi") or [] if isinstance(p, dict)}
    da_fare = {_norm(c.get("cosa")) for c in _conclusioni(stato) if c.get("stato") in {"da_fare", "dubbio"}}
    esito = []
    for voce in fatti:
        cosa = _norm(voce.get("cosa"))
        if cosa and cosa in passi and cosa not in da_fare:
            esito.append(Incoerenza(
                "passo_gia_fatto", f"il prossimo passo «{voce.get('cosa')}» risulta già fatto",
                "il deposito o la notifica è provato dalla ricevuta: il passo non va riproposto", _norma(voce), RICALCOLO,
                {"codice_conclusione": voce.get("codice"), "pannello": "lettura"}))
        giorno = iso((voce.get("termine") or {}).get("scadenza_iso"))
        aperte = [s for s in stato.scadenze if _stato(s) == "APERTO" and iso(s.get("data")) == giorno
                  and codice_scadenza(s) == voce.get("codice") and automatica(s)]
        if aperte:
            esito.append(Incoerenza(
                "scadenza_di_adempimento_provato", f"la scadenza «{_t(aperte[0].get('titolo'))}» è ancora aperta",
                "l'adempimento risulta eseguito con la prova: la scadenza si completa con il riferimento alla ricevuta",
                _norma(voce), RICONCILIA_ADEMPIMENTI, {"scadenza_id": aperte[0].get("id"), "data": giorno,
                                                       "codice_conclusione": voce.get("codice")}))
    return esito


def controlla_stato(stato: StatoFascicolo) -> list[Incoerenza]:
    """Lo stato del fascicolo segue la causa (decisione dell'avvocato o della definizione automatica: solo avviso)."""
    codice = _t(stato.stato_fascicolo).upper()
    if not codice or stato.lettura is None:
        return []
    fase = _t((_ragionamento(stato).get("fase") or {}).get("codice"))
    future = [u for u in _udienze(stato) if u["iso"] >= stato.oggi.isoformat()]
    esito = []
    if codice == "DEFINITO" and future:
        esito.append(Incoerenza(
            "definito_con_udienza_futura", f"il fascicolo è «Definito» ma c'è un'udienza il {data_it(future[0]['iso'])}",
            "una causa con un'udienza fissata non è definita: va verificata la definizione o l'udienza", "",
            "", {"stato_fascicolo": codice, "data": future[0]["iso"]}))
    elif (codice == "DEFINITO" and fase in FASI_DI_CAUSA_PENDENTE
          and any(isinstance(p, dict) for p in (stato.lettura or {}).get("prossimi_passi") or [])):
        esito.append(Incoerenza(
            "definito_senza_decisione", "il fascicolo è «Definito» ma non risulta una decisione della causa",
            f"la fase letta è «{(_ragionamento(stato).get('fase') or {}).get('descrizione') or fase}»", "",
            "", {"stato_fascicolo": codice}))
    if codice in {"IN_CORSO", "APERTO"} and fase == "giudicato_da_verificare" and stato.credito_incassato:
        esito.append(Incoerenza(
            "in_corso_con_giudicato_e_incasso", "il fascicolo è «In corso» con il termine per impugnare decorso e il credito incassato",
            "decorso il termine senza impugnazione la sentenza passa in giudicato (art. 324 c.p.c.) e l'incasso chiude il "
            "credito: verificato il registro delle impugnazioni, la pratica si può definire",
            "art. 324 c.p.c.; art. 2909 c.c.", "", {"stato_fascicolo": codice}))
    return esito


def controlla_quadro(stato: StatoFascicolo) -> list[Incoerenza]:
    """La riga «Prossimo passo» del quadro dice lo stesso primo passo della Lettura."""
    righe = (stato.quadro or {}).get("righe") or []
    passi = [p for p in (stato.lettura or {}).get("prossimi_passi") or [] if isinstance(p, dict)]
    riga = next((r for r in righe if r.get("tema") == "prossimo_passo"), None)
    if riga is None or not passi or stato.lettura is None:
        return []
    primo = _norm(passi[0].get("azione"))
    if primo and not _norm(riga.get("testo")).startswith(primo):
        return [Incoerenza(
            "quadro_diverso_dalla_lettura", "il quadro mostra un prossimo passo diverso dalla Lettura",
            f"quadro: «{_t(riga.get('testo'))[:120]}»; Lettura: «{_t(passi[0].get('azione'))[:120]}»", "",
            RICALCOLO, {"pannello": "quadro"})]
    return []


def controlla_freschezza(stato: StatoFascicolo) -> list[Incoerenza]:
    """Ogni pannello salvato è calcolato sulle fonti attuali; altrimenti va ricalcolato (e si mostra «in aggiornamento»)."""
    esito = []
    for voce in stato.pannelli:
        if voce.get("pannello") not in PANNELLI_DELLA_CATENA:
            continue
        attesa = voce.get("attesa")
        if attesa and voce.get("salvata") and voce.get("salvata") != attesa and voce.get("tentata") != attesa:
            esito.append(Incoerenza(
                "pannello_superato", f"il pannello «{voce.get('pannello')}» è calcolato su fonti superate",
                "una fonte del fascicolo è cambiata dopo il calcolo: il dato si mostra «in aggiornamento» finché non è ricalcolato",
                "", RICALCOLO, {"pannello": voce.get("pannello")}))
    return esito


def controlla_bozze(stato: StatoFascicolo) -> list[Incoerenza]:
    """Le bozze pronte corrispondono a un passo aperto della Lettura."""
    if stato.lettura is None:
        return []
    passi = {_norm(p.get("azione")) for p in (stato.lettura or {}).get("prossimi_passi") or [] if isinstance(p, dict)}
    esito = []
    for bozza in stato.bozze:
        if _t(bozza.get("stato")) != "pronta":
            continue
        agganci = {_norm(p.get("azione")) for p in bozza.get("passi") or [] if isinstance(p, dict)}
        if agganci and not agganci & passi:
            esito.append(Incoerenza(
                "bozza_senza_passo", f"la bozza «{_t(bozza.get('titolo'))}» non corrisponde più a un passo aperto",
                "il passo è stato fatto o non è più dovuto: la bozza non toccata dall'avvocato va tolta dai passi",
                "", PREPARA_BOZZE, {"bozza": bozza.get("chiave")}))
    return esito


def controlla_catalogo(stato: StatoFascicolo) -> list[Incoerenza]:
    """Il catalogo corretto dopo l'ultima lettura: fatti e definizione vanno riletti con la voce nuova."""
    if not stato.catalogo_dopo_letture:
        return []
    voci = stato.catalogo_dopo_letture
    return [Incoerenza(
        "catalogo_dopo_le_letture", f"{len(voci)} voci del catalogo sono cambiate dopo l'ultima lettura del fascicolo",
        f"per esempio «{_t(voci[0].get('documento'))}» ora è «{_t(voci[0].get('voce'))}»: i fatti letti, la definizione "
        "dalla sentenza e i termini dipendono dalla natura del documento", "art. 20 CAD", RICONVALIDA_CICLO,
        {"pannello": "letture", "data": iso(max(_t(v.get("quando")) for v in voci))})]


CONTROLLI = (controlla_catalogo, controlla_termini, controlla_agenda, controlla_passi, controlla_stato, controlla_quadro,
             controlla_freschezza, controlla_bozze)


def controlla(stato: StatoFascicolo) -> list[Incoerenza]:
    """Tutti i controlli. Senza Lettura pronta restano solo la freschezza e lo stato: il resto è «in aggiornamento»."""
    if stato.lettura is None:
        return controlla_freschezza(stato) + controlla_catalogo(stato)
    esito: list[Incoerenza] = []
    for controllo in CONTROLLI:
        esito.extend(controllo(stato))
    visti: set[str] = set()
    return [i for i in esito if not (i.chiave in visti or visti.add(i.chiave))]


def nota_scadenza(dati: dict[str, Any], impronta: str = "") -> str:
    """La nota della scadenza scritta dal guardiano: marcatore, fonte e norma (art. 20 CAD: tracciabile)."""
    righe = [f"{MARCATORE}{dati.get('codice_conclusione')}:{(impronta or '')[:12]}",
             f"Fonte: {dati.get('documento') or ''}" + (f" ({dati.get('documento_id')})" if dati.get("documento_id") else ""),
             f"Norma: {dati.get('norma') or ''}",
             "Termine calcolato dal modello della causa e registrato dal guardiano della catena."]
    return "\n".join(righe)


def in_dizionari(incoerenze: Iterable[Incoerenza]) -> list[dict[str, Any]]:
    return [i.come_dizionario() for i in incoerenze]


__all__ = ["CONTROLLI", "Incoerenza", "MARCATORE", "RIPARAZIONI", "StatoFascicolo", "VERSIONE", "automatica",
           "codice_scadenza", "controlla", "data_it", "in_dizionari", "iso", "nota_scadenza", "termine_certo_dello_studio"]
