"""Distingue la natura della fonte e il procedimento prima di proporre termini."""
from __future__ import annotations
import re
from typing import Any, Iterable
from pct.atto_della_causa import CARATTERI_INTESTAZIONE, ruoli_in_intestazione
from pct.ragionamento.testo import rg_normale
from pct.registro_letture.fatti_repository import Fatto

_ALLEGATO_EMAIL = re.compile(r"(?im)^\[Allegato:[^\]\r\n]+\][ \t]*$")
_AUTORITA_GIUDIZIARIA = re.compile(r"\b(?:tribunale|corte|giudice\s+di\s+pace)\b", re.I)
_DISPOSITIVO_DATA = re.compile(
    r"\b(?:fissa|rifissa|rinvia|differisce|assegna)\b.{0,170}"
    r"\b(?:udienza|termine|deposito|costituzione)\b",
    re.I | re.S,
)
PROVA_RUOLO_ALLEGATO = "ruolo_allegato_pec"


def escludi_date_di_allegati_estranei(fatti: list[Fatto], testo: str, *, contesto) -> None:
    """Attribuisce una data al ruolo del singolo provvedimento nell’estrazione MIME."""
    from .estrazione_ruolo import estrai_ruoli

    numero = str(contesto.numero_rg or "").strip()
    anno = str(contesto.anno_rg or "").strip()
    if not numero.isdecimal() or not anno.isdecimal():
        return
    atteso = f"{int(numero)}/{anno}"
    date_processuali = [
        fatto for fatto in fatti
        if fatto.categoria == "data" and fatto.campo in {"udienza", "termine", "costituzione"}
        and fatto.verifica in {"plausibile", "verificata"}
    ]
    if not date_processuali:
        return
    delimitatori = list(_ALLEGATO_EMAIL.finditer(testo))
    for indice, marker in enumerate(delimitatori):
        fine = delimitatori[indice + 1].start() if indice + 1 < len(delimitatori) else len(testo)
        sezione = testo[marker.end():fine].lstrip("\r\n")
        dispositivo = _DISPOSITIVO_DATA.search(sezione, 0, 1800)
        if dispositivo is None:
            continue
        intestazione = sezione[:dispositivo.start()]
        if not _AUTORITA_GIUDIZIARIA.search(intestazione):
            continue
        ruoli = {f.valore for f in estrai_ruoli(intestazione, origine="indice") if f.confidenza == 1.0}
        if len(ruoli) != 1 or atteso in ruoli:
            continue
        if any(f.valore == atteso for f in estrai_ruoli(sezione[dispositivo.start():], origine="indice")):
            continue
        (ruolo,) = ruoli
        for fatto in date_processuali:
            if not marker.end() <= fatto.posizione < fine:
                continue
            fatto.verifica = "respinta"
            fatto.prove.append({
                "codice": PROVA_RUOLO_ALLEGATO,
                "esito": "respinta",
                "dettaglio": f"Il provvedimento allegato indica R.G. {ruolo}. Il fascicolo è R.G. {atteso}.",
            })


def _documento_identita_strutturale(head: str) -> bool:
    """Riconosce il documento personale vero, non un atto che lo cita."""
    porzione = head[:1800]
    tipo = re.search(
        r"(?:carta\s+d[’'i]?\s*identit[aà]|carta\s+di\s+identit[aà]|identity\s+card|passaporto|passport|patente\s+di\s+guida|permesso\s+di\s+soggiorno)",
        porzione,
        re.I,
    )
    # Le scansioni ruotate possono perdere il titolo. Si riconosce allora
    # soltanto la struttura personale completa, mai il nome del file.
    giudiziario = re.search(r"\b(?:tribunale|ricorso|ordinanza|sentenza|relata|procura|citazione)\b", porzione[:350], re.I)
    campi_ocr = sum(bool(re.search(pattern, porzione, re.I)) for pattern in (
        r'\bcognome', r'\bnome', r'\bcittadinanza|\bnazionalit',
        r'\bscade\s+il|\bscadenza|expiry',
        r'\bstatura|\bsesso|\bconnotati|\bcontrassegni',
        r'\b[A-Z]{2}\s*\d{6,}\b|\bIDITA|P<ITA',
    ))
    personale = re.search(r'\bconnotati|\bcontrassegni|\bstatura|\bIDITA|P<ITA', porzione, re.I)
    if not giudiziario and personale and campi_ocr >= 5:
        return True
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


_UFFICIO_NEL_NOME = re.compile(
    r"\b(?:tribunale|corte\s+d\s*appello|corte\s+di\s+appello|giudice\s+di\s+pace)\s+(?:di\s+)?([a-zàèéìòù]+(?:\s+[a-zàèéìòù]+){0,3})",
    re.I,
)


def precedente_dal_nome(nome: str, ufficio: str) -> bool:
    """Il nome del file indica un provvedimento di un altro ufficio giudiziario: è giurisprudenza prodotta.

    Usato dove la lettura non ha ancora la natura documentale (fascicoli letti da motori precedenti):
    «Tribunale-di-Cosenza-Sentenza-n.-394-2023» in un fascicolo del Tribunale di Locri non è la sentenza
    della causa e non apre obblighi di notifica.
    """
    citta = _citta_dell_ufficio(ufficio)
    piatto = re.sub(r"[^a-z0-9àèéìòù]+", " ", str(nome or "").casefold())
    trovato = _UFFICIO_NEL_NOME.search(piatto)
    if not citta or not trovato:
        return False
    return not f" {trovato.group(1)} ".startswith(f" {citta} ") and f" {citta} " not in f" {piatto} "


def precedenti_del_fascicolo(fascicolo: Any, fatti: Iterable[Any] = ()) -> set[str]:
    """I documenti del fascicolo che sono giurisprudenza prodotta, non atti della causa.

    Dal fatto letto («natura_documentale = precedente_giurisprudenziale») o, per le letture di motori
    precedenti, dal nome del file che indica un altro ufficio. Esclusi da notifiche, economia e importi.
    """
    precedenti = {
        str(getattr(f, "oggetto_id", "") or "") for f in fatti
        if getattr(f, "campo", "") == "natura_documentale" and getattr(f, "valore", "") == "precedente_giurisprudenziale"
        and getattr(f, "verifica", "") not in {"respinta", "ignorata"}
    }
    ufficio = str(getattr(fascicolo, "tribunale", "") or getattr(fascicolo, "ufficio_giudiziario", "") or "")
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        if precedente_dal_nome(str(getattr(documento, "nome", "") or ""), ufficio):
            precedenti.add(str(getattr(documento, "id", "") or ""))
    precedenti.discard("")
    return precedenti



def documenti_ufficio_incompatibile(fatti: Iterable[Fatto]) -> set[str]:
    """Esclude la fonte se il ruolo incompatibile appartiene alla sua intestazione.

    Un ruolo citato nel corpo può essere respinto come dato della causa.
    La citazione lascia utilizzabili l’atto e gli altri fatti che contiene.
    """
    incompatibili: set[str] = set()
    confermati: set[str] = set()
    for fatto in fatti:
        if fatto.tipo != "documento" or fatto.campo != "numero_ruolo" or not fatto.oggetto_id:
            continue
        if fatto.verifica == "corretta" or (
            fatto.verifica == "verificata" and any(
                prova.get("codice") == "concordanza" and prova.get("esito") == "ok"
                for prova in fatto.prove
            )
        ):
            confermati.add(fatto.oggetto_id)
        elif (fatto.verifica == "respinta" and fatto.posizione < CARATTERI_INTESTAZIONE
              and any(prova.get("codice") == "ufficio_giudiziario" and prova.get("esito") == "respinta"
                      for prova in fatto.prove)):
            incompatibili.add(fatto.oggetto_id)
    return incompatibili - confermati


def natura_documentale(testo: str, numero_rg: str = "", anno_rg: str = "", ufficio: str = "") -> tuple[str, str]:
    from .copie_atti import messaggio_strutturato
    if messaggio_strutturato(testo):
        return "messaggio_pec", "La fonte è un messaggio o una ricevuta: l’atto da notificare è l’allegato, non la busta email."
    head = " ".join(str(testo or "").split())[:4000]
    contract_heading = re.search(
        r"(?:^|\n)\s*(?:\d{1,3}\s+)?\*{0,2}contratto\s+di\s+prestazione\s+d['’]\s*opera(?:\s+occasionale)?",
        str(testo or "")[:2200], re.I,
    )
    if contract_heading and not re.search(r"\b(?:tribunale|ricorso|citazione|sentenza|ordinanza)\b", str(testo or "")[:contract_heading.start()], re.I):
        return "contratto_prestazione_opera", "Il documento disciplina una prestazione d’opera: i contraenti non sono parti processuali e le sue date non sono termini processuali."
    if re.search(r"(?:contratto individuale di lavoro|contratto di lavoro a tempo determinato)", head[:1800], re.I):
        return "contratto_lavoro", "Il documento disciplina il rapporto di lavoro: le sue date non sono termini processuali."
    if _documento_identita_strutturale(head):
        return "documento_identita", "Date di emissione, scadenza e nascita del documento di identità."
    if (
        re.search(r"(?:io sottoscritt|procura alle liti)", head[:600], re.I)
        # Formule di conferimento della procura (art. 83 c.p.c.): anche «delego … a rappresentarmi e difendermi»
        # e «conferisco … procura/facoltà/poteri» (revisione del 04/11/2026: 30 procure lette come mediazione).
        and re.search(r"(?:difensore e procuratore|conferisc\w{0,8}.{0,60}(?:potere|poteri|mandato|procura|facolt)|nomino.{0,100}difensore|"
                      r"deleg[oa].{0,120}(?:rappresentar\w*|difender\w*|assister\w*))", head, re.I | re.S)
        and not _nomina_difensore_penale(head)
    ):
        return "procura", "Formula di conferimento della rappresentanza processuale riconosciuta nel contenuto."
    judicial = re.search(
        r"(?:REPUBBLICA ITALIANA|TRIBUNALE.{0,90}(?:VERBALE|ORDINANZA|SENTENZA|DECRETO))",
        head[:450], re.I,
    )
    if judicial and numero_rg and anno_rg:
        atteso = rg_normale(numero_rg, anno_rg)
        ruoli = {rg_normale(numero, anno) for numero, anno in ruoli_in_intestazione(head)} - {""}
        if atteso and len(ruoli) == 1 and atteso not in ruoli:
            (letto,) = ruoli
            return "precedente_giurisprudenziale", f"L'intestazione identifica il procedimento {letto}, diverso dal fascicolo {atteso}."
        # Una sentenza di un altro ufficio, anche con il numero di ruolo
        # oscurato («n. XXX/2022 R.G.»): se non cita né l'ufficio né il ruolo
        # del fascicolo, e' giurisprudenza prodotta, non un provvedimento della causa.
        citta = _citta_dell_ufficio(ufficio)
        intestazione = re.sub(r"[^a-z0-9àèéìòù]+", " ", head[:1500].casefold())
        ruolo_del_fascicolo = re.search(rf"(?<!\d){int(numero_rg)}\s*/\s*{anno_rg}\b", head) if str(numero_rg).isdigit() else None
        if citta and f" {citta} " not in f" {intestazione} " and not ruolo_del_fascicolo and re.search(r"\b(?:tribunale|corte)\b", intestazione[:700]):
            return "precedente_giurisprudenziale", f"L'intestazione indica un ufficio giudiziario diverso da quello del fascicolo ({ufficio.strip()})."
    elif judicial and str(ufficio or "").strip():
        # Fascicolo senza numero di ruolo (ancora da iscrivere o non compilato): basta l'ufficio. Una decisione
        # della Corte di cassazione in un fascicolo di merito, o di un altro tribunale, è giurisprudenza prodotta,
        # non il provvedimento della causa (revisione del 10/11/2026: Cass. 29961/2023 in un fascicolo del
        # Tribunale di Vicenza senza RG letta come sentenza della causa).
        # Solo le decisioni (sentenza o ordinanza «in nome del popolo italiano»): un provvedimento qualsiasi di
        # un altro ufficio (convalida del GIP, decreto) senza RG non basta; la Corte costituzionale ha la sua voce.
        intestazione = re.sub(r"[^a-z0-9àèéìòù]+", " ", head[:1500].casefold())
        decisione = re.search(r"\bin nome del popolo italiano\b", intestazione) and re.search(r"\b(?:sentenza|ordinanza)\b", intestazione)
        # Nei fascicoli amministrativi (ottemperanza, art. 112 c.p.a.) la sentenza del giudice ordinario è il titolo
        # da eseguire, non giurisprudenza; in appello la sentenza del primo grado è quella impugnata.
        sede = str(ufficio).casefold()
        if not decisione or re.search(r"\bcorte costituzionale\b", intestazione) or re.search(
                r"amministrativ|\btar\b|consiglio di stato|giustizia amministrativa", sede):
            return "", ""
        appello = bool(re.search(r"\bcorte\s+d\W?\s*appello\b|\bcorte\s+di\s+appello\b", sede))
        if re.search(r"\bcorte (?:suprema )?di cassazione\b", intestazione) and "cassazione" not in str(ufficio).casefold():
            return "precedente_giurisprudenziale", f"Decisione della Corte di cassazione in un fascicolo di merito ({ufficio.strip()})."
        citta = _citta_dell_ufficio(ufficio)
        if not appello and citta and f" {citta} " not in f" {intestazione} " and re.search(r"\b(?:tribunale|corte)\b", intestazione[:700]):
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
            r"note.{0,50}in\s+sostituzione\s+(?:dell(?:a|[’'])?\s*)?udienza|"
            r"termine perentorio.{0,60}deposito di note",
            clausola,
            re.I,
        ):
            note.add(f.valore[:10])
    for f in fatti:
        if any(p.get("codice") == "udienza_sostituita_distinta" for p in f.prove):
            continue
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
    natura, motivo = natura_documentale(testo, contesto.numero_rg, contesto.anno_rg, contesto.ufficio_giudiziario)
    if not natura:
        return fatti
    for fatto in fatti:
        if (fatto.categoria == "data" and fatto.campo in {"termine", "udienza", "costituzione"} and natura in {"contratto_lavoro", "contratto_prestazione_opera", "documento_identita", "precedente_giurisprudenziale"}) or (natura in {"precedente_giurisprudenziale", "messaggio_pec"} and fatto.campo == "domanda_atto") or (natura == "precedente_giurisprudenziale" and fatto.categoria == "importo"):
            fatto.verifica = "respinta"
            fatto.prove = list(fatto.prove) + [{"codice": "pertinenza_documentale", "esito": "respinta", "dettaglio": motivo}]
    fatti.append(Fatto(categoria="evento", campo="natura_documentale", valore=natura, etichetta=natura.replace("_", " ").capitalize(), contesto=motivo, origine=origine, confidenza=0.95, verifica="verificata", prove=[{"codice": "contenuto_identificativo", "esito": "ok", "dettaglio": motivo}]))
    return fatti
