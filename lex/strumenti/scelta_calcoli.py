"""Quale calcolatore serve alla domanda e con quali campi, anche quando l'avvocato descrive la situazione.

Precedenza al calcolo: se la domanda chiede «entro quando», «quanto», «a quanto ammonta», «spetta», «quando scade»,
«si prescrive»… e descrive una situazione che un calcolatore risolve (``usi_calcolatori.USI``), il calcolo prevale sui
dati dello studio («sentenza notificata», «scade», «udienza» non bastano a mandare la domanda allo scadenziario o alle
ricevute). Una domanda sui dati dello studio («abbiamo», «nostro», «nel fascicolo», «in agenda») senza date né importi
non è un calcolo.
"""
from __future__ import annotations

import re
from functools import lru_cache

from . import estrazione as ex
from .mappa import mappa
from .usi_calcolatori import CAMPI_DA_USO, USI

RICHIESTA_DI_CALCOLO = re.compile(
    r"\be prescritt\w*|\bsi e prescritt\w*|caduto in prescrizione|ancora in tempo|(?:si puo|posso|possiamo|puo) ancora|\bcalcol\w*|\bquant[oaie]\b|a quanto ammont\w*|entro quando|(?:ultimo )?giorno utile|termine ultimo|\btermine (?:per|di)\b|\btermine\s*\?|quanto tempo|entro che (?:data|giorno)|fino a quando|quando scade|"
    r"quando (?:si )?(?:prescrive|perfeziona|matura)|\bscade\b|\bscadono\b|\bspett\w*\b|devo pagare|\bcosta\b|\bcostano\b|"
    r"\bverific\w*|\bstima\w*|\bdetermin\w*|\brivaluta\w*|\bscorpor\w*|in tempo per|sono ancora in tempo|e usurari\w*|"
    r"supera la soglia|che grado|chi eredita|\bcompetent\w*|\be obbligatori\w*|serve (?:la|il) (?:mediazione|negoziazione)|"
    r"\bmi fai (?:il )?(?:calcolo|conto)|\bconteggi\w*|a quanto (?:si riduce|arriva)|che pena|quale pena|come si (?:liquid|calcol)\w*")
DATI_DELLO_STUDIO = re.compile(
    r"\babbiamo\b|\bnostr\w|\blo studio\b|nello scadenziario|\bin agenda\b|nel fascicolo|quest[oa] (?:incarico|pratica|causa|fascicolo)|"
    r"del cliente|ricevut\w* (?:e )?(?:arrivat|ricevut)|e arrivat\w*|sono arrivat\w*|abbiamo ricevut")


def _numeri_o_date(t: str) -> bool:
    return bool(ex.date_it(t) or ex.importi(t) or ex.percentuali(t) or re.search(
        r"\b\d{1,3}(?:\.\d{3})+\b|\b\d+ (?:anni|mesi|giorni|punti|figli|vacazioni)\b|\b(?:nel|del|dal) (?:19|20)\d{2}\b", t))


@lru_cache(maxsize=1)
def _usi_compilati() -> tuple[tuple[str, int, re.Pattern[str]], ...]:
    calcolatori = mappa()["calcolatori"]
    return tuple((i, p, re.compile(e)) for i, p, e in USI if i in calcolatori)


def punteggi_usi(t: str) -> dict[str, int]:
    """Per ogni calcolatore il peso dell'uso più specifico riconosciuto (non la somma: tre usi generici non battono un uso
    specifico come «interessi con acconti»); a parità di peso conta quanti usi corrispondono (decimi)."""
    pesi: dict[str, int] = {}
    quanti: dict[str, int] = {}
    for ident, peso, schema in _usi_compilati():
        if schema.search(t):
            pesi[ident] = max(pesi.get(ident, 0), peso)
            quanti[ident] = quanti.get(ident, 0) + 1
    return {i: pesi[i] * 10 + min(quanti[i], 9) for i in pesi}


# Calcolatori dei termini e della procedura: si scelgono solo fra quelli del rito della domanda.
PROCEDURALI = frozenset({"impugnazioni", "termini_processuali", "termini_penali", "indagini_preliminari", "custodia_cautelare",
                         "custodia_durata", "improcedibilita_penale", "competenza_valore", "perfezionamento_notifica",
                         "prescrizione", "prescrizione_penale", "procedibilita_adr"})
AMMESSI_PER_RITO = {
    "penale": {"termini_penali", "indagini_preliminari", "custodia_cautelare", "custodia_durata", "improcedibilita_penale",
               "prescrizione_penale", "perfezionamento_notifica"},
    "sanzioni": {"termini_processuali", "perfezionamento_notifica"},
    "condominio": {"termini_processuali", "perfezionamento_notifica", "procedibilita_adr"},
    "tributario": {"termini_processuali", "perfezionamento_notifica"},
    "amministrativo": {"termini_processuali", "perfezionamento_notifica"},
    "lavoro": {"impugnazioni", "termini_processuali", "perfezionamento_notifica", "prescrizione", "procedibilita_adr"},
}
PREDEFINITO_PER_RITO = {"penale": "termini_penali", "sanzioni": "termini_processuali", "condominio": "termini_processuali",
                        "tributario": "termini_processuali", "amministrativo": "termini_processuali", "lavoro": "impugnazioni"}
_DOMANDA_DI_TERMINE = re.compile(r"entro quando|quando scade|\btermin\w*|\bscad\w*|giorno utile|fino a quando|"
                                 r"\bimpugn\w*|\bappell\w*|\bricors\w*|\bopposizion\w*|\boppor\w*|in tempo")


def _secondo_il_rito(t: str, ordinati: list[tuple[str, int]]) -> str | None:
    """Il calcolatore procedurale ammesso dal rito; None se il rito non è detto o la domanda non è di termini."""
    r = ex.rito(t)
    if not r or not ordinati or not (ordinati[0][0] in PROCEDURALI or _DOMANDA_DI_TERMINE.search(t)):
        return None
    if ordinati[0][0] not in PROCEDURALI:
        # Una domanda di termine («entro quando», «quando scade») con un rito detto resta un calcolo di termini.
        if re.search(r"entro quando|quando scade|giorno utile|fino a quando|\btermine (?:per|di)\b|quanto tempo", t):
            return next((i for i, _ in ordinati if i in AMMESSI_PER_RITO[r]), PREDEFINITO_PER_RITO[r])
        # Un atto del rito notificato o ricevuto che si vuole impugnare («ricorso contro l'avviso di accertamento IRPEF
        # ricevuto il …»): il calcolo è il termine, non l'imposta nominata nell'atto.
        if (ordinati[0][1] < 40 and re.search(r"\bimpugn\w*|\bricors\w*|\bopposizion\w*|\boppor\w*|\bappell\w*|\bcontestar\w*", t)
                and re.search(r"notificat\w*|ricevut\w*|consegnat\w*|\b\d{1,2}/\d{1,2}/\d{4}\b", t) and not re.search(r"\bquant[oaie]\b", t)):
            return next((i for i, _ in ordinati if i in AMMESSI_PER_RITO[r]), PREDEFINITO_PER_RITO[r])
        return ordinati[0][0]
    ammessi = AMMESSI_PER_RITO[r]
    for ident, _ in ordinati:
        if ident in ammessi:
            return ident
    return PREDEFINITO_PER_RITO[r] if _DOMANDA_DI_TERMINE.search(t) else None


def calcolatore(domanda: str) -> str:
    """Il calcolatore che la domanda chiede; vuoto se non è un calcolo o se due calcolatori si equivalgono.
    Per i termini prima si riconosce il rito (penale, lavoro, condominio, tributario, amministrativo, sanzioni) e si
    sceglie solo fra i calcolatori di quel rito: un appello penale non è un appello civile."""
    from lex.calcoli_certi.riconoscimento import scegli_strumento

    t = ex.normalizza(domanda)
    chiede = bool(RICHIESTA_DI_CALCOLO.search(t))
    dati = _numeri_o_date(t)
    # Quanto si DEVE per legge, o entro quando: decide il calcolatore. Il dato dello studio vale solo se si chiede che cosa
    # è stato registrato, pagato, incassato o emesso.
    dovuto = re.search(r"quanto (?:si |devo |dobbiamo |deve |devono )?(?:deve|dovr\w*|versare|pagare|chiedere|spetta|costa)|"
                       r"per legge|\bdovut\w*|\bspett\w*|entro quando|quando scade|\btermine\b|giorno utile|"
                       r"\bminimo\b|\bmassimo\b|parametri|a quanto ammont|\bcalcol\w*|in ritardo|di ritardo|\btardi\b|ridurre (?:la )?sanzion\w*|tardiv\w*|regolarizz\w*|"
                       r"cosa comporta|quanto (?:prender\w*|gli spetta|le spetta|mi spetta)|quanto si paga|quanto costa|devo pagare|"
                       # i verbi del ricevere: quanto prende, riceve, incassa, porta a casa, gli danno
                       r"quanto (?:\w+ )?(?:prend\w*|ricev\w*|incass\w*|porta a casa|gli dann\w*|le dann\w*|mi dann\w*|(?:gli |le |mi )?verr\w*)|"
                       r"(?:si puo|posso|possiamo|puo) ancora|in piu\b|in regola", t)
    registrato = re.search(r"(?:ha|hanno|abbiamo|risulta|(?:e|sono) (?:gia )?stat\w*) (?:gia |gia' )?(?:pagat|versat|incassat|registrat|emess|fatturat|"
                           r"saldat|ricevut)\w*|(?:pagat|incassat|registrat|emess|fatturat)\w* (?:dal cliente|nel fascicolo|in contabilita)", t)
    # Un uso che nomina l'istituto da calcolare (ravvedimento, TFR…) vale anche se la domanda parla del cliente o di un
    # pagamento in ritardo: «il cliente ha pagato in ritardo la cartella: ravvedimento?» è un calcolo.
    # Il verbo e il suo tempo decidono: passato o registrato → contabilità del fascicolo; dovuto → calcolatore.
    gia_registrato = re.search(r"\bgia (?:pagat|versat|incassat|emess|registrat|fatturat|saldat)\w*|\brisulta\w* (?:pagat|versat|incassat|emess|registrat|saldat)|\brisulta\w*|(?:abbiamo|ho|ha|hanno|avete) (?:gia )?(?:pagat|versat|emess|incassat|registrat|"
                               r"fatturat|saldat|anticipat)\w*|(?:e|sono) (?:gia )?stat\w* (?:pagat|versat|incassat|emess|registrat|saldat)\w*", t)
    istituto_nominato = (not gia_registrato or dovuto) and any(p >= 40 for p in punteggi_usi(t).values())
    if (registrato or gia_registrato) and not dovuto and not istituto_nominato:
        return ""
    if DATI_DELLO_STUDIO.search(t) and not dati and not dovuto and not istituto_nominato:
        return ""
    if re.search(r"\bcalcol\w*|mi fai il calcolo", t):  # «calcola <nome del calcolatore>»: vale il nome
        presenti = [(t.find(titolo), -len(titolo), ident) for titolo, ident in
                    ((ex.normalizza(v["titolo"]).split(" — ")[0], k) for k, v in mappa()["calcolatori"].items())
                    if len(titolo) >= 6 and titolo in t]
        if presenti:  # il nome che viene per primo (subito dopo «calcola»), a parità il più lungo
            return min(presenti)[2]
    punteggi = punteggi_usi(t)
    if punteggi:
        ordinati = sorted(punteggi.items(), key=lambda x: -x[1])
        primo, peso = ordinati[0]
        del_rito = _secondo_il_rito(t, ordinati)
        if del_rito and (chiede or dati or peso >= 30):
            return del_rito
        # Peso 4: l'uso nomina un istituto che si risolve solo con il calcolatore («legittima lesa», «pensione di
        # reversibilità», «che parentela c'è»): basta da solo.
        peso_uso = peso // 10
        pari = len(ordinati) > 1 and ordinati[1][1] // 10 == peso_uso and ordinati[1][1] == peso
        if not pari and (peso_uso >= 4 or (peso_uso >= 3 and (chiede or dati)) or (peso_uso >= 2 and chiede)):
            return primo
        if pari and chiede:
            certo = scegli_strumento(domanda, {k: v["titolo"] for k, v in mappa()["calcolatori"].items()})
            if certo in {i for i, p in ordinati if p == peso}:
                return certo
    # Solo dati raccontati, nessuna domanda espressa: un atto del rito notificato o ricevuto con la sua data è un termine.
    r = ex.rito(t)
    if not punteggi and r and ex.date_it(domanda) and re.search(r"notificat\w*|ricevut\w*|depositat\w*|pubblicat\w*|comunicat\w*|\blett[ao]\b|emess[ao]|pronunciat[ao]", t):
        return PREDEFINITO_PER_RITO[r]
    if chiede:
        scelto = scegli_strumento(domanda, {k: v["titolo"] for k, v in mappa()["calcolatori"].items()})
        r = ex.rito(t)
        if scelto in PROCEDURALI and r and scelto not in AMMESSI_PER_RITO[r]:
            return PREDEFINITO_PER_RITO[r]
        if not scelto and r and _DOMANDA_DI_TERMINE.search(t) and re.search(r"entro quando|quando scade|giorno utile|fino a quando|termine|quanto tempo", t):
            return PREDEFINITO_PER_RITO[r]
        return scelto
    return ""


# Un evento del processo con la sua data (o con la domanda di termine) chiede il calcolo del termine, anche se nomina
# un'udienza, una PEC, il cliente o un fascicolo. Ogni voce: calcolatore, campo e valore del modello, evento.
EVENTI_PROCESSUALI: tuple[tuple[str, str, str, str], ...] = (
    ("termini_penali", "tp_atto", "motivi_nuovi", r"motivi (?:nuovi|aggiunti)\b.{0,80}(?:appell|condann|penal|585|corte d'appello|udienza)|"
                                                  r"(?:appell\w* penal\w*|condann\w*|585 c\.?p\.?p).{0,80}motivi (?:nuovi|aggiunti)"),
    ("perfezionamento_notifica", "", "", r"(?:quando|da quando) (?:si )?(?:perfeziona|e perfezionat|si considera perfezionat)|perfezionat\w* per il (?:notificante|destinatario)|"
                                         r"notific\w*.{0,80}(?:consegnat\w* alle|ricevut\w* dal destinatario|spedit\w*).{0,80}(?:perfezion|decorr|da quando)|"
                                         r"perfezionamento (?:della )?notific"),
    ("termini_processuali", "term_modello", "CIV_COSTITUZIONE_CONVENUTO_166",
     r"(?:costitu\w*|comparsa(?: di risposta)?).{0,80}(?:convenut\w*|udienza)|(?:convenut\w*|citazione notificat\w*|citat\w* in giudizio|udienza).{0,100}(?:costitu\w*|comparsa)|"
     r"costituzione del convenuto"),
    ("termini_processuali", "term_modello", "CIV_IMPUGNAZIONE_DELIBERA_1137",
     r"(?:delibera\w*|verbale (?:dell'|della )?assemblea).{0,40}(?:condomin\w*).{0,80}(?:ricevut|arrivat|comunicat|notificat|impugn|\d{1,2}/\d{1,2}/\d{4})|"
     r"condomin\w*.{0,40}(?:delibera\w*|verbale).{0,80}(?:ricevut|arrivat|comunicat|impugn|\d{1,2}/\d{1,2}/\d{4})"),
    ("termini_processuali", "term_modello", "CIV_RECLAMO_CAUTELARE_669_TERDECIES",
     r"(?:ordinanza|provvedimento) cautelar\w*.{0,80}(?:reclam|comunicat|\d{1,2}/\d{1,2}/\d{4})|reclam\w*.{0,60}(?:cautelar|ricorso d'urgenza|\b700\b)|"
     r"(?:ricorso d'urgenza|\b700 c\.?p\.?c|sequestro).{0,80}(?:rigettat|accolt|respint|reclam)"),
    ("termini_processuali", "term_modello", "AMM_APPALTI_120",
     r"aggiudicazion\w*.{0,100}(?:comunicat|ricevut|notificat|impugn|ricorr|\d{1,2}/\d{1,2}/\d{4})|esclusion\w* dalla gara|"
     r"(?:gara|appalto).{0,60}(?:aggiudicat|esclus).{0,60}(?:impugn|ricorr|\d{1,2}/\d{1,2}/\d{4})"),
    ("impugnazioni", "imp_mezzo", "cassazione", r"sentenza (?:della corte )?d'appello.{0,120}(?:cassazione)|cassazione.{0,30}(?:contro|avverso) (?:la )?sentenza|(?:ricors\w*|ricorrere) (?:in|per) cassazione.{0,80}(?:notificat|pubblicat|depositat|\d{1,2}/\d{1,2}/\d{4})"),
)


def calcolo_per_evento(domanda: str) -> str:
    """Il calcolatore del termine se la domanda racconta un evento del processo con la data o chiede il termine;
    vuoto se non c'è un evento o se si chiede che cosa è già stato fatto («abbiamo già depositato la comparsa?»)."""
    t = ex.normalizza(domanda)
    if re.search(r"\bgia (?:depositat|fatt|presentat|notificat|pagat|versat)|(?:abbiamo|ho|hanno) (?:gia )?(?:depositat|presentat|fatto)\w*|"
                 r"\bmodell\w*|fac[- ]?simile|\bbozza\b|come si (?:fa|procede|redige)", t):
        return ""
    termine = bool(ex.date_it(domanda)) or bool(re.search(
        r"entro quando|quando scade|ultimo giorno|giorno utile|\btermine\b|\btermini\b|in tempo|possiamo ancora|posso ancora|vogliamo|voglio|"
        r"da quando|quando si|\bimpugn\w*|\breclam\w*|\bricorr\w*", t))
    if not termine:
        return ""
    for ident, _campo, _valore, schema in EVENTI_PROCESSUALI:
        if re.search(schema, t) and ident in mappa()["calcolatori"]:
            return ident
    return ""


def campi(ident: str, domanda: str) -> dict[str, object]:
    """I campi del calcolatore: quelli scritti nella domanda e quelli resi certi dall'uso nominato."""
    voce = mappa()["calcolatori"][ident]
    uscita = ex.campi_calcolatore(domanda, voce["campi"])
    t = ex.normalizza(domanda)
    for calc, campo, valore, schema in CAMPI_DA_USO:
        if calc == ident and campo not in uscita and campo in voce["campi"] and re.search(schema, t):
            if valore in voce["campi"][campo].get("valori", [valore]):
                uscita[campo] = valore
    # L'evento del processo fissa il modello del termine (costituzione, delibera, reclamo, appalti, motivi nuovi…).
    for calc, campo, valore, schema in EVENTI_PROCESSUALI:
        if (calc == ident and campo and campo in voce["campi"] and campo not in uscita and re.search(schema, t)
                and valore in voce["campi"][campo].get("valori", [valore])):
            uscita[campo] = valore
            break
    # Il rito fissa il modello di termine e le regole (sospensione feriale esclusa nel rito del lavoro: art. 3 l. 742/1969).
    r = ex.rito(t)
    scelte_rito = {
        ("termini_processuali", "tributario"): ("term_modello", "TRIB_APPELLO_51" if re.search(r"appell", t) else "TRIB_RICORSO_21"),
        ("termini_processuali", "amministrativo"): ("term_modello", "AMM_APPELLO_92" if re.search(r"appell", t) else
                                                    "AMM_APPALTI_120" if re.search(r"appalt|gara", t) else "AMM_RICORSO_29"),
        ("termini_processuali", "condominio"): ("term_modello", "CIV_IMPUGNAZIONE_DELIBERA_1137"),
        ("termini_penali", "penale"): ("tp_atto", "impugnazione_sentenza" if re.search(r"appell|impugn|cassazione", t) else ""),
        ("impugnazioni", "lavoro"): ("imp_sospensione_feriale", "esclusa"),
    }
    if (ident, r) in scelte_rito:
        campo, valore = scelte_rito[(ident, r)]
        if valore and campo in voce["campi"] and campo not in uscita and valore in voce["campi"][campo].get("valori", []):
            uscita[campo] = valore
    # Il decreto prefettizio di espulsione (art. 18 d.lgs. 150/2011, non il CdS) è già fissato da CAMPI_DA_USO
    # (usi_calcolatori.py), che viene prima: qui non arriva mai senza modello.
    if ident == "termini_processuali" and r == "sanzioni" and "term_modello" not in uscita:
        if re.search(r"prefett", t):
            uscita["term_modello"] = "CDS_RICORSO_PREFETTO_60GG"
        elif re.search(r"giudice di pace", t):
            uscita["term_modello"] = "CDS_RICORSO_GDP_30GG"
    # «notificata il …» è la data di notificazione, non di pubblicazione.
    if ident == "impugnazioni" and re.search(r"notificat\w*", t) and not re.search(r"pubblicat\w*|depositat\w*", t):
        if "imp_data_pubblicazione" in uscita and "imp_data_notificazione" not in uscita:
            uscita["imp_data_notificazione"] = uscita.pop("imp_data_pubblicazione")
    # Una data sola in una domanda di termine è l'evento da cui il termine decorre.
    date = ex.date_it(domanda)
    if len(date) == 1:
        evento = [n for n, c in voce["campi"].items() if c["tipo"] == "date" and n not in uscita and re.search(
            r"evento|pubblicazione|notificazione|decorrenza|invio|fatto|data_inizio|sinistro", n)]
        gia = [n for n, v in uscita.items() if v == date[0]]
        if evento and not gia:
            nome = next((n for n in evento if "notific" in n and re.search(r"notificat", t)), evento[0])
            uscita[nome] = date[0]
    return uscita


__all__ = ["DATI_DELLO_STUDIO", "EVENTI_PROCESSUALI", "RICHIESTA_DI_CALCOLO", "calcolatore", "calcolo_per_evento", "campi", "punteggi_usi"]
