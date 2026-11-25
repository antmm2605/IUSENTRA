"""Scelta deterministica degli strumenti per una domanda, sulla mappa generata dal codice.

È il riferimento con cui si misura il modello piccolo addestrato a scegliere lo strumento e la guida che il retrieval
usa per non interrogare fonti che la domanda non chiede. Procede per categorie di richiesta, dalla più specifica:

1. calcolo con un calcolatore riconoscibile (titolo, sinonimi d'uso) e una richiesta di calcolo;
2. modelli d'atto e loro norme; procedure guidate;
3. fonti pubbliche citate: Gazzetta, prassi, pronuncia per estremi, articolo citato, giustizia amministrativa,
   Cassazione e Consulta, norma per argomento, aggiornamenti, siti ufficiali;
4. dati dello studio: fascicolo (quadro, catena, Lettura, documenti), economia, clienti, scadenze, agenda, PEC,
   notifiche e ricevute, avvisi, ricerca nello studio; deposito telematico; pagine del software.
Nessun segnale: lista vuota (decide il percorso ordinario). I parametri vengono da ``lex.strumenti.estrazione``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import estrazione as ex
from .mappa import mappa

normalizza = ex.normalizza


@dataclass
class Chiamata:
    nome: str
    parametri: dict[str, Any] = field(default_factory=dict)
    motivo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"nome": self.nome, "parametri": {k: v for k, v in self.parametri.items() if v not in (None, "", {})}}


def _c(nome: str, motivo: str, **parametri: Any) -> Chiamata:
    return Chiamata(nome, {k: v for k, v in parametri.items() if v not in (None, "", {})}, motivo)


def _ha(t: str, schema: str) -> bool:
    return re.search(schema, t) is not None


# ------------------------------------------------------------------------------------------------ calcolatori
# calcolatore è riesportato: lex.strumenti.scelta.calcolatore
from .scelta_calcoli import calcolatore, calcolo_per_evento  # noqa: E402
from .scelta_calcoli import campi as _campi_calcolo  # noqa: E402


# ------------------------------------------------------------------------------------------------ testi liberi
def _dopo(t: str, schema: str, *, fino: str = r"(?:\s+(?:e (?:dimmi|poi|trovami)|con le|dal catalogo|secondo il|sul|per favore)\b|[?!]|\s*$)") -> str:
    m = re.search(schema + r"\s*(.+?)" + fino, t)
    if not m:
        return ""
    valore = m.group(1).strip(" ,:;'\"«»")
    valore = re.sub(r"^(?:(?:il|lo|la|i|gli|le|un|una|uno)\s+|l'|un')", "", valore)
    return valore.rstrip(" .") if not re.search(r"\b[a-z]\.[a-z]\.(?:[a-z]\.)?$", valore) else valore


def _atto_redazione(t: str) -> str:
    for schema in (r"\bmodell[oi] (?:di|del|della|dello|per)", r"\bfac[- ]?simile di", r"\bbozza di", r"\bschema (?:pronto )?(?:di|per)",
                   r"\brequisiti (?:del|della|dello|dell')", r"\bmodello d'atto (?:di|per)"):
        valore = _dopo(t, schema)
        if valore:
            return valore
    return ""


def _procedura(t: str) -> str:
    istituto = ex.togli_cornice(t)
    if istituto and len(istituto.split()) <= 8 and istituto != normalizza(t).strip(" ?.!"):
        return istituto
    return _procedura_da_schemi(t)


def _procedura_da_schemi(t: str) -> str:
    for schema in (r"\bcome si (?:procede|fa) (?:per|con|un|una|l')", r"\bpassi,? termini e allegati per", r"\bguida pratica:?",
                   r"\bche cosa serve per (?:avviare|fare|proporre)?", r"\bcosa serve per (?:avviare|fare|proporre)?",
                   r"\biter (?:di|del|della|per)", r"\bavviare", r"\bprocedura (?:di|del|della|per)"):
        valore = _dopo(t, schema, fino=r"(?:\s+(?:passo per passo|e (?:trovami|dimmi)|e schema|e il modello)\b|[?.!,]|$)")
        if valore:
            return valore
    return ex.togli_cornice(ex.argomento(t))


_PAROLE_RICERCA = {"cerca", "cercami", "trovami", "trova", "sito", "ufficiale", "vai", "sul", "del", "della", "dello", "e",
                   "il", "la", "le", "i", "gli", "lo", "mi", "serve", "per", "favore", "su", "nel", "web"}


def _ricerca_web(domanda: str) -> str:
    parole = re.findall(r"[\w'’]+", domanda)
    return " ".join(p for p in parole if normalizza(p) not in _PAROLE_RICERCA).strip()


def _persona(domanda: str) -> str:
    """Un nome proprio retto da «di/da/del/per/a» («i pagamenti di Castagnoli», «mail da Pianigiani», «preventivo per Tettamanzi srl»)."""
    m = re.search(r"\b(?:di|da|del|della|dal|dalla|per|a|al|alla|dell'|la societa|societa|la ditta|ditta|l'impresa|impresa)\s*"
                  r"((?:sig\.?(?:ra)?\s+|dott\.?(?:ssa)?\s+|avv\.?\s+)?"
                  r"[A-Z][\w'’]+(?:\s+[A-Z][\w'’]+)*(?:\s+(?:srl|spa|sas|snc))?)", domanda)
    if not m:
        return ""
    nome = m.group(1).strip(" ?,.")
    escluse = {"Cassazione", "Corte", "Tribunale", "Consiglio", "Stato", "Gazzetta", "Ufficiale", "Agenzia", "Entrate", "INPS",
               "TAR", "Lex", "IUSENTRA", "PEC", "SDI", "Prefetto", "Procura", "Repubblica", "Costituzione", "UNEP",
               "Agenzia delle Entrate Riscossione", "Cancelleria", "Ministero", "Comune", "Regione", "Garante", "CNF"}
    return "" if nome.split()[0] in escluse else nome


def _nome_proprio(domanda: str) -> str:
    """Il nome dopo «cliente», «assistito», «sig.»: parole con l'iniziale maiuscola, con l'eventuale forma societaria."""
    m = re.search(r"(?:cliente|assistit\w|sig\.|signor\w*)\s+((?:[A-Z][\w'’]+)(?:\s+[A-Z][\w'’]+)*(?:\s+(?:srl|spa|sas|snc|s\.r\.l\.|s\.p\.a\.))?)",
                  domanda)
    return m.group(1).strip(" ?,.") if m else ""


# ------------------------------------------------------------------------------------------------ fascicolo
_FASCICOLO = r"\b(?:quest[oa] (?:fascicolo|pratica|causa|incarico)|nel fascicolo|del fascicolo|della pratica|della causa|fascicolo aperto|pratica aperta|nella pratica|in questa pratica)\b"


def _sezione_quadro(t: str) -> str | None:
    for valore, schema in (("prossimi_passi", r"prossim\w* pass|cosa (?:devo|dobbiamo) fare|che cosa (?:devo|dobbiamo) fare"),
                           ("udienze", r"udienz"), ("termini", r"\btermin"), ("economia", r"economi"),
                           ("parti", r"\bparti\b|ruolo del cliente|controparti"), ("notifiche", r"notific"),
                           ("documenti", r"document")):
        if _ha(t, schema):
            return valore
    return None


def _parte_lettura(t: str) -> str | None:
    for valore, schema in (("cronologia", r"cronologi|in fila|ordine di data|eventi della"), ("atti", r"\batti\b"),
                           ("depositi", r"deposit"), ("notifiche", r"notific"), ("narrativa", r"vicenda|storia|raccont|riassum"),
                           ("fase", r"\bfase\b")):
        if _ha(t, schema):
            return valore
    return None


def _voce_economica(t: str) -> str | None:
    for valore, schema in (("sdi", r"\bsdi\b|sistema di interscambio|fattur\w* elettronic\w*|scartat\w*|codice destinatario|"
                                   r"notifica di scarto|ricevuta di consegna della fattura"),
                           ("spese_liquidate", r"liquidat|spese .{0,20}sentenza"), ("contributo_unificato", r"contributo unificato|\bcu\b"),
                           ("pagamenti", r"pagat|pagament|incass|saldat|\bsaldo\b|insolut\w*|non (?:ha )?pagat|da incassare|bonific\w*"),
                           ("parcelle", r"parcell|fattur|abbiamo emesso|emess\w*|proforma|notula"),
                           ("preventivi", r"(?<!tecnico )(?<!tecnica )(?<!concordato )preventiv(?!a)"), ("conferimenti", r"conferiment|mandato"),
                           ("attivita", r"\bore\b|timesheet|attivita registrat"),
                           ("conto", r"conto economico|situazione economica|bilancio")):
        if _ha(t, schema):
            return valore
    return None


# ------------------------------------------------------------------------------------------------ scelta
def scegli(domanda: str, *, fascicolo_aperto: bool = False, massimo: int = 3) -> list[Chiamata]:
    """Gli strumenti da interrogare, nell'ordine; vuota se nessun segnale è certo.

    La domanda si normalizza (accenti, refusi, linguaggio comune) prima di scegliere; i parametri si leggono dal testo
    corretto ma senza le aggiunte della normalizzazione. Le richieste in sequenza («… e poi calcola …») si scelgono
    una per una. Una pratica nominata (nome o numero di ruolo) vale come fascicolo indicato, mai come «corrente»."""
    from .normalizzazione import normalizza_domanda

    corretta = normalizza_domanda(domanda)
    pulita = re.sub(r"\s*\[[^\]]*\]\s*$", "", corretta)
    t = normalizza(corretta)
    if not t or _ha(t, r"^(?:ciao|buongiorno|buonasera|salve|grazie|ok|perfetto|va bene)\b[^?]{0,40}$") and not _ha(t, r"\?|calcol|cerca|trova"):
        return []
    pratica = ex.pratica_indicata(domanda)
    fa = fascicolo_aperto or bool(pratica) or _ha(t, _FASCICOLO)
    fascicolo = pratica or ("corrente" if fascicolo_aperto or _ha(t, _FASCICOLO) else "")
    parti = re.split(r"\s*(?:\be poi\b|,?\s*\bpoi\b|\binoltre\b|\be anche\b|\bquindi\b|\bdopodiche\b|\bdopo di che\b|\be infine\b|\be successivamente\b|"
                     r"\be (?=(?:la|le|i|il|gli|lo|l') ?(?:relativ\w*|passaggi|procedura|scheda|sentenze|giurisprudenz\w*|pronunce|norme|circolar\w*|novita|"
                     r"compensi|onorari|interessi|contributo|rivalutazione|termine|termini|testo|ricevute|scadenze|udienze|pec)\b)|"
                     r"\be (?:dopo |dopodiche )?(?=calcol|dimmi|trova|cerca|verifica|controlla|quanto|entro|leggi|apri|guarda|aggiorna|fammi|mostra|dammi|segna|registra)|"
                     r"(?<=[a-z0-9)])[.?!]\s+(?=(?:Calcol|Dimmi|Trova|Cerca|Verifica|Controlla|Leggi|Apri|Guarda|Poi|Quindi|"
                     r"Inoltre|Mostrami|Fammi|Dammi|Aggiungi|Entro|Quando|Quanto|Qual|Segna|Registra)))\s*", pulita)
    parti = [p for p in parti if len(p) >= 8]
    if len(parti) > 1:
        # Richieste in sequenza: la prima da sola, le altre con il contesto della prima («e poi le sentenze» si riferisce
        # all'articolo citato prima), infine la domanda intera per gli abbinamenti già noti (modello e sue norme).
        scelte: list[Chiamata] = []
        nomi: set[str] = set()

        def aggiungi(chiamate: list[Chiamata], *, anche_segnali: bool, richiesta_propria: bool = False) -> None:
            for c in chiamate:
                # «apri la pratica X e poi dimmi le prossime udienze»: la seconda richiesta ha il suo strumento (agenda o
                # scadenziario della pratica), non si fonde nel quadro già scelto.
                if (richiesta_propria and c.nome == "fascicolo_quadro" and c.nome in nomi
                        and c.parametri.get("sezione") in ("udienze", "termini")):
                    c = _c("agenda_udienze" if c.parametri["sezione"] == "udienze" else "scadenziario", c.motivo,
                           fascicolo=c.parametri.get("fascicolo"))
                # Un secondo calcolo diverso, chiesto da una sua richiesta («… poi la rivalutazione»), si aggiunge.
                nuovo_calcolo = (richiesta_propria and c.nome == "calcolo" and c.parametri.get("strumento") not in
                                 {x.parametri.get("strumento") for x in scelte if x.nome == "calcolo"})
                if c.nome in nomi and not nuovo_calcolo:  # stesso strumento letto di nuovo: si aggiungono i parametri che mancavano
                    gia = next(x for x in scelte if x.nome == c.nome)
                    if c.nome != "calcolo" or gia.parametri.get("strumento") == c.parametri.get("strumento"):
                        for k, v in c.parametri.items():
                            gia.parametri.setdefault(k, v)
                    continue
                if anche_segnali or c.motivo != "segnali della scheda":
                    scelte.append(c)
                    nomi.add(c.nome)

        aggiungi(_una_richiesta(parti[0], normalizza(parti[0]), fa, fascicolo), anche_segnali=True)
        for parte in parti[1:]:
            # La richiesta da sola, se basta; altrimenti con il contesto della prima («e poi le sentenze» dell'articolo citato).
            da_sola = [c for c in _una_richiesta(parte, normalizza(parte), fa, fascicolo) if c.motivo != "segnali della scheda"]
            con_contesto = f"{parte}. {parti[0]}"
            # Il contesto serve se la richiesta da sola non basta, o se il rito (penale, condominio, amministrativo…) è
            # detto solo nella prima parte: il termine si calcola con le regole di quel rito.
            rito_dal_contesto = not ex.rito(parte) and ex.rito(parti[0]) and any(c.nome == "calcolo" for c in da_sola)
            # «… e trovami un modello d'atto»: l'oggetto (l'atto, l'istituto) sta nella prima parte.
            senza_oggetto = any(re.fullmatch(r"(?:un |il |l')?(?:modell\w*|fac[- ]?simile|schema|bozza)(?: d'atto| di atto)?", str(v or "").strip())
                                for c in da_sola for v in c.parametri.values() if isinstance(v, str)) or any(
                c.nome in ("modelli_atto", "norme_modello") and not (c.parametri.get("cerca") or c.parametri.get("atto")) for c in da_sola)
            # «… che lo applicano», «la relativa giurisprudenza», «della stessa somma»: l'oggetto è nella prima parte.
            anaforica = bool(re.search(r"\b(?:che )?(?:lo|la|li|le) (?:applic|cit|richiam|interpret|disciplin|regol|prevede|preved)\w*|\brelativ\w*\b|"
                                       r"\b(?:stess[ao]|medesim[ao]) (?:articolo|norma)\b|"
                                       r"\b(?:stess[ao]|medesim[ao]) (?:somma|norma|articolo|importo|credito|atto|causa)\b|\bsu di (?:esso|essa)\b|"
                                       r"\b(?:quest[oa]|tale) (?:norma|articolo|disposizione)\b", normalizza(parte)))
            if anaforica and any(c.nome == "calcolo" for c in da_sola):
                # «poi la rivalutazione della stessa somma»: il calcolo è quello chiesto, i dati vengono dalla prima parte.
                for c in da_sola:
                    if c.nome == "calcolo":
                        c.parametri["campi"] = _campi_calcolo(c.parametri["strumento"], con_contesto) or None
                aggiungi(da_sola, anche_segnali=False, richiesta_propria=True)
                continue
            rito_dal_contesto = rito_dal_contesto or senza_oggetto
            if anaforica:
                # Il pronome si sostituisce con l'oggetto della prima parte: l'articolo citato o l'argomento.
                citato = ex.articolo_citato(parti[0])
                tema = ex.togli_cornice(ex.argomento(normalizza(parti[0])))
                oggetto = f"art. {citato[0]} {citato[1]}" if citato else tema
                testo_parte = f"{parte} {oggetto}"
                scelte_parte = [c for c in _una_richiesta(testo_parte, normalizza(testo_parte), fa, fascicolo)
                                if c.motivo != "segnali della scheda"] or _una_richiesta(con_contesto, normalizza(con_contesto), fa, fascicolo)
            else:
                scelte_parte = (_una_richiesta(con_contesto, normalizza(con_contesto), fa, fascicolo) if (not da_sola or rito_dal_contesto)
                                else da_sola)
            # «controlla le ricevute» dopo un deposito: le ricevute del deposito.
            for c in scelte_parte:
                if (c.nome == "notifiche_ricevute" and c.parametri.get("tipo") == "notificazioni" and not re.search(r"notific", normalizza(parte))
                        and re.search(r"deposit", normalizza(parti[0]))):
                    c.parametri["tipo"] = "ricevute_deposito"
            if anaforica:  # «la relativa giurisprudenza»: si cerca l'argomento della prima parte, non il pronome
                tema = ex.togli_cornice(ex.argomento(normalizza(parti[0])))
                for c in scelte_parte:
                    for k in ("cerca", "argomento"):
                        if tema and re.search(r"relativ|stess|medesim|che l[oaie] |quest[oa] |tale ", str(c.parametri.get(k) or "")):
                            c.parametri[k] = tema
            aggiungi(scelte_parte, anche_segnali=False, richiesta_propria=True)
        aggiungi(_una_richiesta(pulita, t, fa, fascicolo), anche_segnali=False)
        if "calcolo" in nomi:  # il quadro letto per un calcolo serve per i termini
            for c in scelte:
                if c.nome == "fascicolo_quadro" and "sezione" not in c.parametri:
                    c.parametri["sezione"] = "termini"
        if scelte:
            return scelte[:massimo]
    return _una_richiesta(pulita, t, fa, fascicolo)[:massimo]


def _una_richiesta(domanda: str, t: str, fa: bool, fascicolo: str) -> list[Chiamata]:
    scelte = _fonti_e_calcoli(domanda, t, fa, fascicolo)
    if not scelte:
        scelte = _studio(domanda, t, fa, fascicolo)
    if not scelte:
        scelte = _segnali_della_mappa(domanda, t, fa, fascicolo)
    return scelte


_RICERCA_NELLO_STUDIO = (r"in tutto lo studio|in tutto l'archivio|ovunque nello studio|ricerca (?:globale|libera|generale)|cerca ovunque|"
                         r"avevamo (?:una|un) (?:pratica|causa|fascicolo|cliente)|c'era (?:una|un) (?:pratica|causa|fascicolo)|"
                         r"mi ricordo (?:una|un) (?:pratica|causa)|nei nostri documenti|tra (?:le|i) (?:nostre|nostri) (?:pratiche|fascicoli)|"
                         r"in quali (?:pratiche|fascicoli|cause)|abbiamo (?:gia |mai )?(?:trattato|seguito|avuto|gestito)\b")


def _fonti_e_calcoli(domanda: str, t: str, fa: bool, fascicolo: str) -> list[Chiamata]:
    if _ha(t, _RICERCA_NELLO_STUDIO):  # ricerca libera nello studio: la decide _studio, anche se nomina un istituto
        return []
    # 0. dove si trova qualcosa nel software; ricerca sui siti ufficiali (prima dei nomi di fonti che contengono)
    if (_ha(t, r"\b(?:programma|software|menu|applicazione|gestionale|iusentra|piattaforma|schermata|app)\b|in quale pagina|quale pagina") and _ha(
            t, r"\bdove\b|\bdov'e|in che|in quale|trovo|si trova|come (?:arrivo|accedo|apro)|quale pagina")) or _ha(
            t, r"dove (?:vedo|trovo|si trova|e|sta|apro) (?:la |il |l'|lo )?(?:pagina|sezione|menu|voce|schermata|funzione|scheda)|"
               r"come (?:arrivo|accedo|apro|entro) (?:alla|al|la|il|nella|nel) (?:pagina|sezione|menu|schermata|funzione)"):
        return [_c("pagine_software", "pagine", cerca=_dopo(t, r"(?:pagina per|si trova(?: nel (?:software|programma))?|trovo)") or ex.argomento(t))]
    if _ha(t, r"sul sito|sito ufficiale|sul web|in rete|\bonline\b|(?:cerca|trova|guarda|leggi|consulta)\w* (?:sul|nel) portale"):
        return [_c("web_ufficiale", "web", cerca=_ricerca_web(domanda), solo_ufficiali=True if _ha(t, r"sito|portale") else None)]
    # 1. calcolo
    # Un articolo citato da leggere o una procedura da spiegare non sono calcoli, salvo richiesta espressa di calcolo.
    calcolo_espresso = _ha(t, r"\bcalcol\w*|entro quando|quando scade|a quanto ammont|\bquant[oaie]\b|fino a quando|giorno utile|termine ultimo|ultimo giorno")
    da_leggere = ex.articolo_citato(domanda) is not None and _ha(
        t, r"\btesto\b|cosa (?:dice|prevede|stabilisce)|leggimi|formulazion|formulat\w*|riporta|recita|com'?\s?era|versione|vigente al|in vigore al")
    da_spiegare = _ha(t, r"come si (?:procede|fa)\b|passi,? termini e allegati|\biter\b|guida pratica|che cosa serve per|cosa serve per")
    # Chi chiede norme, giurisprudenza, prassi, novità o modelli su un istituto non chiede di calcolarlo.
    cerca_fonti = _ha(t, r"\bnovit|aggiornament|e cambiat\w*|cosa (?:e|e') cambiat|cambiato qualcosa|\briform\w*|ultime modifiche|modifiche recenti|di recente|nuove regole|nuova disciplina|\bnorma\b|\bnorme\b|che articolo|quale articolo|disciplin\w*|regolat\w*|cassazione|giurisprudenz|orientament|"
                         r"\bsentenze\b|\bpronunce\b|circolar\w*|\bprassi\b|interpell\w*|\bnovita\b|aggiornament\w*|modell\w*|fac[- ]?simile|"
                         r"\bformulari\w*|\bbozza\b|\btemplate\b|schema (?:di|per)|traccia (?:di|per)")
    calc = calcolo_per_evento(domanda) or (calcolatore(domanda) if calcolo_espresso or not (da_leggere or da_spiegare or cerca_fonti) else "")
    if calc:
        uscita = [_c("calcolo", "calcolatore", strumento=calc, campi=_campi_calcolo(calc, domanda))]
        # Quanto può durare la custodia di una persona già detenuta: la durata massima, poi la misura in corso.
        # Solo per una persona concreta (il cliente, una data di inizio), non per la domanda generale su «un indagato».
        if calc == "custodia_durata" and _ha(t, r"in carcere|arrestat\w*|detenut\w*|fermat\w*|ai domiciliari|agli arresti|in custodia") and _ha(
                t, r"\b(?:il mio|la mia|mio|mia|il nostro|il cliente|la cliente|assistit\w*)\b|\be (?:in carcere|detenut\w*|ai domiciliari)|"
                   r"\be stat[oa] (?:arrestat|fermat)|\b\d{1,2}/\d{1,2}/\d{4}\b|\bda (?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
                   r"settembre|ottobre|novembre|dicembre)\b"):
            uscita.append(_c("calcolo", "misura cautelare in corso", strumento="custodia_cautelare",
                             campi=_campi_calcolo("custodia_cautelare", domanda)))
        # Il primo passo che la domanda chiede prima del calcolo: leggere il conto o il fascicolo.
        if _ha(t, r"conto economico|(?:dal|nel|sul|in base al) conto\b|dall'economia|dalle parcelle|"
                  r"(?:controlla|guarda|apri|leggi|vedi)\w* (?:il |l')?(?:conto|economia)"):
            uscita.insert(0, _c("economia_conto", "dati economici per il calcolo", fascicolo=fascicolo or None, voce="conto"))
        elif fa and fascicolo and (calcolo_per_evento(domanda) and fascicolo != "corrente" and _ha(
                t, r"\b(?:del|della|nel|nella|dal|dalla) (?:fascicolo|pratica|causa)\b") or _ha(t, r"(?:guarda|prendi|leggi|cerca|recupera|apri|controlla|vedi)\w* .{0,40}(?:fascicolo|pratica|causa)|"
                                         r"(?:dal|nel|sul) fascicolo|(?:sulla base|in base|alla luce) (?:del|dei dati del) fascicolo|"
                                         r"dagli atti (?:della|del) (?:pratica|causa|fascicolo)|leggendo il fascicolo")):
            if _ha(t, r"\bleggi\w*|\blettura\b"):
                uscita.insert(0, _c("fascicolo_lettura", "dati dal fascicolo", fascicolo=fascicolo or "corrente"))
            else:
                uscita.insert(0, _c("fascicolo_quadro", "dati dal fascicolo", fascicolo=fascicolo or "corrente", sezione="termini"))
        return uscita
    # I prossimi passi di una pratica nominata o aperta sono nel suo quadro, non nella procedura guidata.
    if (fa or fascicolo) and _ha(t, _PROSSIMI_PASSI):
        return [_c("fascicolo_quadro", "prossimi passi della pratica", fascicolo=fascicolo or "corrente", sezione="prossimi_passi")]
    # 2. redazione e procedure
    modello = _ha(t, r"\bmodell[oi]\b|\btemplate\b|fac[- ]?simile|\bformulari\w*|\bmodul\w* (?:di|per)|schema (?:pronto|dell'atto|di atto|di ricorso|di contratto|di)|"
                     r"\bbozza\b|dal catalogo|schema per|schema dell|traccia (?:di|per)")
    norme = _ha(t, r"su quali norme|quali (?:fonti|norme|basi) normativ|basi normativ|si (?:fonda|basa)|requisiti (?:del|della|dello|dell')|"
                   r"fonti normative|norme del modello|relative basi|riferimenti normativi|fondamento normativo|base giuridica|"
                   r"(?:quali|che) articoli|su quali articoli|normativa di riferimento|norme di riferimento|"
                   r"articoli (?:citati|richiamati)|fonti del modello|\ballegat\w*|documenti da allegare|cosa (?:deve|devo) (?:contenere|allegare)|"
                   r"contenuto obbligatorio|elementi (?:essenziali|obbligatori)|\brequisiti\b|su cosa si (?:basa|fonda)|quali leggi|riferimenti di legge|"
                   r"\bconform\w*|controllo normativo|verifica normativa|norme (?:che )?(?:cita|richiama|applica)|"
                   r"quali norme|che norme|norme (?:richiamate|applicate|citate)|norme che (?:il|lo|la|l') ?(?:modell\w*|schema|atto) (?:cita|richiama|applica|prevede)")
    procedura = _ha(t, r"come si (?:procede|fa)\b|passo per passo|\biter\b|guida pratica|che cosa serve per|cosa serve per|"
                       r"passi,? termini e allegati|spiegami come|\bpassi\b|scheda (?:pratica|della procedura|operativa)|vademecum|"
                       r"cosa (?:devo|dobbiamo|bisogna) fare per|come (?:devo|dobbiamo) procedere|procedura (?:per|da seguire)|\bstep\b|"
                       r"\bpassaggi\b|(?<!prossimi )\badempimenti\b(?! (?:di|in|nella|nel) quest)|come funziona (?:il|la|l')|come si (?:avvia|instaura|introduce|propone)")
    if modello or (norme and _ha(t, r"modell|schema|catalogo")):
        atto = _atto_redazione(t)
        if procedura:
            frase = next((f for f in re.split(r"[.;]\s+", t) if re.search(
                r"come si (?:procede|fa)|passo per passo|\biter\b|guida pratica|cosa serve per|passi", f)), t)
            return [_c("procedura_guidata", "procedura", procedura=_procedura(frase)),
                    _c("modelli_atto", "modello", cerca=_procedura(frase))]
        if norme:
            # Solo le norme, salvo che la domanda chieda espressamente anche il modello («trovami il modello … e le norme»).
            chiede_il_modello = _ha(t, r"\b(?:trova\w*|voglio|cerco|hai|prepar\w*|dammi|mandami|scarica\w*)\b.{0,25}(?:modell|schema|bozza|fac)") and _ha(
                t, r"\be (?:dimmi|poi|anche|le|i|su quali)\b|\bcon le (?:norme|fonti)|\binsieme\b")
            richieste = [_c("norme_modello", "norme del modello", atto=atto)]
            return ([_c("modelli_atto", "modello", cerca=atto)] + richieste) if chiede_il_modello else richieste
        codice = re.search(r"\bcodice (?:del )?(?:modello )?([a-z]{1,6}[-_.]?\d{1,5}[a-z]?)\b", t)
        return [_c("modelli_atto", "modello", cerca=atto or ex.argomento(t), materia=ex.materia(t, anche_senza_preposizione=True) or None,
                   codice_modello=codice.group(1).upper() if codice else None)]
    if procedura and not _ha(t, r"\bart(?:icolo|\.)\s*\d"):
        return [_c("procedura_guidata", "procedura", procedura=_procedura(t))]
    # 3. fonti pubbliche: prima le novità («riforma», «cosa è cambiato»), che non sono né calcoli né procedure
    if not _ha(t, r"cassazione|giurisprudenz|sentenz|pronunc|consiglio di stato|\btar\b|circolar|prassi|interpell|agenzia (?:delle )?entrate|"
                  r"\binps\b|sul sito|sito ufficiale|gazzetta") and _ha(t, r"\bnovit|aggiornament|e cambiat\w*|cosa (?:e|e') cambiat|cambiato qualcosa|\briform\w*|ultime modifiche|modifiche recenti|di recente|nuove regole|nuova disciplina") and not ex.estremi_pronuncia(domanda):
        return [_c("aggiornamenti_normativi", "aggiornamenti", cerca=ex.togli_cornice(ex.argomento(t)))]
    if _ha(t, r"gazzetta|\bg\.\s?u\.|\bgu\b|serie generale|serie speciale|\b(?:[1-5]a|prima|seconda|terza|quarta|quinta) serie\b"):
        date = ex.date_it(domanda)
        if not date:
            date = [d for d in ex.periodo_del_mese(domanda) if d]
        return [_c("gazzetta_ufficiale", "gazzetta", dal=date[0] if date else None, al=date[1] if len(date) > 1 else None,
                   serie=ex.serie_gazzetta(t) or None, tipo_atto=ex.tipo_atto_gazzetta(t) or None)]
    pec_o_posta = _ha(t, r"\bpec\b|\bemail\b|e-mail|\bposta\b")
    if not pec_o_posta and _ha(t, r"circolar|risoluzion\w* (?:dell'?)?(?:agenzia|ade)|\bprassi\b|interpell|documenti di prassi") or (
            ex.ente_prassi(t) and _ha(t, r"circolar|risoluz|messagg|chiarit|istruzion|prassi|cosa (?:dice|ha detto)|indicazion|posizione|"
                                         r"documenti|ha precisato|orientamento|provvediment\w*|\bnovit\w*|\bnuov[eia]\b|\bultim[eio]\b|aggiornament\w*|pubblicat\w*|di recente") and not pec_o_posta
            and not _ha(t, r"\bsul sito|portale")):
        m = (re.search(r"\bn\.?\s*(\d{1,5})(?:/[a-z])?\s*(?:del|/)\s*(?:\d{1,2}(?:[./-]\d{1,2}[./-]|\s+[a-z]+\s+))?((?:19|20)\d{2})", t)
             or re.search(r"\b(?:circolare|risoluzione|messaggio|interpello|provvedimento)\s+(?:n\.?\s*)?(\d{1,5})(?:/[a-z])?\s*"
                          r"(?:del|/)\s*(?:\d{1,2}(?:[./-]\d{1,2}[./-]|\s+[a-z]+\s+))?((?:19|20)\d{2})", t)
             or re.search(r"\b(\d{1,4})/((?:19|20)\d{2})\b", t))
        ente = ex.ente_prassi(t) or None
        if m:
            return [_c("prassi_ade_inps", "prassi per estremi", ente=ente, numero=int(m.group(1)), anno=int(m.group(2)))]
        return [_c("prassi_ade_inps", "prassi", ente=ente, cerca=ex.argomento(t), anno=ex.anno_citato(t))]
    estremi = ex.estremi_pronuncia(domanda)
    if estremi and estremi["organo"] in ("consiglio_di_stato", "tar", "cgars"):
        return [_c("giustizia_amministrativa", "pronuncia amministrativa per estremi", organo=estremi["organo"],
                   sede=ex.sede_tar(domanda) or None, numero=estremi["numero"], anno=estremi["anno"])]
    if estremi and estremi["organo"] in ("cassazione", "consulta"):
        return [_c("giurisprudenza_cassazione_consulta", "pronuncia per estremi", corte=estremi["organo"],
                   numero=estremi["numero"], anno=estremi["anno"],
                   sezione=ex.sezione_cassazione(t) or None if estremi["organo"] == "cassazione" else None)]
    citato = ex.articolo_citato(domanda)
    if citato is not None:
        numero_art, atto = citato
        sentenze = _ha(t, r"sentenz|giurisprudenz|pronunc|precedent|orientament|giudici|interpret|massim\w*|cassazione|"
                          r"\bconsulta\b|corte costituzionale|tribunali|applicat\w* dai")
        # «cosa dice la Cassazione sull'art. X» chiede le pronunce, non il testo: il testo solo se chiesto espressamente.
        testo = _ha(t, r"\btesto\b|formulazion|leggimi|citami|riporta|recita") or (
            _ha(t, r"\bnorma\b|cosa (?:dice|prevede)") and not sentenze)
        norma = _c("norma_testo_vigente", "articolo citato", atto=atto, articolo=numero_art,
                   comma=ex.comma(domanda) or None,
                   alla_data=(ex.date_it(domanda) or [None])[0])
        if sentenze:
            sent = _c("sentenze_per_norma", "pronunce sull'articolo", norma=f"art. {numero_art} {atto}")
            return [norma, sent] if testo else [sent]
        return [norma]
    if _ha(t, r"\btar\b|t\.a\.r\.|consiglio di stato|giustizia amministrativa|giurisprudenza amministrativa|giudic\w* amministrativ|\bcgars\b") and not _ha(
            t, r"deposit\w*|\bpat\b|\bsiga\b|firma|\bpdf\b|come si (?:procede|fa)|modell|fac[- ]?simile"):
        org = "consiglio_di_stato" if _ha(t, r"consiglio di stato|cons\. ?st") else "tar"
        return [_c("giustizia_amministrativa", "giustizia amministrativa", organo=org, cerca=ex.argomento(t),
                   sede=ex.sede_tar(domanda) or None if org == "tar" else None, anno=ex.anno_citato(t))]
    if _ha(t, r"cassazione|suprema corte|sezioni unite|\bs\.\s?u\.|corte costituzionale|\bconsulta\b|giurisprudenz|orientament|precedent|pronunce"):
        corte = ("consulta" if _ha(t, r"costituzional|consulta") else "cassazione"
                 if _ha(t, r"cassazione|suprema corte|sezioni unite|\bs\.\s?u\.") else None)
        return [_c("giurisprudenza_cassazione_consulta", "giurisprudenza", corte=corte, cerca=ex.argomento(t),
                   sezione=ex.sezione_cassazione(t) or None if corte == "cassazione" else None, anno=ex.anno_citato(t))]
    if _ha(t, r"(?:quale|che|qual e la) (?:norma|disposizione|articolo|legge)|la norma che (?:regola|disciplina|prevede|punisce|stabilisce)|"
              r"\bnorm[ae] (?:sul|sulla|sui|sugli|sull'|sulle|in materia di|che regolano|che disciplinano)\b|\bnorm[ae] che l[oaie] (?:regol|disciplin|prevede)\w*|"
              r"l'articolo (?:che|sul|sulla|sui|delle|del)|la disposizione (?:che|sul|sulla)|la regola (?:che|sul|sulla|del codice|del c\.c\.)|cosa dice la legge (?:su|sul|sulla)|"
              r"articolo del codice (?:civile|penale|di procedura \w+) (?:che|sul|sulla)|in quale articolo|dove (?:e|sta|si trova) (?:regolat|disciplinat|previst)|"
              r"la norma su|indicarmi la norma|disciplina di|in quale disposizione|devo guardare per|"
              r"\b(?:norma|disposizione|regola|legge|articolo) (?:secondo (?:cui|la quale|il quale)|per cui|in base (?:alla|al) quale)|"
              r"(?:c'e|esiste|ci sono) (?:una |un |delle |degli )?(?:norma|norme|disposizion\w*|articol\w*|regola|legge)\b.{0,15}\bche\b|"
              r"\b(?:norma|disposizione|articolo|regola) che (?:\w+ ){0,2}(?:vieta|prevede|stabilisce|obbliga|consente|punisce|regola|disciplina|impone|sancisce|"
              r"dice|tutela|attribuisce|esclude|limita)\b|in quale (?:legge|codice|testo)|(?:che|cosa) (?:cosa )?(?:dice|prevede|stabilisce) la legge"):
        atto = ex.atto_citato(t[t.rfind("("):]) if "(" in t else ""
        return [_c("norma_per_argomento", "norma per argomento", argomento=ex.togli_cornice(ex.argomento(t)), atto=atto or None)]
    if not _ha(t, r"cassazione|giurisprudenz|sentenz|pronunc|consiglio di stato|\btar\b|circolar|prassi|interpell|agenzia (?:delle )?entrate|"
                  r"\binps\b|sul sito|sito ufficiale|gazzetta") and _ha(t, r"\bnovit|aggiornament|e cambiato|cambiato qualcosa|riforma recente|di recente"):
        return [_c("aggiornamenti_normativi", "aggiornamenti", cerca=ex.argomento(t))]
    if _ha(t, r"sul sito|sito ufficiale|sul web|in rete|\bonline\b"):
        return [_c("web_ufficiale", "web", cerca=_ricerca_web(domanda), solo_ufficiali=True if _ha(t, r"sito") else None)]
    return []


_PERIODO = (r"\b(?:di|a|in|del mese di|entro) (?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b|"
            r"\bdel mese di\b")  # un mese o una data detti: il filtro di date dell'agenda (non «la prossima settimana»)
def _periodo(domanda: str) -> dict[str, str | None]:
    """Il filtro di date detto nella domanda: «dal …», «tra il … e il …», «dopo il …»."""
    date = ex.date_it(domanda)
    return {"dal": date[0] if date else None, "al": date[1] if len(date) > 1 else None}


_PROSSIMI_PASSI = (r"prossim\w* (?:pass\w*|adempiment\w*|mosse|step|attivita|cose da fare)|cosa (?:dobbiamo|devo|bisogna|c'e da) fare (?:adesso|ora|dopo|nella|nel|per)|"
                   r"come (?:procediamo|andiamo avanti|proseguiamo)|che (?:si fa|facciamo) (?:ora|adesso)|cosa (?:facciamo|si fa) (?:ora|adesso)|quali sono i prossimi")
# Il cliente chiede della sua causa o della sua pena: il quadro della sua pratica, non la sua anagrafica.
_CLIENTE_CHIEDE_DELLA_CAUSA = (r"(?:pena|condanna).{0,40}(?:resta|rimane|scontare|residu|finisce)|(?:resta|rimane) da scontare|fine pena|finisce di scontare|"
                               r"a che punto (?:e|sta)|com'?\s?e messa|come (?:va|sta andando|procede) (?:la|il) (?:sua |nostra )?(?:causa|pratica|procedimento|processo)|"
                               r"(?:sua|nostra) (?:causa|pratica|vertenza|procedimento|processo)|stata decisa|stato della (?:causa|pratica)|"
                               r"novita (?:sulla|della) (?:causa|pratica)|quando (?:finisce|si chiude) (?:la|il) (?:causa|processo|pratica)|"
                               r"finire (?:di scontare )?la pena|manca.{0,25}\bpena\b|\bpena\b.{0,25}manca|(?:ha|abbiamo|hanno) (?:vinto|perso) (?:la )?causa|"
                               r"esito della (?:sua )?(?:causa|sentenza)|com'?\s?e (?:finita|andata) (?:la )?(?:causa|udienza)|notizie (?:della|sulla) (?:sua )?(?:causa|pratica)")
_CASELLA_ORDINARIA = r"posta ordinaria|\bpec ordinari\w*|\bordinari[ae]\b|non certificat\w*|posta (?:elettronica )?semplice|mail normal\w*"
_ESITO_DEPOSITO = (r"(?:cancelleri\w*|deposit\w*).{0,60}(?:\bha accettat\w*|e stat\w* accettat\w*|\baccettat\w*|andat\w* a buon fine|"
                   r"\be passat\w*|\besito\b|\bricevut[ae] di)|"
                   r"(?:\baccettat\w*|accettazione|andat\w* a buon fine|\besito\b).{0,60}(?:cancelleri\w*|deposit\w*)|"
                   r"(?:seconda|terza|quarta) pec|pec di (?:accettazione|consegna|esito) del deposito|ricevut\w* del deposito")
_ERRORE_DEPOSITO = (r"non (?:e |sono )?(?:andat\w*|stat\w* accettat\w*) |non va a buon fine|rifiutat|scartat|\berrore|respint|anomali|fallit|"
                    r"bloccat|esito negativo|warning|come (?:faccio|si fa|devo)|prima di depositare|posso depositare|preparare")


def _studio(domanda: str, t: str, fa: bool, fascicolo: str) -> list[Chiamata]:
    if _ha(t, r"(?:programma|software|menu)\b") and _ha(t, r"dove|in che|in quale|trovo|si trova"):
        return [_c("pagine_software", "pagine", cerca=_dopo(t, r"(?:pagina per|si trova|trovo)") or ex.argomento(t))]
    # Esito di un deposito già fatto (accettazione, buon fine, terza o quarta PEC): lo dicono le ricevute del deposito.
    # Un errore o uno scarto da capire resta al controllo del deposito telematico.
    if _ha(t, _ESITO_DEPOSITO) and not _ha(t, _ERRORE_DEPOSITO):
        return [_c("notifiche_ricevute", "esito del deposito", fascicolo=fascicolo or None, tipo="ricevute_deposito", **_periodo(domanda))]
    if _ha(t, r"deposit\w* telematic|\bpst\b|\bpct\b|\bpdp\b|\bpat\b|\bptt\b|datiatto|invio telematico|busta|\bsiga\b|\bsigit\b|"
              r"processo (?:civile|amministrativo|tributario) telematico|portale (?:del )?deposito|"
              r"\bdeposit\w*\b.{0,40}(?:scartat|rifiutat|\berrore|respint|anomali|fallit|bloccat|non (?:e )?andat\w* a buon fine)|"
              r"(?:verific|controll|prepar)\w* (?:il |lo stato del )?deposito (?:della|del|dell')") and not _ha(
            t, r"\bletti\b|\blettura\b"):
        controllo = next((v for v, s in (
            ("datiatto", r"datiatto|\bxml\b|codice oggetto|dati (?:dell'atto|della busta)"),
            ("firma", r"\bfirm\w*|\bp7m\b|cades|pades"),
            ("pdf", r"\bpdf\b|pdf/a|nativo digitale|scansion\w*|dimension\w*|pesa troppo|troppo grande|\bmb\b"),
            ("errore", r"errore|rifiutat\w*|anomali\w*|scartat\w*|warning|esito negativo|non (?:e )?andat\w* a buon fine|"
                       r"non va a buon fine|non (?:riesce|parte|passa)|fallit\w*|bloccat\w*"),
            ("stato", r"\bstato del deposito|a che punto|e stato (?:accettat|depositat)|risulta depositat|esito del deposito"),
            ("checklist", r"controll\w*|verific\w*|prima d|cosa (?:devo|serve)|checklist|e pronto|posso depositare"))
            if _ha(t, s)), None)
        canale = next((c for c, s in (("pct", r"\bpct\b|\bpst\b|processo civile telematico|portale dei servizi telematici"),
                                      ("pdp", r"\bpdp\b|portale (?:del )?deposito (?:atti )?penal\w*|deposito penale"),
                                      ("pat", r"\bpat\b|\bsiga\b|processo amministrativo telematico"),
                                      ("ptt", r"\bptt\b|\bsigit\b|processo tributario telematico|giustizia tributaria"))
                       if _ha(t, s)), None)
        atto = _dopo(t, r"(?:depositare|invio telematico di|deposito telematico (?:della|del|dell')|firma (?:della|del|dell')|"
                        r"pdf (?:della|del|dell')|deposito \w+ (?:della|del|dell'))", fino=r"(?:\s+(?:sul|sulla|per il|per la|e|ha|va|è)\b|[?.!,]|$)")
        return [_c("deposito_telematico", "deposito", fascicolo=fascicolo if fa else None, canale=canale, controllo=controllo,
                   atto=atto or None)]
    if _ha(t, r"campanell|avvisi"):
        return [_c("avvisi_utente", "avvisi")]
    if _ha(t, r"cosa (?:ho|abbiamo) (?:da fare )?oggi|piano (?:del giorno|di oggi|della giornata)|programma (?:di oggi|della giornata)|"
              r"impegni di oggi|da fare oggi"):
        return [_c("scadenziario", "piano del giorno", stato="aperte"), _c("agenda_udienze", "piano del giorno")]
    if _ha(t, r"avevamo (?:una|un) (?:pratica|causa|fascicolo|cliente)|c'era (?:una|un) (?:pratica|causa|fascicolo)|mi ricordo (?:una|un) (?:pratica|causa)|"
              r"abbiamo avuto (?:una|un) (?:pratica|causa)|una pratica (?:con|su|di) (?:un|una) cert|in quale pratica (?:c'era|avevamo)|"
              r"in tutto lo studio|in tutto l'archivio|ovunque nello studio|ricerca (?:globale|libera|generale)|cerca ovunque|"
              r"(?:nei|tra i|fra i) (?:nostri )?(?:documenti|fascicoli|atti) (?:dello studio|archiviati)|"
              r"(?:cerca|trova\w*|c'e qualcosa)\b.{0,40}\b(?:nei nostri|nell'archivio|in archivio|in studio|nello studio)|"
              r"in quali (?:pratiche|fascicoli|cause)|dove abbiamo (?:gia )?(?:seguito|trattato)|abbiamo (?:gia |mai )?(?:trattato|seguito|avuto|gestito)|"
              r"in studio|nello studio|nell'archivio dello studio|altre (?:pratiche|cause)|nostri precedenti|precedenti (?:dello|nello) studio|"
              r"(?:cerca|trova\w*) (?:in|tra|fra) (?:tutt[ie] )?(?:le )?(?:pratiche|fascicoli|documenti dello studio)"):
        return [_c("ricerca_studio", "ricerca", cerca=ex.argomento(t))]
    nome = _nome_proprio(domanda) or _persona(domanda)
    if (nome or fascicolo) and _ha(t, _CLIENTE_CHIEDE_DELLA_CAUSA):
        return [_c("fascicolo_quadro", "la causa del cliente", fascicolo=fascicolo or nome)]
    anagrafica = _ha(t, r"telefono|recapit|codice fiscale|indirizzo|anagrafic|residen|partita iva|\bnato\b|fascicoli ha")
    if nome and anagrafica and _ha(t, r"cliente|assistit|soggett|controparte|sig\.|signor") and not _ha(t, r"scadenz|termin"):
        dato = next((v for v, s in (("fascicoli", r"fascicoli|pratiche"), ("recapiti", r"\bpec\b|telefono|recapit|email"),
                                    ("anagrafica", r"codice fiscale|indirizzo|anagrafic")) if _ha(t, s)), None)
        return [_c("clienti_soggetti", "cliente", cerca=nome, dato=dato)]
    # Una persona nominata con pagamenti, preventivi, parcelle, mail o scadenze chiede quei dati, non la sua anagrafica.
    if nome and _ha(t, r"pagat|pagament|saldat|saldo|insolut|bonific|parcell|fattur|preventiv|conferiment|incass|ore registrat"):
        voce = _voce_economica(t)
        return [_c("economia_conto", "economia", cliente=nome, voce=voce if voce != "conto" else None,
                   fascicolo=fascicolo if fa and fascicolo else None)]
    if nome and _ha(t, r"\bpec\b|\bmail\b|\be-?mail\b|messagg\w*|\bposta\b|scritto|ha scritto|ha mandato|ha inviato"):
        date = ex.date_it(domanda)
        return [_c("pec_comunicazioni", "pec", mittente=nome, dal=date[0] if date else None, fascicolo=fascicolo if fa and fascicolo else None,
                   casella="ordinaria" if _ha(t, _CASELLA_ORDINARIA) else "pec" if _ha(t, r"\bpec\b") else "ordinaria" if _ha(t, r"\bmail\b|e-?mail") else None)]
    if nome and _ha(t, r"scadenz|termin\w* (?:\w+ )?(?:aperti|pendenti|in scadenza|da rispettare)|scadono"):
        return [_c("scadenziario", "scadenze", cliente=nome, stato=ex.stato_scadenze(t) or None)]
    if nome and _ha(t, r"anagrafic|codice fiscale|recapit|telefono|indirizzo|fascicoli ha|residen|partita iva|\bdati del|chi e il cliente") and not _ha(
            t, r"scadenz|termin|calcol"):
        dato = next((v for v, s in (("fascicoli", r"fascicoli|pratiche"), ("recapiti", r"\bpec\b|telefono|recapit|email"),
                                    ("anagrafica", r"codice fiscale|indirizzo|anagrafic")) if _ha(t, s)), None)
        return [_c("clienti_soggetti", "cliente", cerca=nome, dato=dato)]
    uscita: list[Chiamata] = []
    if fa or fascicolo:
        if _ha(t, r"incoerenz|incongruen\w*|non torna|non tornano|non combacia|coerenz\w*|\bcatena\b|torna con|tornano con|allineat\w*|combaci\w*|"
                  r"corrispond\w*|quadrano|coincid\w*|disallinea\w*|discrepanz\w*|contraddi\w*|differenz\w* (?:tra|fra)|"
                  r"(?:sono|siano) (?:giust[ei]|corrett[ei]|congruent[ei])\b.{0,40}(?:rispetto|con)|conflitt\w* (?:tra|fra)|"
                  r"(?:sono|siano|risultano) (?:tutti |tutte )?(?:nello|in) scadenziario|(?:mancano|manca|assenti|non registrat\w*) (?:nello|dallo|in) scadenziario|"
                  r"(?:registrat\w*|riportat\w*) (?:tutti |tutte )?(?:nello|in) scadenziario"):
            return [_c("fascicolo_catena", "catena", fascicolo=fascicolo or "corrente")]
        if _ha(t, r"\b(?:termin|scadenz)\w* (?:\w+ )?(?:aperti|aperte|pendenti|ancora da rispettare|da rispettare)\b") and not _ha(t, r"\bcliente\b"):
            return [_c("scadenziario", "termini aperti della pratica", fascicolo=fascicolo or "corrente", stato="aperte"),
                    _c("fascicolo_catena", "termini letti negli atti ma non registrati", fascicolo=fascicolo or "corrente")]
        if _ha(t, r"conto economico|(?:apri|guarda|leggi|controlla|vedi)\w* (?:il |l')?(?:conto|economia)"):
            return [_c("economia_conto", "economia", fascicolo=fascicolo or "corrente", voce="conto")]
        if _ha(t, r"in (?:che|quale) fase|a che fase|a che stadio|fase (?:della|del|in cui (?:e|si trova)) (?:causa|pratica|giudizio|procedimento|fascicolo)"):
            return [_c("fascicolo_lettura", "lettura", fascicolo=fascicolo or "corrente", parte="fase")]
        if _ha(t, r"cronologi|vicenda|\bstoria\b|\blettura\b|\bletti\b|\blett[ae]\b|in fila|ordine di data|raccontami|"
                  r"(?:quali|che) atti (?:sono stati|risultano|abbiamo) (?:gia )?depositat|atti (?:processuali )?depositati|"
                  r"\bleggi\w* (?:il|tutto il|l'intero) (?:fascicolo|incartamento)"):
            return [_c("fascicolo_lettura", "lettura", fascicolo=fascicolo or "corrente", parte=_parte_lettura(t))]
        if _ha(t, r"\bdocument|(?:trovami|cerca|cercami) nel fascicolo|apri il (?:documento|file|pdf|verbale)|\brelata\b|\bperizia\b|\bverbale\b|"
                  r"(?:trova|cerca|recupera|mostra)\w*\b.{0,50}\b(?:nel|tra i documenti del|dentro il|nella) (?:fascicolo|pratica|causa)|"
                  r"mi serve (?:la|il|l'|lo) ?(?:sentenza|atto|ricorso|decreto|contratto|procura|relata|perizia|verbale|comparsa)|"
                  r"(?:nel|del|nella) (?:fascicolo|pratica|causa)\b.{0,40}\b(?:il|la|lo|l'|un|una) ?(?:contratto|atto|sentenza|ricevuta|"
                  r"perizia|relata|procura|fattura|lettera|diffida|comparsa|memoria|ricorso|decreto)\b|"
                  r"c'e (?:la|il|lo|un|una|l') ?(?:sentenza|atto|ricorso|decreto|procura|relata|perizia|verbale|comparsa|citazione|contratto|memoria)|"
                  # verbo del cercare o del mostrare + un documento nominato, nella pratica indicata o aperta
                  r"(?:dove (?:si trova|sta|e|sono|trovo)|dov'e|fammi vedere|fammi leggere|mostra\w*|apri\w*|recuper\w*|trova\w*|cerca\w*|"
                  r"dammi|passami|mi serve|mi servono|c'e|ci sono|abbiamo|hai|manca|mancano|leggi\w*)\b.{0,25}\b"
                  r"(?:la |il |lo |l'|i |le |gli |un |una |l')?(?:procura|comparsa|citazione|atto di|atti di|ricorso|sentenza|ordinanza|decreto|"
                  r"verbal\w*|\bctu\b|consulenza tecnica|perizi\w*|contratt\w*|memori\w*|relat[ae]|letter\w*|diffid\w*|"
                  r"precetto|pignoramento|delibera|testamento|visura|planimetri\w*|certificat\w*|estratto conto|bust[ae] pag\w*|"
                  r"allegat\w*|document\w*|\bfile\b|\bpdf\b|copia|quietanz\w*|scrittura privata|denuncia|querela|istanza|"
                  r"mandato)"):
            tipo = (re.search(r"(?:^|\s)['\"«](.+?)['\"»](?=[\s?.,!]|$)", domanda) or [None, None])[1] or _dopo(
                t, r"(?:trovami nel fascicolo|che contiene|cerca nel fascicolo|cercami nel fascicolo)", fino=r"(?:\s+(?:in questa|nel fascicolo)\b|[?.!]|$)")
            return [_c("documenti_fascicolo", "documenti", fascicolo=fascicolo or "corrente", tipo_documento=normalizza(tipo) if tipo else None)]
        voce = _voce_economica(t)
        if voce and voce != "conto" or _ha(t, r"conto economico"):
            return [_c("economia_conto", "economia", fascicolo=fascicolo or "corrente", voce=voce)]
        if _ha(t, r"notific|ricevut|consegn|accettazion|accettat\w* dalla cancelleria|rifiutat\w* dalla cancelleria|esito della cancelleria|"
                  r"esito .{0,15}deposito|(?:accettat|rifiutat)\w* .{0,30}deposito"):
            tipo = ("ricevute_archiviate" if _ha(t, r"archiviat|salvat") else "ricevute_deposito"
                    if _ha(t, r"deposit|accettazion|accettat|cancelleria") else "notificazioni")
            if not _ha(t, r"\bpec\b.{0,30}(?:arrivat|ricevut)|mostrami le pec"):
                return [_c("notifiche_ricevute", "notifiche", fascicolo=fascicolo or "corrente", tipo=tipo, **_periodo(domanda))]
        if _ha(t, r"\bpec\b|comunicazion\w* di cancelleria|email") and _ha(t, r"agenda|udienz"):
            return [_c("pec_comunicazioni", "pec", fascicolo=fascicolo or "corrente", mittente="cancelleria" if _ha(t, r"cancelleria") else None,
                       casella="pec"),
                    _c("agenda_udienze", "agenda", fascicolo=fascicolo or "corrente", tipo="udienze")]
        if _ha(t, r"udienz|appuntament") and not _ha(t, r"\bpec\b|email|posta") and (ex.date_it(domanda) or _ha(t, _PERIODO)):
            date = ex.date_it(domanda)
            return [_c("agenda_udienze", "agenda", fascicolo=fascicolo or "corrente", dal=date[0] if date else None,
                       al=date[1] if len(date) > 1 else None,
                       tipo="udienze" if _ha(t, r"udienz") and not _ha(t, r"appuntament") else "appuntamenti" if not _ha(t, r"udienz") else None)]
        if not _ha(t, r"\bpec\b|email|posta") and _ha(t, r"prossim\w* (?:pass|udienz)|cosa (?:devo|dobbiamo) fare|a che punto|"
                                                           r"\bquadro\b|termini (?:aperti|gravi)|\bparti\b|ruolo del cliente|"
                                                           r"udienz\w* di quest|economi|questa causa|questo fascicolo|questa pratica|"
                                                           r"(?:guarda|leggi|prendi|controlla)\w* .{0,30}(?:data|sentenza|udienza|termin)|"
                                                           r"udienz|termin\w* (?:aperti|in corso)|\bdocumenti\b|"
                                                           r"(?:apri|guarda|controlla|vedi|recupera|prendi)\w* (?:il |la |l')?(?:fascicolo|pratica|causa|quadro)"):
            return [_c("fascicolo_quadro", "quadro", fascicolo=fascicolo or "corrente", sezione=_sezione_quadro(t))]
    if _ha(t, r"\bpec\b|\bemail\b|e-mail|\bmail\b|posta ordinaria|comunicazion\w* di cancelleria"):
        mittente = next((m for m, s in (("cancelleria", r"cancelleria"), ("controparte", r"controparte"), ("UNEP", r"\bunep\b"),
                                        ("Agenzia delle Entrate Riscossione", r"entrate riscossione")) if _ha(t, s)), None)
        date = ex.date_it(domanda)
        uscita.append(_c("pec_comunicazioni", "pec", fascicolo=fascicolo if fa else None, mittente=mittente,
                         dal=date[0] if date else None, casella="ordinaria" if _ha(t, _CASELLA_ORDINARIA) else "pec" if _ha(t, r"\bpec\b") else None))
        return uscita
    if _ha(t, r"notific|ricevut\w* (?:di|del)|avvenuta consegna|accettazione|esito (?:della |del |dei )?(?:cancelleria|deposito|controlli)|"
              r"(?:accettat|rifiutat)\w* dalla cancelleria|(?:terza|quarta) pec"):
        return [_c("notifiche_ricevute", "notifiche", fascicolo=fascicolo or None, **_periodo(domanda),
                   tipo="ricevute_deposito" if _ha(t, r"deposit|accettazione") else "notificazioni")]
    voce = _voce_economica(t)
    if voce:
        return [_c("economia_conto", "economia", fascicolo=fascicolo or None, voce=voce)]
    if _ha(t, r"scadenz|scadut|termini .{0,20}scad|scadono|termin\w* (?:\w+ )?(?:aperti|pendenti|in scadenza|da rispettare)"):
        date = ex.date_it(domanda)
        return [_c("scadenziario", "scadenze", dal=date[0] if date else None, al=date[1] if len(date) > 1 else None,
                   stato=ex.stato_scadenze(t) or None, cliente=_nome_proprio(domanda) or None,
                   fascicolo=fascicolo if fascicolo and fascicolo != "corrente" else None)]
    if _ha(t, r"udienz|appuntament|impegni|agenda"):
        date = ex.date_it(domanda)
        tipo = "udienze" if _ha(t, r"udienz") else "appuntamenti" if _ha(t, r"appuntament") else None
        return [_c("agenda_udienze", "agenda", dal=date[0] if date else None, al=date[0] if len(date) == 1 else (date[1] if date else None),
                   tipo=tipo, fascicolo=fascicolo if fa and not date else None)]
    return uscita


def _segnali_della_mappa(domanda: str, t: str, fa: bool, fascicolo: str) -> list[Chiamata]:
    """Ultima risorsa: i segnali dichiarati nelle schede, senza gli strumenti che vogliono parametri certi."""
    punteggi: dict[str, int] = {}
    for voce in mappa()["strumenti"]:
        punti = sum(1 for s in voce["segnali"] if re.search(s, t))
        if punti:
            punteggi[voce["nome"]] = punti
    for nome in ("calcolo", "norma_testo_vigente", "sentenze_per_norma"):
        punteggi.pop(nome, None)
    if not fa:
        for nome in ("fascicolo_quadro", "fascicolo_catena", "fascicolo_lettura", "documenti_fascicolo"):
            punteggi.pop(nome, None)
    if not punteggi:
        return []
    nome = max(punteggi, key=lambda n: punteggi[n])
    voce = next(s for s in mappa()["strumenti"] if s["nome"] == nome)
    par: dict[str, Any] = {}
    if "fascicolo" in voce["parametri"] and (fa or voce["parametri"]["fascicolo"].get("obbligatorio")):
        par["fascicolo"] = fascicolo or "corrente"
    for p in ("cerca", "argomento", "procedura"):
        if p in voce["parametri"] and voce["parametri"][p].get("obbligatorio"):
            par[p] = ex.argomento(t)
    return [Chiamata(nome, par, "segnali della scheda")]


__all__ = ["Chiamata", "calcolatore", "normalizza", "scegli"]
