"""Renderer dedicati degli atti civili e stragiudiziali più usati dallo studio.

Il renderer generico degli atti civili stampa solo fatti, diritto e conclusioni:
per un ricorso monitorio, un precetto o una procura significava scartare proprio
i campi che fanno l'atto (importo, titolo esecutivo, conferimento del mandato).
Qui ogni atto ha la struttura richiesta dalla norma che lo disciplina. Un dato
mancante resta visibile come «[da indicare: …]»: mai un valore inventato.

Basi normative:
- ricorso per decreto ingiuntivo: artt. 633, 634, 638, 641, 642 c.p.c.;
  art. 13, comma 3, D.P.R. 115/2002 (contributo ridotto alla metà);
- atto di precetto: artt. 480 e 481 c.p.c.;
- procura alle liti: art. 83 c.p.c.; art. 4, comma 3, D.Lgs. 28/2010;
  art. 2, comma 7, D.L. 132/2014; art. 13 Reg. UE 2016/679;
- memorie integrative: art. 171-ter c.p.c. (D.Lgs. 149/2022);
- comparsa di costituzione e risposta: artt. 166 e 167 c.p.c.;
- messa in mora: artt. 1219 e 2943 c.c.
"""

from __future__ import annotations

import re
from typing import Any, Callable

_SOCIETA = re.compile(
    r"\b(s\.?\s?r\.?\s?l|s\.?\s?p\.?\s?a|s\.?\s?a\.?\s?s|s\.?\s?n\.?\s?c|s\.?\s?c\.?\s?a\.?\s?r\.?\s?l|società|societa|"
    r"cooperativa|consorzio|fondazione|associazione|comune di|ministero|agenzia|ente|banca|condominio)\b",
    re.IGNORECASE,
)


def _ca():
    from pct import compilatore_atti as ca

    return ca


def da_indicare(cosa: str) -> str:
    return f"[da indicare: {cosa}]"


def _v(payload: dict[str, Any], *nomi: str) -> str:
    return _ca()._first_non_empty(*(payload.get(nome) for nome in nomi))


def e_ente(nome: str) -> bool:
    return bool(_SOCIETA.search(str(nome or "")))


def identificativo_fiscale(valore: str) -> str:
    testo = str(valore or "").strip()
    if not testo:
        return ""
    compatto = testo.replace(" ", "").upper()
    if re.fullmatch(r"\d{11}", compatto):
        return f"P.IVA {compatto}"
    return f"C.F. {compatto}"


def blocco_parte(nome: str, fiscale: Any = "", indirizzo: Any = "", *, pec: Any = "") -> str:
    """«Beta S.p.A. (P.IVA …), con sede in …» senza doppi punti né parentesi orfane."""
    nome = str(nome or "").strip() or da_indicare("parte")
    parti = [nome]
    fiscale_txt = identificativo_fiscale(_ca()._first_non_empty(fiscale))
    if fiscale_txt:
        parti.append(f"({fiscale_txt})")
    testo = " ".join(parti)
    indirizzo_txt = _ca()._first_non_empty(indirizzo)
    if indirizzo_txt:
        testo += f", {'con sede in' if e_ente(nome) else 'residente in'} {indirizzo_txt}"
    pec_txt = _ca()._first_non_empty(pec)
    if pec_txt:
        testo += f", PEC {pec_txt}"
    return testo.rstrip(".") + "."


def blocco_difensore(payload: dict[str, Any], assistito: str) -> str:
    ca = _ca()
    avvocato = ca._normalize_lawyer_name(payload.get("lawyer") or payload.get("signature"))
    cf = _v(payload, "lawyer_tax_code", "_lawyer_tax_id")
    pec = _v(payload, "lawyer_pec", "_lawyer_pec")
    studio = _v(payload, "_studio_address")
    genere = "rappresentata e difesa" if e_ente(assistito) else "rappresentato e difeso"
    testo = f"{'in persona del legale rappresentante pro tempore, ' if e_ente(assistito) else ''}{genere} dall'{avvocato}"
    if cf:
        testo += f" (C.F. {cf})"
    testo += ", in forza di procura alle liti allegata al presente atto"
    if studio:
        testo += f", con elezione di domicilio presso il suo studio in {studio}"
    testo += "."
    if pec:
        testo += f" Il difensore dichiara di voler ricevere le comunicazioni all'indirizzo PEC {pec} (art. 136 c.p.c.)."
    return testo


def importo(valore: Any, cosa: str) -> str:
    testo = _ca()._format_currency(valore)
    return testo or da_indicare(cosa)


def _numero(valore: Any) -> float | None:
    testo = str(valore or "").strip()
    if not testo:
        return None
    if "," in testo and "." in testo:
        testo = testo.replace(".", "").replace(",", ".")
    elif "," in testo:
        testo = testo.replace(",", ".")
    testo = re.sub(r"[^\d.\-]", "", testo)
    try:
        return float(testo)
    except ValueError:
        return None


def elenco(valore: Any) -> list[str]:
    ca = _ca()
    voci = ca._to_string_list(valore)
    if len(voci) == 1 and "\n" in voci[0]:
        voci = [riga.strip(" -•\t") for riga in voci[0].splitlines() if riga.strip(" -•\t")]
    return voci


def intestazione(payload: dict[str, Any], *nomi: str) -> str:
    ca = _ca()
    ufficio = _v(payload, *nomi, "court_name", "competent_court", "recipient_or_court", "_court_heading")
    return ca._normalize_court_heading(ufficio) if ufficio else da_indicare("ufficio giudiziario").upper()


def chiusura(payload: dict[str, Any]) -> list[str]:
    ca = _ca()
    avvocato = ca._normalize_lawyer_name(payload.get("signature") or payload.get("lawyer"))
    return ["", ca._render_footer_line(payload), "", avvocato]


def riferimento_rg(payload: dict[str, Any]) -> str:
    """Solo il numero di ruolo («R.G. n. 1234/2026»), non l'etichetta della pratica."""
    for nome in ("proceeding_number", "linked_proceeding", "case_reference_display"):
        testo = _v(payload, nome)
        numero = re.search(r"\b(\d{1,7}\s*/\s*\d{4})\b", testo or "")
        if numero:
            return f"R.G. n. {numero.group(1).replace(' ', '')}"
    return ""


# ---------------------------------------------------------------- monitorio

def render_decreto_ingiuntivo(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    creditore = _v(payload, "claimant", "creditor", "client_or_sender")
    debitore = _v(payload, "debtor", "counterparty_or_recipient")
    somma = importo(payload.get("requested_amount"), "importo del credito")
    causa = _v(payload, "credit_source", "claim_subject", "subject") or da_indicare("titolo del credito (contratto, fatture, prestazione)")
    scadenza = _v(payload, "credit_due_date")
    interessi = _v(payload, "interest_requested") or da_indicare("interessi richiesti (legali o moratori ex D.Lgs. 231/2002)")
    prove = elenco(payload.get("written_evidence")) or elenco(payload.get("documents_offered")) or elenco(payload.get("attachments_list"))
    spese = _v(payload, "requested_costs")
    lavoro = str(model.get("code", "")).startswith("LAV")
    spese_txt = " ({})".format(spese.rstrip(".")) if spese else ""

    righe: list[str] = [
        intestazione(payload, "competent_court"),
        "RICORSO PER DECRETO INGIUNTIVO",
        "(artt. 633 e ss. c.p.c.)",
        "",
        f"{'Ricorre' if not e_ente(creditore) else 'Ricorre la società'} {blocco_parte(creditore, payload.get('_client_tax_id'), payload.get('_client_address')).rstrip('.')}, {blocco_difensore(payload, creditore)}",
        "",
        "contro",
        blocco_parte(debitore, payload.get("_counterparty_tax_id"), payload.get("_counterparty_address"), pec=payload.get("_counterparty_pec")),
        "",
        "PREMESSO CHE",
        f"1. il ricorrente è creditore di {debitore or da_indicare('debitore')} della somma di {somma} a titolo di {causa.rstrip('.')};",
        f"2. il credito è certo, liquido ed esigibile{f', scaduto il {ca._format_italian_date(scadenza)}' if scadenza else ''};",
        "3. il credito è provato per iscritto ai sensi dell'art. 634 c.p.c. dai documenti prodotti ed elencati in calce;",
        "4. le richieste di pagamento sono rimaste senza esito.",
    ]
    fatti = [riga for riga in ca._render_text_block_lines(payload.get("facts")) if riga != "-"]
    if fatti:
        righe.extend(["", *fatti])
    righe.extend([
        "",
        "Tutto ciò premesso, il ricorrente, come sopra rappresentato e difeso,",
        "",
        "CHIEDE",
        "",
        (
            f"che l'Ill.mo {'Giudice del Lavoro' if lavoro else 'Giudice'} adito voglia, ai sensi degli artt. 633 e 641 c.p.c., "
            f"ingiungere a {debitore or da_indicare('debitore')} di pagare al ricorrente, entro quaranta giorni dalla notificazione del decreto, "
            f"la somma di {somma}, oltre interessi {interessi.rstrip('.')}"
            f"{f' dal {ca._format_italian_date(scadenza)}' if scadenza else ''} fino al saldo, "
            f"nonché le spese e i compensi della procedura{spese_txt}, "
            "con l'avvertimento che nello stesso termine può essere proposta opposizione e che, in mancanza, "
            "il decreto diventerà esecutivo."
        ),
    ])
    esecutorieta = _v(payload, "provisional_enforceability_request")
    if esecutorieta and esecutorieta.strip().lower() not in {"no", "false", "0", "non richiesta"}:
        motivo = "" if esecutorieta.strip().lower() in {"si", "sì", "true", "1", "richiesta"} else f": {esecutorieta.rstrip('.')}"
        righe.extend([
            "",
            f"Chiede altresì che il decreto sia dichiarato provvisoriamente esecutivo ai sensi dell'art. 642 c.p.c.{motivo}.",
        ])
    righe.extend(["", "Si producono in copia i seguenti documenti:"])
    righe.extend(ca._render_numbered_list(prove) if prove else [da_indicare("prova scritta del credito (art. 634 c.p.c.)")])
    righe.extend([
        "",
        (
            f"Dichiarazione di valore: il valore del procedimento è pari a {somma}; il contributo unificato è dovuto "
            "nella misura ridotta alla metà ai sensi dell'art. 13, comma 3, del D.P.R. 115/2002."
        ),
    ])
    righe.extend(chiusura(payload))
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- precetto

ART_480_AVVERTIMENTO = (
    "Si avverte il debitore che può, con l'ausilio di un organismo di composizione della crisi o di un "
    "professionista nominato dal giudice, porre rimedio alla situazione di sovraindebitamento concludendo con "
    "i creditori un accordo di composizione della crisi o proponendo agli stessi un piano del consumatore "
    "(art. 480, comma 2, c.p.c.)."
)


def render_precetto(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    creditore = _v(payload, "creditor", "client_or_sender")
    debitore = _v(payload, "debtor", "counterparty_or_recipient")
    titolo = _v(payload, "enforcement_title") or da_indicare("titolo esecutivo (es. sentenza/decreto n., ufficio, data)")
    notifica = _v(payload, "title_service_date")
    voci = [
        ("sorte capitale", payload.get("principal_amount")),
        ("interessi maturati", payload.get("interest_amount")),
        ("spese liquidate e successive", payload.get("costs_amount")),
    ]
    totale = sum(n for n in (_numero(v) for _, v in voci) if n is not None)
    tutte = all(_numero(v) is not None for _, v in voci)
    termine = _v(payload, "payment_deadline")
    termine_txt = "entro il termine di dieci giorni dalla notificazione del presente atto"
    numero_giorni = _numero(termine)
    if numero_giorni and numero_giorni >= 10 and float(numero_giorni).is_integer():
        termine_txt = f"entro il termine di {int(numero_giorni)} giorni dalla notificazione del presente atto"

    righe: list[str] = [
        "ATTO DI PRECETTO",
        "(artt. 480 e ss. c.p.c.)",
        "",
        f"Ad istanza di {blocco_parte(creditore, payload.get('_client_tax_id'), payload.get('_client_address')).rstrip('.')}, {blocco_difensore(payload, creditore)}",
        "",
        "PREMESSO CHE",
        f"- il creditore è in possesso del seguente titolo esecutivo: {titolo.rstrip('.')};",
        (
            f"- il titolo, munito di formula esecutiva, è stato notificato il {ca._format_italian_date(notifica)};"
            if notifica
            else f"- il titolo, munito di formula esecutiva, è stato notificato il {da_indicare('data di notificazione del titolo (art. 480, comma 2, c.p.c.)')};"
        ),
        "",
        "INTIMA E FA PRECETTO",
        "",
        f"a {blocco_parte(debitore, payload.get('_counterparty_tax_id'), payload.get('_counterparty_address')).rstrip('.')},",
        f"di pagare {termine_txt} le seguenti somme:",
    ]
    for etichetta, valore in voci:
        righe.append(f"- {etichetta}: {importo(valore, etichetta)};")
    righe.append("- competenze e spese del presente atto (D.M. 55/2014): " + da_indicare("importo") + ";")
    righe.append(
        f"per complessivi {ca._format_currency(totale)} oltre alle competenze del presente atto, agli interessi successivi fino al saldo e alle spese occorrende,"
        if tutte
        else "per un totale da determinare sommando le voci che precedono, oltre agli interessi successivi fino al saldo e alle spese occorrende,"
    )
    righe.append("con l'avvertimento che, in mancanza, si procederà ad esecuzione forzata.")
    studio = _v(payload, "_studio_address")
    studio_in = f" in {studio}" if studio else ""
    ulteriore = _v(payload, "formal_intimation_to_pay")
    if ulteriore:
        righe.extend(["", ulteriore])
    righe.extend([
        "",
        ART_480_AVVERTIMENTO,
        "",
        (
            "Il creditore dichiara di eleggere domicilio presso lo studio del difensore"
            f"{studio_in}; "
            "ove lo studio non si trovi nel comune in cui ha sede il giudice competente per l'esecuzione, "
            f"elegge domicilio in {da_indicare('domicilio nel comune del giudice dell’esecuzione')} (art. 480, comma 3, c.p.c.)."
        ),
        "",
        "Il precetto diventa inefficace se nel termine di novanta giorni dalla sua notificazione non è iniziata l'esecuzione (art. 481 c.p.c.).",
    ])
    avvertenze = _v(payload, "legal_warnings")
    if avvertenze and avvertenze not in ART_480_AVVERTIMENTO:
        righe.extend(["", avvertenze])
    righe.extend(chiusura(payload))
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- procura

def render_procura(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    mandante = _v(payload, "granting_party", "client_or_sender")
    avvocato = ca._normalize_lawyer_name(_v(payload, "appointed_professional", "lawyer", "signature"))
    oggetto = _v(payload, "mandate_subject", "subject") or da_indicare("giudizio o procedimento per cui si conferisce la procura")
    ufficio = _v(payload, "court_name", "recipient_or_court")
    rg = riferimento_rg(payload)
    poteri = _v(payload, "special_powers_requested")
    domicilio = _v(payload, "domicile_election_details", "_studio_address")
    pec = _v(payload, "lawyer_pec", "_lawyer_pec")
    domiciliatario = _v(payload, "substitute_or_domiciliatary")
    nome_modello = str(model.get("name") or "Procura alle liti")
    titolo = "PROCURA ALLE LITI" if nome_modello.lower().startswith("procura alle liti") else nome_modello.upper()

    cf = _v(payload, "_lawyer_tax_id", "lawyer_tax_code")
    cf_avvocato = f" (C.F. {cf})" if cf else ""
    procedimento = oggetto.rstrip(".")
    if ufficio:
        procedimento += f", dinanzi al {ufficio}" if not ufficio.lower().startswith(("al ", "alla ", "dinanzi")) else f", {ufficio}"
    if rg:
        procedimento += f", {rg}"
    righe: list[str] = [
        titolo,
        "(art. 83 c.p.c.)",
        "",
        (
            f"{'La sottoscritta società' if e_ente(mandante) else 'Il/La sottoscritto/a'} "
            f"{blocco_parte(mandante, payload.get('_client_tax_id'), payload.get('_client_address')).rstrip('.')}"
            f"{', in persona del legale rappresentante pro tempore' if e_ente(mandante) else ''},"
        ),
        "",
        (
            f"nomina e costituisce proprio difensore l'{avvocato}{cf_avvocato}, "
            f"conferendogli procura a rappresentarlo/a e difenderlo/a nel seguente procedimento: {procedimento}, "
            "in ogni sua fase, stato e grado, compresa la fase cautelare, esecutiva e di opposizione"
            f"{', ' + poteri.rstrip('.') if poteri else ', con ogni facoltà di legge'}."
        ),
    ]
    if domiciliatario:
        righe.extend(["", f"Nomina altresì domiciliatario {domiciliatario.rstrip('.')}."])
    righe.extend([
        "",
        (
            f"Elegge domicilio presso lo studio del difensore{f' in {domicilio}' if domicilio else ''}"
            f"{f' e domicilio digitale all’indirizzo PEC {pec}' if pec else ''}."
        ),
        "",
        (
            "Dichiara di essere stato/a informato/a, ai sensi dell'art. 4, comma 3, del D.Lgs. 28/2010, della possibilità "
            "di avvalersi del procedimento di mediazione e dei benefici fiscali connessi, nonché, ai sensi dell'art. 2, comma 7, "
            "del D.L. 132/2014, della possibilità di ricorrere alla convenzione di negoziazione assistita."
        ),
        "",
        (
            "Dichiara di aver ricevuto l'informativa sul trattamento dei dati personali (art. 13 del Regolamento UE 2016/679) "
            "e presta il consenso al trattamento per le finalità del mandato."
        ),
    ])
    note = _v(payload, "revocation_or_renunciation_notes")
    if note:
        righe.extend(["", note])
    righe.extend([
        "",
        ca._render_footer_line(payload),
        "",
        f"Firma: ______________________________ ({mandante or 'mandante'})",
        "",
        f"È autentica. {avvocato}",
    ])
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- memorie 171-ter

_MEMORIE_171_TER = {
    1: (
        "almeno quaranta giorni prima dell'udienza di prima comparizione",
        "propone le domande e le eccezioni che sono conseguenza della domanda riconvenzionale o delle eccezioni "
        "proposte dalle altre parti e precisa o modifica le domande, le eccezioni e le conclusioni già proposte",
    ),
    2: (
        "almeno venti giorni prima dell'udienza",
        "replica alle domande e alle eccezioni nuove o modificate dalle altre parti, propone le eccezioni che sono "
        "conseguenza delle domande nuove e indica i mezzi di prova e le produzioni documentali",
    ),
    3: (
        "almeno dieci giorni prima dell'udienza",
        "replica alle eccezioni nuove e indica la prova contraria",
    ),
}


def numero_memoria(model: dict[str, Any]) -> int | None:
    trovato = re.search(r"memoria\s+n\.?\s*([123])\b", str(model.get("name") or ""), re.IGNORECASE)
    return int(trovato.group(1)) if trovato else None


def render_memoria(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    parte = _v(payload, "filing_party", "client_or_sender")
    controparte = _v(payload, "counterparty_or_recipient")
    numero = numero_memoria(model)
    rg = riferimento_rg(payload) or da_indicare("numero di ruolo generale")
    giudice = _v(payload, "judge_name")
    titolo = (
        f"MEMORIA INTEGRATIVA N. {numero} AI SENSI DELL'ART. 171-TER C.P.C."
        if numero
        else str(payload.get("title") or model.get("name") or "Memoria").upper()
    )
    righe: list[str] = [
        intestazione(payload),
        f"{rg}{f' — G.I. {giudice}' if giudice else ''}",
        "",
        titolo,
        "",
        f"nell'interesse di {blocco_parte(parte, payload.get('_client_tax_id'), '').rstrip('.')}, {blocco_difensore(payload, parte)}",
    ]
    if controparte:
        righe.extend(["", f"nei confronti di {blocco_parte(controparte, payload.get('_counterparty_tax_id'), '')}"])
    if numero:
        termine, contenuto = _MEMORIE_171_TER[numero]
        righe.extend([
            "",
            f"Con la presente memoria, depositata {termine}, la parte {contenuto} (art. 171-ter, n. {numero}, c.p.c.).",
        ])
    oggetto = _v(payload, "memo_subject")
    if oggetto:
        ca._append_section(righe, "OGGETTO", [oggetto])
    corpo = [riga for riga in ca._render_text_block_lines(payload.get("clarifications_or_arguments")) if riga != "-"]
    ca._append_section(righe, "IN FATTO E IN DIRITTO", corpo or [da_indicare("deduzioni della memoria")])
    istanze = elenco(payload.get("evidence_means"))
    if istanze:
        ca._append_section(righe, "ISTANZE ISTRUTTORIE", ca._render_numbered_list(istanze))
    conclusioni = [riga for riga in ca._render_text_block_lines(payload.get("requests_or_conclusions")) if riga != "-"]
    ca._append_section(
        righe,
        "CONCLUSIONI",
        conclusioni or ["Si insiste per l'accoglimento delle conclusioni già rassegnate negli atti introduttivi, come precisate nella presente memoria."],
    )
    documenti = elenco(payload.get("documents_offered"))
    if documenti:
        ca._append_section(righe, "SI PRODUCONO", ca._render_numbered_list(documenti))
    righe.extend(chiusura(payload))
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- comparsa

def render_comparsa(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    appello = "appell" in str(model.get("name") or "").lower()
    assistito = _v(payload, "appellee" if appello else "defendant", "client_or_sender")
    avversario = _v(payload, "appellant" if appello else "plaintiff", "counterparty_or_recipient")
    rg = riferimento_rg(payload) or da_indicare("numero di ruolo generale")
    udienza = _v(payload, "hearing_date")
    righe: list[str] = [
        intestazione(payload),
        rg,
        "",
        "COMPARSA DI COSTITUZIONE E RISPOSTA" + (" IN APPELLO" if appello else ""),
        "(artt. 166 e 167 c.p.c.)" if not appello else "(art. 347 c.p.c.)",
        "",
        f"per {blocco_parte(assistito, payload.get('_client_tax_id'), payload.get('_client_address')).rstrip('.')}, {blocco_difensore(payload, assistito)}",
        f"– {'appellato' if appello else 'convenuto'} –",
        "",
        f"contro {blocco_parte(avversario, payload.get('_counterparty_tax_id'), payload.get('_counterparty_address')).rstrip('.')}",
        f"– {'appellante' if appello else 'attore'} –",
    ]
    if udienza:
        righe.extend(["", f"Udienza di prima comparizione: {ca._format_italian_date(udienza)}."])
    posizione = [r for r in ca._render_text_block_lines(payload.get("position_on_facts")) if r != "-"]
    ca._append_section(
        righe,
        "PRESA DI POSIZIONE SUI FATTI",
        posizione or [da_indicare("presa di posizione chiara e specifica sui fatti posti a fondamento della domanda (art. 167, comma 1, c.p.c.)")],
    )
    ca._append_section(righe, "ECCEZIONI PROCESSUALI E DI MERITO", ca._merge_render_lines(
        ca._render_text_block_lines(payload.get("procedural_exceptions")),
        ca._render_text_block_lines(payload.get("merit_exceptions")),
    ) or [da_indicare("eccezioni processuali e di merito non rilevabili d'ufficio, a pena di decadenza")])
    riconvenzionale = _v(payload, "counterclaim")
    if riconvenzionale:
        ca._append_section(righe, "DOMANDA RICONVENZIONALE", [riconvenzionale])
    terzo = _v(payload, "third_party_call")
    if terzo:
        ca._append_section(righe, "CHIAMATA IN CAUSA DEL TERZO", [terzo, "Si chiede il differimento della prima udienza ai sensi dell'art. 269 c.p.c."])
    prove = elenco(payload.get("evidence_means"))
    ca._append_section(righe, "MEZZI DI PROVA", ca._render_numbered_list(prove) if prove else [da_indicare("mezzi di prova e documenti (art. 167, comma 1, c.p.c.)")])
    conclusioni = [r for r in ca._render_text_block_lines(payload.get("requests_or_conclusions")) if r != "-"]
    ca._append_section(
        righe,
        "CONCLUSIONI",
        conclusioni or [f"Voglia l'Ill.mo {'Collegio' if appello else 'Giudice'} adito respingere le domande avversarie perché infondate in fatto e in diritto, con vittoria di spese e compensi."],
    )
    documenti = elenco(payload.get("documents_offered"))
    if documenti:
        ca._append_section(righe, "SI PRODUCONO", ca._render_numbered_list(documenti))
    righe.extend(chiusura(payload))
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- messa in mora

def render_messa_in_mora(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    mittente = _v(payload, "sender", "client_or_sender")
    destinatario = _v(payload, "recipient", "counterparty_or_recipient")
    rapporto = _v(payload, "legal_relationship_title") or da_indicare("rapporto da cui nasce l'obbligazione (contratto, data)")
    inadempimento = _v(payload, "breach_description") or da_indicare("inadempimento contestato")
    richiesta = _v(payload, "requested_amount_or_performance") or da_indicare("somma dovuta o prestazione richiesta")
    termine = _v(payload, "deadline_assigned")
    termine_txt = (
        f"entro il {ca._format_italian_date(termine)}" if re.match(r"\d{4}-\d{2}-\d{2}", termine or "")
        else (f"entro {termine}" if termine else f"entro {da_indicare('termine assegnato (es. quindici giorni dal ricevimento)')}")
    )
    avvocato = ca._normalize_lawyer_name(payload.get("signature") or payload.get("lawyer"))
    somma_di_denaro = bool(re.search(r"€|\beuro\b|\d", richiesta, re.IGNORECASE))
    interessi_mora = ", oltre interessi dalla scadenza al saldo" if somma_di_denaro else ""
    righe: list[str] = [
        f"Spett.le {blocco_parte(destinatario, payload.get('_counterparty_tax_id'), payload.get('_counterparty_address'), pec=payload.get('_counterparty_pec'))}",
        "",
        "Trasmessa a mezzo PEC / raccomandata A.R.",
        "",
        "Oggetto: costituzione in mora e interruzione della prescrizione (artt. 1219 e 2943 c.c.)",
        "",
        f"Scrivo in nome e per conto di {blocco_parte(mittente, payload.get('_client_tax_id'), payload.get('_client_address')).rstrip('.')}, che mi ha conferito mandato.",
        "",
        f"In forza di {rapporto.rstrip('.')}, la Vostra parte è tenuta nei confronti del mio assistito a quanto segue: {richiesta.rstrip('.')}.",
        f"A oggi risulta il seguente inadempimento: {inadempimento.rstrip('.')}.",
        "",
        (
            f"Con la presente, pertanto, Vi intimo e formalmente Vi costituisco in mora ai sensi dell'art. 1219 c.c. "
            f"affinché provvediate {termine_txt} a {richiesta.rstrip('.')}{interessi_mora}."
        ),
    ]
    ulteriore = _v(payload, "formal_notice_to_perform")
    if ulteriore:
        righe.extend(["", ulteriore])
    righe.extend([
        "",
        (
            _v(payload, "warning_of_further_actions")
            or "In mancanza, senza ulteriore avviso, il mio assistito agirà nelle competenti sedi per la tutela dei propri diritti, con aggravio di spese a Vostro carico."
        ),
        "",
        "La presente vale quale atto interruttivo della prescrizione ai sensi dell'art. 2943 c.c.",
        "",
        ca._render_footer_line(payload),
        "",
        avvocato,
    ])
    return ca._clean_rendered_lines(righe)


# ---------------------------------------------------------------- deposito e NIR

def render_deposito(model: dict[str, Any], payload: dict[str, Any]) -> str:
    ca = _ca()
    parte = _v(payload, "filing_party", "client_or_sender")
    controparte = _v(payload, "counterparty_or_recipient")
    nir = "iscrizione" in str(model.get("name") or "").lower()
    rg = riferimento_rg(payload)
    documenti = elenco(payload.get("documents_list_detailed")) or elenco(payload.get("attachments_list"))
    numerazione = _v(payload, "attachments_numbering")
    scopo = _v(payload, "purpose_of_filing")
    righe: list[str] = [intestazione(payload)]
    if rg:
        righe.append(rg)
    if nir:
        righe.extend([
            "",
            "NOTA DI ISCRIZIONE A RUOLO",
            "(art. 71 disp. att. c.p.c.; artt. 14 e 18 D.M. 44/2011)",
            "",
            f"Parte istante: {blocco_parte(parte, payload.get('_client_tax_id'), payload.get('_client_address'))}",
            f"Difensore: {ca._normalize_lawyer_name(payload.get('lawyer') or payload.get('signature'))}"
            + (f", C.F. {_v(payload, '_lawyer_tax_id')}" if payload.get("_lawyer_tax_id") else "")
            + (f", PEC {_v(payload, '_lawyer_pec')}" if payload.get("_lawyer_pec") else ""),
            f"Controparte: {blocco_parte(controparte, payload.get('_counterparty_tax_id'), payload.get('_counterparty_address')) if controparte else da_indicare('controparte')}",
            f"Oggetto della domanda: {_v(payload, 'subject') or da_indicare('oggetto')}",
            f"Codice oggetto (catalogo ministeriale): {_v(payload, 'object_code', 'codice_oggetto', '_object_code') or da_indicare('codice oggetto PST')}",
            f"Valore della causa: {importo(payload.get('case_value') or payload.get('_case_value'), 'valore della causa')}",
            f"Contributo unificato (D.P.R. 115/2002, art. 13): {da_indicare('importo versato ed estremi del pagamento')}",
            "",
            "Nel processo civile telematico la nota di iscrizione a ruolo è generata nella busta di deposito "
            "(file DatiAtto.xml): questo prospetto serve a verificarne i dati prima dell'invio.",
        ])
    else:
        righe.extend([
            "",
            str(payload.get("title") or model.get("name") or "Deposito documenti").upper(),
            "",
            f"nell'interesse di {blocco_parte(parte, payload.get('_client_tax_id'), '').rstrip('.')}, {blocco_difensore(payload, parte)}",
            "",
            f"Il sottoscritto difensore deposita {'per ' + scopo.rstrip('.') if scopo else 'i seguenti documenti'}:",
        ])
    if documenti:
        ca._append_section(righe, "DOCUMENTI", ca._render_numbered_list(documenti))
    elif not nir:
        ca._append_section(righe, "DOCUMENTI", [da_indicare("elenco dei documenti depositati")])
    if numerazione:
        righe.extend(["", f"Numerazione degli allegati: {numerazione}"])
    if scopo and nir:
        righe.extend(["", f"Finalità del deposito: {scopo}"])
    righe.extend(chiusura(payload))
    return ca._clean_rendered_lines(righe)


def renderer_dedicato(model: dict[str, Any]) -> Callable[[dict[str, Any], dict[str, Any]], str] | None:
    """Sceglie il renderer dall'atto (nome e campi), non dalla sola area."""
    nome = str(model.get("name") or "").strip().lower()
    campi = set(model.get("required_extra_fields") or [])
    if {"credit_source", "written_evidence"} <= campi:
        return render_decreto_ingiuntivo
    if "precetto" in nome and "enforcement_title" in campi:
        return render_precetto
    if nome.startswith("procura") and {"granting_party", "appointed_professional"} <= campi:
        return render_procura
    if numero_memoria(model) and "clarifications_or_arguments" in campi:
        return render_memoria
    if "position_on_facts" in campi and "comparsa" in nome:
        return render_comparsa
    if "formal_notice_to_perform" in campi:
        return render_messa_in_mora
    if {"documents_list_detailed", "purpose_of_filing"} <= campi and model.get("area") == "CIVILE":
        return render_deposito
    return None
