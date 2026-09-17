"""I prossimi passaggi, in ordine di urgenza, con la ragione, la norma e il punto in cui agire.

Non consigli generici: ogni passo nasce da un fatto di un presidio del
fascicolo — una scadenza aperta, un deposito non accettato, una notifica senza
consegna, una PEC non controllata o con un termine non ancora registrato, un
blocco della regia, una parcella scaduta, un documento da verificare — e dice
da dove viene, quale norma lo fonda (registro `pct/procedura_fasi/fonti.py`)
e dove si agisce. Un fascicolo definito, da archiviare o archiviato non ha
passaggi: la lettura lo dichiara invece di proporne.
"""

from __future__ import annotations

import re
from typing import Any

from ._testo import data_da, data_it, pulisci
from .fase import (
    CODICE_FASE_CHIUSA,
    CODICE_FASE_DECISA,
    CODICE_FASE_ESECUTIVA,
    CODICE_FASE_ISCRITTA,
    CODICE_FASE_NOTIFICATA,
    CODICE_FASE_PREPARATORIA,
)
from .modello import Passo

GIORNI_PROSSIMI = 30
MASSIMO_PASSI = 10
STATI_SENZA_PASSI = {"DEFINITO", "CHIUSO", "ARCHIVIATO"}

# Ancore della pagina del fascicolo: ogni passo porta dove si agisce.
HREF_SCADENZE = "#udienze"
HREF_COMUNICAZIONI = "#comunicazioni-notifica"
HREF_PRESIDIO = "#presidio-fascicolo"
HREF_DOCUMENTI = "#documenti"
HREF_CATALOGO = "#catalogazione-documentale"

# Quando il titolo di una scadenza nomina la norma, il passo la cita: nessuna
# deduzione, solo ciò che la scadenza dice di sé.
_NORME_NEL_TITOLO: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (r"171[\s-]*ter", ("cpc_171ter",), "CIV_MEMORIA_171_TER_1"),
    (r"\b165\b|costituzione\s+dell.?attore|iscrizione\s+a\s+ruolo", ("cpc_165",), "CIV_COSTITUZIONE_ATTORE_165"),
    (r"\b166\b|comparsa\s+di\s+risposta|costituzione\s+del\s+convenuto", ("cpc_166",), "CIV_COSTITUZIONE_CONVENUTO_166"),
    (r"\b189\b|precisazione\s+delle\s+conclusioni|conclusional", ("cpc_189",), "CIV_NOTE_CONCLUSIONI_189"),
    (r"\bappello\b|\b325\b", ("cpc_325", "cpc_327"), "CIV_APPELLO_BREVE"),
    (r"cassazione", ("cpc_325",), "CIV_CASSAZIONE_BREVE"),
    (r"opposizione\s+a\s+decreto|\b641\b|\b645\b", ("cpc_641",), "CIV_OPPOSIZIONE_DI"),
    (r"notifica\s+(?:del\s+)?decreto\s+ingiuntivo|\b644\b", ("cpc_644",), "CIV_DI_NOTIFICA_644"),
    (r"precetto", ("cpc_480", "cpc_481"), "ESE_PRECETTO_EFFICACIA_90GG"),
    (r"\b617\b|opposizione\s+agli\s+atti", ("cpc_617",), "ESE_OPPOSIZIONE_ATTI_617"),
    (r"reclamo\s+cautelare|669[\s-]*terdecies", ("cpc_669terdecies",), "CIV_RECLAMO_CAUTELARE_669_TERDECIES"),
    (r"\b416\b|memoria\s+difensiva", ("cpc_416",), ""),
    (r"mediazion", ("dlgs28_art5", "dlgs28_art8"), ""),
    (r"ricorso\s+tributario|\bTU\b.*175|corte\s+di\s+giustizia\s+tributaria", ("tu175_art67", "tu175_art68"), ""),
)

_FONTI_DEPOSITO = {
    "PCT_TELEMATICO": ("dgsia_art17", "dispatt_196sexies"),
    "PDP_PENALE": ("dgsia_art19", "cpp_111bis"),
    "PAT_AMMINISTRATIVO": ("cpa_45",),
    "PTT_TRIBUTARIO": ("tu175_art68", "tu175_art61"),
}


def _norme_della_scadenza(titolo: str) -> tuple[tuple[str, ...], str]:
    testo = pulisci(titolo).lower()
    for modello, fonti, template in _NORME_NEL_TITOLO:
        if re.search(modello, testo):
            return fonti, template
    return (), ""


def stato_passi(intestazione: dict[str, Any]) -> dict[str, Any]:
    """Se il fascicolo ammette passaggi: un fascicolo definito, da archiviare o archiviato non ne ha."""
    stato = pulisci(intestazione.get("stato_codice")).upper()
    if intestazione.get("da_archiviare"):
        return {"attivi": False, "motivo": "Fascicolo pronto per l'archivio: nessun passaggio da eseguire, solo l'archiviazione."}
    if stato in STATI_SENZA_PASSI:
        return {"attivi": False, "motivo": f"Fascicolo {intestazione.get('stato') or stato.lower()}: nessun passaggio da eseguire."}
    if stato == "SOSPESO":
        return {"attivi": True, "motivo": "Fascicolo sospeso: i passaggi restano indicati ma vanno valutati alla ripresa."}
    return {"attivi": True, "motivo": ""}


def _passi_scadenze(scadenze: list[dict[str, Any]], giorno_oggi: Any) -> list[Passo]:
    passi: list[Passo] = []
    for scadenza in scadenze:
        if pulisci(scadenza.get("stato")).upper() not in {"", "APERTO", "APERTA", "IN_CORSO"}:
            continue
        giorno = data_da(scadenza.get("data"))
        titolo = pulisci(scadenza.get("titolo")) or "scadenza"
        if not giorno or not giorno_oggi:
            continue
        fonti, template = _norme_della_scadenza(titolo)
        perentoria = " (termine perentorio)" if scadenza.get("perentorio") else ""
        distanza = (giorno - giorno_oggi).days
        if distanza < 0:
            passi.append(Passo(0, f"Verificare l’esito della scadenza «{titolo}»", f"scaduta il {data_it(giorno)}{perentoria}", data_it(giorno), "scadenziario", fonti, HREF_SCADENZE, template))
        elif distanza <= 7:
            passi.append(Passo(1, f"Adempiere a «{titolo}»", f"scade fra {distanza} giorni{perentoria}", data_it(giorno), "scadenziario", fonti, HREF_SCADENZE, template))
        elif distanza <= GIORNI_PROSSIMI:
            passi.append(Passo(2, f"Pianificare «{titolo}»", f"scade il {data_it(giorno)}{perentoria}", data_it(giorno), "scadenziario", fonti, HREF_SCADENZE, template))
    return passi


def _passi_regia(regia: dict[str, Any], gia: list[Passo]) -> list[Passo]:
    passi: list[Passo] = []
    if pulisci(regia.get("operational_state")) == "profilo_da_confermare" or pulisci(regia.get("page_state")) == "profilo_da_confermare":
        passi.append(Passo(2, "Confermare il profilo procedurale nel Presidio del fascicolo", "senza il profilo la regia non può proporre checklist e controlli", "", "presidio del fascicolo", (), HREF_PRESIDIO))
    for blocco in list(regia.get("blockers") or [])[:3]:
        messaggio = pulisci(blocco.get("suggested_action") or blocco.get("message") or blocco) if isinstance(blocco, dict) else pulisci(blocco)
        if messaggio:
            passi.append(Passo(0, messaggio, "blocco della regia operativa", "", "presidio del fascicolo", (), HREF_PRESIDIO))
    azione_regia = pulisci(regia.get("next_action") or regia.get("nextAction"))
    esito_acquisito = pulisci(regia.get("operational_state")) in {"deposito_acquisito", "deposito_accettato"} or bool(re.match(r"Deposito .+ accettato dalla cancelleria", azione_regia))
    if azione_regia and not esito_acquisito and not any(azione_regia == passo.azione for passo in gia + passi):
        passi.append(Passo(2, azione_regia, "indicazione della regia operativa", "", "presidio del fascicolo", (), HREF_PRESIDIO))
    return passi


GIORNI_ATTESA_RICEVUTE = 3


def _passi_depositi(depositi_letti: dict[str, Any], verifiche: dict[str, Any], giorno_oggi: Any) -> list[Passo]:
    """I depositi: le ricevute le controlla il presidio; all'avvocato restano i rifiuti e i silenzi anomali."""
    passi: list[Passo] = []
    for deposito in depositi_letti["falliti"]:
        fonti = _FONTI_DEPOSITO.get(deposito.get("canale", ""), _FONTI_DEPOSITO["PCT_TELEMATICO"])
        passi.append(Passo(0, f"Ripetere il deposito di «{deposito['atto']}»", f"{deposito['fase']}: {deposito['attesa']}", "", "deposito telematico", fonti, HREF_COMUNICAZIONI))
    in_corso = depositi_letti["in_corso"]
    if not in_corso:
        return passi
    esito = dict((verifiche.get("esiti") or {}).get("depositi") or {})
    if esito.get("esito") == "pec_non_configurata":
        passi.append(Passo(2, "Configurare la casella PEC dello studio per il controllo automatico delle ricevute dei depositi", f"{len(in_corso)} depositi in corso: senza la PEC il presidio non può leggere le ricevute", "", "presidio depositi", ("dm44_art13",), "/impostazioni"))
        return passi
    if not verifiche.get("eseguita_il"):
        return passi  # il presidio non ha ancora controllato: nessun compito all'avvocato
    controllo = verifiche.get("eseguita_il_it") or "ultimo controllo automatico"
    fermi = [voce for voce in in_corso if giorno_oggi and data_da(voce["data"]) and (giorno_oggi - data_da(voce["data"])).days >= GIORNI_ATTESA_RICEVUTE]
    if len(fermi) > 3:
        fonti = _FONTI_DEPOSITO.get(fermi[-1].get("canale", ""), _FONTI_DEPOSITO["PCT_TELEMATICO"])
        passi.append(Passo(1, f"{len(fermi)} depositi senza esito della cancelleria dopo il controllo automatico delle ricevute", f"controllo del {controllo}; gli ultimi: " + ", ".join(f"«{voce['atto']}»" for voce in fermi[-3:]) + "; contattare la cancelleria o ripetere il deposito", "", "presidio depositi", fonti, HREF_COMUNICAZIONI))
        return passi
    for deposito in fermi:
        fonti = _FONTI_DEPOSITO.get(deposito.get("canale", ""), _FONTI_DEPOSITO["PCT_TELEMATICO"])
        giorni = (giorno_oggi - data_da(deposito["data"])).days
        passi.append(Passo(1, f"Deposito «{deposito['atto']}» senza esito da {giorni} giorni nonostante il controllo automatico delle ricevute", f"{deposito['fase']}, {deposito['attesa']}; controllo del {controllo}: contattare la cancelleria o ripetere il deposito", "", "presidio depositi", fonti, HREF_COMUNICAZIONI))
    return passi


def _passi_notifiche(notifiche_lette: dict[str, Any]) -> list[Passo]:
    passi: list[Passo] = []
    for notifica in notifiche_lette["fallite"]:
        passi.append(Passo(0, f"Rinnovare la notifica di «{notifica['atto']}»", notifica["stato_etichetta"], "", "presidio notifiche", ("cpc_147", "l53_art3bis"), HREF_COMUNICAZIONI))
    for notifica in notifiche_lette["aperte"]:
        if notifica in notifiche_lette["fallite"]:
            continue
        # Le ricevute le legge il presidio: i passi restano solo dove serve l'avvocato.
        if notifica["stato"] in {"SENT_WAITING_RAC", "RAC_RECEIVED"}:
            continue
        azione = notifica.get("prossima_azione") or f"Completare la notifica di «{notifica['atto']}»"
        fase = f" — fase: {notifica['fase_procedurale']}" if notifica.get("fase_procedurale") else ""
        passi.append(Passo(1, f"{azione} («{notifica['atto']}»)", f"{notifica['stato_etichetta']}{fase}", notifica.get("scadenza", ""), "presidio notifiche", tuple(notifica.get("fonti_procedurali") or ("l53_art3bis",)), HREF_COMUNICAZIONI))
    return passi


def _passi_pec(pec_letto: dict[str, Any], giorno_oggi: Any = None) -> list[Passo]:
    """Il presidio PEC collega, estrae e registra da solo; all'avvocato restano autenticità, omonimie e revisioni."""
    passi: list[Passo] = []
    for termine in pec_letto.get("termini_da_registrare", []):
        if not termine.get("da_rivedere"):
            continue  # lo registra il presidio
        scadenza = data_da(termine.get("scadenza"))
        if giorno_oggi and scadenza and scadenza < giorno_oggi:
            continue  # A historical, unconfirmed option is not an outstanding obligation.
        norma = f" ({termine['norma']})" if termine.get("norma") else ""
        titolo = f"Valutare l’eventuale opposizione alla trattazione scritta{norma}" if "127" in termine.get("norma", "") else f"Valutare il termine «{termine['tipo'] or 'termine'}»{norma}"
        motivo = f"PEC del {termine['data_pec']}: proposta calcolata dalla comunicazione; l’opposizione è una scelta della parte" if scadenza else f"PEC del {termine['data_pec']}: manca una data di scadenza verificabile; nessuna urgenza è attribuita automaticamente"
        passi.append(Passo(1 if scadenza else 3, titolo, motivo, termine.get("scadenza", ""), "presidio PEC", ("cpc_127ter",) if "127" in termine.get("norma", "") else ("cpc_136",), HREF_COMUNICAZIONI))
    for udienza in pec_letto.get("udienze_da_registrare", []):
        if not udienza.get("da_rivedere"):
            continue
        passi.append(Passo(1, f"Confermare l'udienza del {udienza['data'] or 'data da leggere'} che il presidio PEC propone dalla PEC del {udienza['data_pec']}", f"«{udienza['oggetto']}»: il presidio chiede una revisione prima di metterla in agenda", udienza.get("data", ""), "presidio PEC", ("dgsia_art21", "cpc_136"), HREF_COMUNICAZIONI))
    for messaggio in pec_letto.get("da_controllare", [])[-4:]:
        motivi = list(messaggio.get("motivi_controllo") or [])
        autenticita = [motivo for motivo in motivi if "firma" in motivo or "qualità" in motivo]
        if autenticita:
            passi.append(Passo(1, f"Verificare l'autenticità della PEC del {messaggio['data']} «{messaggio['oggetto']}»", ", ".join(autenticita) + ": il presidio la segnala, la decisione di farvi affidamento è dell'avvocato", "", "presidio PEC", ("dm44_art16", "dgsia_art21"), HREF_COMUNICAZIONI))
            continue
        if "evento da confermare" in motivi:
            passi.append(Passo(2, f"Confermare l'evento che il presidio PEC propone per la PEC del {messaggio['data']} «{messaggio['oggetto']}»", "il presidio non è certo della classificazione", "", "presidio PEC", ("dgsia_art21",), HREF_COMUNICAZIONI))
            continue
        if not messaggio.get("collegata") and messaggio.get("corrispondenza") == "cliente":
            passi.append(Passo(2, f"Confermare se la PEC del {messaggio['data']} «{messaggio['oggetto']}» riguarda questa pratica", "cita l'assistito ma non il numero di ruolo: il presidio non la collega da solo per non confondere omonimi", "", "presidio PEC", ("dgsia_art21",), HREF_COMUNICAZIONI))
        elif not messaggio.get("collegata") and messaggio.get("corrispondenza") == "rg":
            passi.append(Passo(2, f"Confermare il collegamento della PEC del {messaggio['data']} «{messaggio['oggetto']}»", "cita il numero di ruolo ma il mittente non è un ufficio giudiziario: il presidio la collega solo su conferma", "", "presidio PEC", ("dgsia_art21",), HREF_COMUNICAZIONI))
    return passi


def _passi_conformita(conformita: dict[str, Any]) -> list[Passo]:
    passi: list[Passo] = []
    for voce in list(conformita.get("blocking_issues") or [])[:3]:
        testo = pulisci(voce.get("message") or voce.get("label") or voce) if isinstance(voce, dict) else pulisci(voce)
        if testo:
            passi.append(Passo(0, f"Risolvere: {testo}", "controllo di conformità bloccante", "", "conformità", (), HREF_PRESIDIO))
    for voce in list(conformita.get("missing_documents") or [])[:3]:
        testo = pulisci(voce.get("label") or voce.get("name") or voce) if isinstance(voce, dict) else pulisci(voce)
        if testo:
            passi.append(Passo(2, f"Acquisire il documento mancante: {testo}", "richiesto dal profilo di conformità", "", "conformità", (), HREF_DOCUMENTI))
    return passi


def _passi_fase(fase_letta: dict[str, Any], depositi_letti: dict[str, Any], notifiche_lette: dict[str, Any], documenti_letti: dict[str, Any]) -> list[Passo]:
    passi: list[Passo] = []
    codice = fase_letta.get("codice")
    if codice == CODICE_FASE_PREPARATORIA and not notifiche_lette["tutte"]:
        passi.append(Passo(2, "Notificare l'atto introduttivo alla controparte", "l'atto risulta redatto ma nessuna notifica è registrata; via PEC si perfeziona con le ricevute di accettazione e di consegna", "", "lettura del fascicolo", ("l53_art3bis", "cpc_147"), HREF_COMUNICAZIONI))
    if codice == CODICE_FASE_NOTIFICATA and not depositi_letti["tutti"]:
        passi.append(Passo(1, "Iscrivere la causa a ruolo depositando l'atto notificato", "costituzione dell'attore entro dieci giorni dalla notificazione della citazione", "", "lettura del fascicolo", ("cpc_165", "dispatt_196sexies"), HREF_COMUNICAZIONI, "CIV_COSTITUZIONE_ATTORE_165"))
    if codice == CODICE_FASE_ISCRITTA and fase_letta.get("prossima_udienza"):
        passi.append(Passo(2, f"Preparare l'udienza del {fase_letta['prossima_udienza']}", "memorie integrative a pena di decadenza: la prima almeno quaranta giorni prima dell'udienza", fase_letta["prossima_udienza"], "lettura del fascicolo", ("cpc_171ter", "cpc_183"), HREF_SCADENZE, "CIV_MEMORIA_171_TER_1"))
    if codice == CODICE_FASE_DECISA:
        passi.append(Passo(1, "Valutare l'impugnazione o l'esecuzione della sentenza", "appello entro trenta giorni dalla notificazione della sentenza, o entro sei mesi dalla pubblicazione se non notificata", "", "lettura del fascicolo", ("cpc_325", "cpc_327"), HREF_DOCUMENTI, "CIV_APPELLO_BREVE"))
    if codice == CODICE_FASE_ESECUTIVA:
        precetto = next((voce for voce in documenti_letti["tutti"] if "precetto" in voce["etichetta"].lower()), None)
        if precetto:
            passi.append(Passo(1, "Iniziare l'esecuzione prima che il precetto perda efficacia", "il precetto diventa inefficace se entro novanta giorni dalla notificazione non è iniziata l'esecuzione", "", "lettura del fascicolo", ("cpc_481",), HREF_DOCUMENTI, "ESE_PRECETTO_EFFICACIA_90GG"))
    if codice != CODICE_FASE_CHIUSA and fase_letta.get("incoerenze"):
        for incoerenza in fase_letta["incoerenze"]:
            passi.append(Passo(2, incoerenza[:1].upper() + incoerenza[1:], "stato del fascicolo non coerente con gli atti", "", "lettura del fascicolo", (), HREF_PRESIDIO))
    return passi


def _passi_documenti(documenti_letti: dict[str, Any], verifiche: dict[str, Any]) -> list[Passo]:
    """I documenti li legge il presidio documentale; all'avvocato restano classificazione, copie illeggibili e procura."""
    passi: list[Passo] = []
    non_indicizzati = documenti_letti["non_indicizzati"]
    letti_ma_ignoti = [voce for voce in documenti_letti["da_verificare"] if voce["indicizzato"]]
    if letti_ma_ignoti:
        quanti = len(letti_ma_ignoti)
        passi.append(Passo(3, f"Classificare {quanti} document{'o' if quanti == 1 else 'i'} che il contenuto non identifica", "il presidio documentale li ha letti ma nessuna regola li riconosce: la classificazione è una scelta dell'avvocato", "", "catalogazione", (), HREF_CATALOGO))
    da_acquisire = documenti_letti.get("da_acquisire") or []
    if da_acquisire:
        quanti = len(da_acquisire)
        passi.append(Passo(2, f"Acquisire dal portale {quanti} document{'o censito' if quanti == 1 else 'i censiti'} ma non scaricat{'o' if quanti == 1 else 'i'}", "il presidio documentale non può leggerli finché non sono nel fascicolo: lo scarico richiede la sessione autenticata sul portale (PST: CNS/CIE/SPID)", "", "presidio documentale", (), HREF_DOCUMENTI))
    esito = dict((verifiche.get("esiti") or {}).get("documenti") or {})
    errori = int(esito.get("errori") or 0)
    if errori:
        passi.append(Passo(2, f"Fornire una copia leggibile di {errori} document{'o' if errori == 1 else 'i'}", "il presidio documentale non è riuscito a leggerli (riconoscimento del testo fallito)", "", "presidio documentale", (), HREF_DOCUMENTI))
    proposte = int(documenti_letti.get("proposti") or 0)
    if proposte > 0:
        passi.append(Passo(3, f"Confermare con un clic le {proposte} propost{'a' if proposte == 1 else 'e'} di catalogazione pronte", "il presidio ha identificato i documenti dal contenuto con la prova; la conferma resta dell'avvocato", "", "catalogazione", (), HREF_CATALOGO))
    if documenti_letti["totale"] and not documenti_letti.get("procura") and not non_indicizzati and not da_acquisire:
        passi.append(Passo(2, "Acquisire la procura alle liti", "non risulta fra i documenti del fascicolo, tutti letti dal presidio documentale", "", "catalogazione", ("cpc_165",), HREF_DOCUMENTI))
    return passi


def _passi_economico(economico_letto: dict[str, Any]) -> list[Passo]:
    passi: list[Passo] = []
    if not economico_letto.get("presente"):
        return passi
    if not economico_letto.get("ha_incarico"):
        passi.append(Passo(3, "Formalizzare preventivo e conferimento d'incarico", "nessun preventivo o conferimento risulta collegato: il compenso è pattuito per iscritto e la misura prevedibile del costo è comunicata al cliente", "", "presidio economico", ("l247_art13",), HREF_PRESIDIO))
    liquidazione = economico_letto.get("liquidazione") or {}
    liquidato_it = economico_letto.get("liquidato_it") or ""
    if economico_letto.get("liquidato"):
        fonte = f" ({liquidazione['fonte']})" if liquidazione.get("fonte") else ""
        quando = f" del {liquidazione['data']}" if liquidazione.get("data") else ""
        if liquidazione.get("stato") == "da_registrare":
            passi.append(Passo(2, f"Confermare nel presidio economico la liquidazione di {liquidato_it} letta dalla sentenza{quando}", f"il presidio l'ha letta automaticamente{fonte}: va confermata per diventare credito da riscuotere", "", "presidio economico", (), HREF_PRESIDIO))
        stato_incasso = economico_letto.get("liquidazione_incasso")
        if stato_incasso == "non_incassata":
            passi.append(Passo(1, f"Riscuotere la somma liquidata dal giudice ({liquidato_it}): non risulta bonificata sul conto dello studio", f"sentenza{quando}{fonte}; incassato finora {economico_letto.get('incassato_it') or '€ 0,00'} (in Fatturazione)", "", "presidio economico", (), "/fatturazione"))
        elif stato_incasso == "parziale":
            passi.append(Passo(1, f"Completare la riscossione della somma liquidata ({liquidato_it}): incassato {economico_letto.get('incassato_it')}", f"sentenza{quando}{fonte}; il resto non risulta bonificato", "", "presidio economico", (), "/fatturazione"))
    if float(economico_letto.get("incassato_bonifico") or 0) > float(economico_letto.get("fatturato") or 0):
        passi.append(Passo(2, f"Emettere la parcella per l'incasso ricevuto ({economico_letto.get('incassato_bonifico_it')})", "i bonifici registrati superano il fatturato del fascicolo", "", "presidio economico", (), "/fatturazione/nuova"))
    if float(economico_letto.get("anticipazioni_da_recuperare") or 0) > 0:
        passi.append(Passo(3, f"Recuperare le anticipazioni ({economico_letto.get('anticipazioni_da_recuperare_it')})", "contributo unificato e spese anticipate dallo studio, non ancora rimborsate secondo il controllo pagamenti", "", "presidio economico", (), HREF_PRESIDIO))
    scadute = economico_letto.get("parcelle_scadute") or []
    if scadute:
        numeri = ", ".join(voce["numero"] or "senza numero" for voce in scadute[:3])
        passi.append(Passo(1, f"Sollecitare l'incasso di {economico_letto['importo_scaduto_it']} di parcelle scadute", f"{len(scadute)} parcell{'a scaduta' if len(scadute) == 1 else 'e scadute'} ({numeri})", "", "presidio economico", (), HREF_PRESIDIO))
    elif float(economico_letto.get("saldo_aperto") or 0) > 0:
        passi.append(Passo(3, f"Seguire l'incasso del saldo aperto di {economico_letto['saldo_aperto_it']}", f"fatturato {economico_letto['fatturato_it']}, incassato {economico_letto['incassato_it']}", "", "presidio economico", (), HREF_PRESIDIO))
    return passi


def prossimi_passi(
    *,
    intestazione: dict[str, Any],
    fase_letta: dict[str, Any],
    depositi_letti: dict[str, Any],
    notifiche_lette: dict[str, Any],
    documenti_letti: dict[str, Any],
    scadenze: list[dict[str, Any]],
    conformita: dict[str, Any],
    regia: dict[str, Any],
    economico_letto: dict[str, Any],
    pec_letto: dict[str, Any],
    verifiche: dict[str, Any] | None = None,
    oggi: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """I passi e lo stato dei passi (attivi o no, e perché)."""
    stato = stato_passi(intestazione)
    if not stato["attivi"]:
        return [], stato
    giorno_oggi = data_da(oggi)
    verifiche = dict(verifiche or {})
    passi: list[Passo] = []
    passi.extend(_passi_scadenze(scadenze, giorno_oggi))
    passi.extend(_passi_regia(regia, passi))
    passi.extend(_passi_depositi(depositi_letti, verifiche, giorno_oggi))
    passi.extend(_passi_notifiche(notifiche_lette))
    passi.extend(_passi_pec(pec_letto, giorno_oggi))
    passi.extend(_passi_conformita(conformita))
    passi.extend(_passi_fase(fase_letta, depositi_letti, notifiche_lette, documenti_letti))
    passi.extend(_passi_documenti(documenti_letti, verifiche))
    passi.extend(_passi_economico(economico_letto))

    for passo in passi:
        giorno = data_da(passo.entro)
        passo.scaduto = bool(giorno and giorno_oggi and giorno < giorno_oggi)
    passi.sort(key=lambda passo: (passo.scaduto, passo.urgenza))
    visti: set[str] = set()
    unici: list[dict[str, Any]] = []
    for passo in passi:
        chiave = passo.azione.lower()
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(passo.come_dizionario())
    return unici, stato


__all__ = ["GIORNI_ATTESA_RICEVUTE", "GIORNI_PROSSIMI", "MASSIMO_PASSI", "STATI_SENZA_PASSI", "prossimi_passi", "stato_passi"]
