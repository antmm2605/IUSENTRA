"""Distingue la natura della fonte e il procedimento prima di proporre termini."""
from __future__ import annotations
import re
from pct.registro_letture.fatti_repository import Fatto

def _documento_identita_strutturale(head: str) -> bool:
    """Riconosce il documento personale vero, non un atto che lo cita."""
    porzione = head[:1800]
    tipo = re.search(
        r"(?:carta\s+d[’'i]?\s*identit[aà]|carta\s+di\s+identit[aà]|identity\s+card|passaporto|passport|patente\s+di\s+guida|permesso\s+di\s+soggiorno)",
        porzione,
        re.I,
    )
    if not tipo:
        return False
    intestazione_forte = re.search(
        r"(?:repubblica\s+italiana|ministero\s+dell['’]interno|comune\s+di|questura|passport|identity\s+card)",
        porzione[:350],
        re.I,
    )
    campi = sum(
        1
        for pattern in (
            r"\bcognome\b|\bsurname\b",
            r"\bnome\b|\bname\b",
            r"\bcittadinanza\b|\bnazionalit[aà]\b|\bnationality\b",
            r"\bscadenza\b|data\s+di\s+scadenza|date\s+of\s+expiry",
            r"\bstatura\b|\bsesso\b|\bsex\b",
            r"\bIDITA|P<ITA|CA\d{4,}[A-Z]{0,3}\b|[A-Z]{2}\s*\d{6,}\b",
        )
        if re.search(pattern, porzione, re.I)
    )
    if intestazione_forte and campi >= 2:
        return True
    # Una scansione cartacea può iniziare direttamente con «Carta d'identità»,
    # ma deve comunque mostrare più campi propri del documento.
    return bool(tipo.start() < 250 and campi >= 3)


def _nomina_difensore_penale(head: str) -> bool:
    """La nomina del difensore di fiducia non e' una procura alle liti.

    Sono due atti diversi: la procura alle liti conferisce la rappresentanza
    processuale nel civile (art. 83 c.p.c.), la nomina del difensore di fiducia
    designa il difensore nel penale (art. 96 c.p.p.). Nel deposito hanno ruoli
    diversi, e all'avvocato dicono cose diverse.

    La formula pero' si somiglia — «io sottoscritto… nomino… difensore» — e la
    regola generica se le prendeva entrambe. I segni del penale invece non sono
    ambigui: il titolo dell'atto, la qualita' di indagato o imputato, il
    registro delle notizie di reato.
    """
    return bool(
        re.search(r"nomina\s+(?:del\s+|di\s+)?difensore(?:\s+di\s+fiducia)?", head[:400], re.I)
        or re.search(r"\bdifensore\s+di\s+fiducia\b", head, re.I)
        and re.search(r"\bindagat\w+\b|\bimputat\w+\b|\bR\.?\s*G\.?\s*N\.?\s*R\.?\b|procedimento\s+penale", head, re.I)
    )


def _citta_dell_ufficio(ufficio: str) -> str:
    """«Tribunale di Santa Maria Capua Vetere» -> «santa maria capua vetere»."""
    testo = re.sub(r"[^a-z0-9àèéìòù]+", " ", str(ufficio or "").casefold()).strip()
    if " di " in f" {testo} ":
        testo = f" {testo} ".rsplit(" di ", 1)[1].strip()
    testo = re.sub(r"^(?:tribunale|ordinario|corte|d appello|giudice|pace)\s+", "", testo)
    return testo if len(testo) >= 3 else ""


def natura_documentale(testo: str, numero_rg: str = "", anno_rg: str = "", ufficio: str = "") -> tuple[str, str]:
    head = " ".join(str(testo or "").split())[:4000]
    if re.search(r"(?:contratto individuale di lavoro|contratto di lavoro a tempo determinato)", head[:1800], re.I):
        return "contratto_lavoro", "Il documento disciplina il rapporto di lavoro: le sue date non sono termini processuali."
    if _documento_identita_strutturale(head):
        return "documento_identita", "Date di emissione, scadenza e nascita del documento di identità."
    if (
        re.search(r"(?:io sottoscritt|procura alle liti)", head[:600], re.I)
        and re.search(r"(?:difensore e procuratore|conferisco.{0,35}(?:potere|mandato)|nomino.{0,100}difensore)", head, re.I)
        and not _nomina_difensore_penale(head)
    ):
        return "procura", "Formula di conferimento della rappresentanza processuale riconosciuta nel contenuto."
    judicial = re.search(r"(?:REPUBBLICA ITALIANA|TRIBUNALE.{0,90}(?:VERBALE|ORDINANZA|SENTENZA))", head[:450], re.I)
    if judicial and numero_rg and anno_rg:
        patterns = [r"(?:VERBALE DELLA CAUSA|numero registro generale|ruolo generale|procedimento.{0,65}iscritto al|causa.{0,40}iscritta al)\s*(?:n\.?|numero)?\s*(?:r\.?\s*g\.?\s*)?(\d+)\s*/\s*(\d{4})", r"(?<![A-Za-z])(?:R\.?\s*G\.?|NRG)\s*(?:n\.?)?\s*(\d+)\s*/\s*(\d{4})"]
        matches = sorted((m.start(), f"{int(m.group(1))}/{m.group(2)}") for pat in patterns for m in re.finditer(pat, head, re.I))
        atteso = f"{int(numero_rg)}/{anno_rg}" if str(numero_rg).isdigit() else ""
        if matches and matches[0][1] != atteso:
            return "precedente_giurisprudenziale", f"L'intestazione identifica il procedimento {matches[0][1]}, diverso dal fascicolo {atteso}."
        # Una sentenza di un altro ufficio, anche con il numero di ruolo
        # oscurato («n. XXX/2022 R.G.»): se non cita né l'ufficio né il ruolo
        # del fascicolo, e' giurisprudenza prodotta, non un provvedimento della causa.
        citta = _citta_dell_ufficio(ufficio)
        intestazione = re.sub(r"[^a-z0-9àèéìòù]+", " ", head[:1500].casefold())
        ruolo_del_fascicolo = re.search(rf"(?<!\d){int(numero_rg)}\s*/\s*{anno_rg}\b", head) if str(numero_rg).isdigit() else None
        if citta and f" {citta} " not in f" {intestazione} " and not ruolo_del_fascicolo and re.search(r"\b(?:tribunale|corte)\b", intestazione[:700]):
            return "precedente_giurisprudenziale", f"L'intestazione indica un ufficio giudiziario diverso da quello del fascicolo ({ufficio.strip()})."
    return "", ""

def applica_pertinenza(fatti: list[Fatto], testo: str, *, contesto, origine: str) -> list[Fatto]:
    # La medesima data può essere descritta come udienza e come termine per
    # note: la modalità viene decisa qui, prima della consegna a calendario.
    note = set()
    for f in fatti:
        if f.categoria != "data" or f.campo not in {"udienza", "termine"}:
            continue
        # The short display quotation can end inside «sostituita». Read the
        # complete clause from the text while still inside the reading motor.
        dopo = testo[f.posizione:f.posizione + 400]
        prossima = re.search(r"\budienza\s+del\b", dopo, re.I)
        if prossima:
            dopo = dopo[:prossima.start()]
        clausola = " ".join((testo[max(0, f.posizione - 80):f.posizione] + dopo).split())
        if re.search(
            r"trattazione scritta|sostituit[ao].{0,80}(?:deposito|note)|"
            r"note.{0,50}in\s+sostituzione\s+dell(?:a|[’'])?\s*udienza|"
            r"termine perentorio.{0,60}deposito di note",
            clausola,
            re.I,
        ):
            note.add(f.valore[:10])
    for f in fatti:
        if f.categoria == "data" and f.campo in {"udienza", "termine"} and f.valore[:10] in note:
            giorno = f.valore[:10]
            ora = f.valore[11:16] if len(f.valore) >= 16 and f.valore[10] == "T" else ""
            f.campo = "termine"
            f.valore = giorno + (f"T{ora}" if ora else "")
            f.etichetta = (
                "Deposito note in sostituzione udienza del "
                + giorno[8:10] + "/" + giorno[5:7] + "/" + giorno[:4]
                + (f" ore {ora}" if ora else "")
            )
            if not any(p.get("codice") == "modalita_note" and p.get("esito") == "ok" for p in f.prove):
                f.prove = list(f.prove) + [{
                    "codice": "modalita_note",
                    "esito": "ok",
                    "dettaglio": (
                        "Deposito di note scritte in sostituzione dell’udienza; "
                        + (f"le ore {ora} sono il termine del deposito, non un orario di comparizione." if ora else "nessuna comparizione fisica fissata.")
                    ),
                    "modalita": "note_scritte",
                    "ora_termine": ora,
                }]
    natura, motivo = natura_documentale(testo, contesto.numero_rg, contesto.anno_rg)
    if not natura:
        return fatti
    for fatto in fatti:
        if (fatto.categoria == "data" and fatto.campo in {"termine", "udienza", "costituzione"} and natura in {"contratto_lavoro", "documento_identita", "precedente_giurisprudenziale"}) or (natura == "precedente_giurisprudenziale" and (fatto.categoria == "importo" or fatto.campo == "domanda_atto")):
            fatto.verifica = "respinta"
            fatto.prove = list(fatto.prove) + [{"codice": "pertinenza_documentale", "esito": "respinta", "dettaglio": motivo}]
    fatti.append(Fatto(categoria="evento", campo="natura_documentale", valore=natura, etichetta=natura.replace("_", " ").capitalize(), contesto=motivo, origine=origine, confidenza=0.95, verifica="verificata", prove=[{"codice": "contenuto_identificativo", "esito": "ok", "dettaglio": motivo}]))
    return fatti
