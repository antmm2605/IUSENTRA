"""Il linguaggio legale delle voci che il software scrive in agenda.

Ogni impegno nato da una PEC o da una lettura si legge come lo scriverebbe l'avvocato: che cosa ha disposto o
comunicato la cancelleria, in quale causa (RG e ufficio), con data, ora e modalità dell'udienza. Niente sigle
interne («note_scritte»), niente prefissi tecnici («PEC ricevuta:»), niente ripetizioni («rigetto istanza: istanza
rigettata»). Modalità d'udienza: artt. 127, 127-bis e 127-ter c.p.c.
"""

from __future__ import annotations

import re

MODALITA_UDIENZA = {
    "note_scritte": "cartolare con note scritte ex art. 127-ter c.p.c.",
    "cartolare": "cartolare con note scritte ex art. 127-ter c.p.c.",
    "trattazione_scritta": "cartolare con note scritte ex art. 127-ter c.p.c.",
    "da_remoto": "da remoto (art. 127-bis c.p.c.)",
    "remoto": "da remoto (art. 127-bis c.p.c.)",
    "videoconferenza": "da remoto (art. 127-bis c.p.c.)",
    "audiovisiva": "da remoto (art. 127-bis c.p.c.)",
    "mista": "mista, in presenza e da remoto (art. 127-bis c.p.c.)",
    "in_presenza": "in presenza",
    "presenza": "in presenza",
}

#: eventi del registro di cancelleria (SICID) riscritti in forma legale
EVENTI_REGISTRO = (
    (r"^rigetto\s+istanza", "rigetto dell'istanza"),
    (r"^accoglimento\s+istanza", "accoglimento dell'istanza"),
    (r"^deposito\s+istanz\w*(?:\s+generic\w*)?", "deposito di istanza"),
    (r"^deposito\s+atto\s+non\s+codificato", "deposito di atto"),
    (r"^atto\s+non\s+codificato", "atto non codificato nel registro"),
    (r"^deposito\s+(?:di\s+)?memori\w*", "deposito di memoria"),
    (r"^deposito\s+(?:di\s+)?note", "deposito di note"),
    (r"^iscrizione\s+(?:a\s+)?ruolo(?:\s+generale)?", "iscrizione della causa a ruolo"),
    (r"^annotazione", "annotazione di cancelleria"),
    (r"^deposito\s+ricorso\s+notificato", "deposito del ricorso notificato"),
    (r"^deposito\s+verbale", "deposito del verbale d'udienza"),
    (r"^riassegnazione\s+termine\s+per\s+note\s+in\s+sostituzione\s+udienza", "riassegnazione del termine per note scritte in sostituzione dell'udienza (art. 127-ter c.p.c.)"),
    (r"^fissazione\s+termine\s+per\s+note\s+in\s+sostituzione\s+udienza", "assegnazione del termine per note scritte in sostituzione dell'udienza (art. 127-ter c.p.c.)"),
)
_MINUSCOLE = {"di", "del", "della", "dello", "dei", "degli", "delle", "e", "ed", "in", "per", "a", "al", "alla", "da", "con", "su", "c.", "s.p.a.", "s.r.l."}


def modalita_legale(codice: str) -> str:
    """«note_scritte» → «cartolare con note scritte ex art. 127-ter c.p.c.»; testo libero restituito com'è."""
    chiave = "_".join(str(codice or "").strip().lower().replace("-", " ").split())
    return MODALITA_UDIENZA.get(chiave, str(codice or "").strip().replace("_", " "))


def nome_proprio(testo: str) -> str:
    """«MINISTERO DELL'ISTRUZIONE E DEL MERITO» → «Ministero dell'Istruzione e del Merito»."""
    parole = []
    for indice, parola in enumerate(str(testo or "").split()):
        bassa = parola.lower()
        if indice and bassa in _MINUSCOLE:
            parole.append(bassa)
        elif "'" in bassa:
            prima, _, dopo = bassa.partition("'")
            parole.append(f"{prima if indice else prima.capitalize()}'{dopo.capitalize()}")
        else:
            parole.append(bassa.capitalize())
    return " ".join(parole)


def evento_registro(evento: str, dettaglio: str = "") -> str:
    """L'evento di cancelleria in forma legale, senza ripetere nel dettaglio ciò che l'evento già dice."""
    base = " ".join(str(evento or "").lower().split())
    originale = base
    for espressione, legale in EVENTI_REGISTRO:
        if re.search(espressione, base):
            base = legale
            break
    resto = parole_del_registro(" ".join(str(dettaglio or "").split()))
    # «DEPOSITATO ATTO ricorso notificato…» ripete l'evento: resta ciò che è stato depositato o annotato.
    resto = re.sub(r"^(?:depositat\w*|inserit\w*|iscritt\w*)\s+(?:atto\s+|a\s+)?", "", resto, flags=re.I)
    resto = re.sub(r"^atto\s+", "", resto, flags=re.I)
    radici = {p[:5] for p in re.findall(r"\w{4,}", f"{base} {originale}".lower())}
    nuove = [p for p in re.findall(r"\w{4,}", resto.lower()) if p[:5] not in radici]
    if not resto or not nuove:
        return base or "comunicazione di cancelleria"
    if len(resto) > 90:
        resto = resto[:90].rsplit(" ", 1)[0] + "…"
    return f"{base}: {resto}"


_SIGLE = frozenset({"RG", "PEC", "CTU", "CTP", "INPS", "INAIL", "MIM", "TAR", "PST", "SDI", "IVA", "CU", "DM", "DPR"})
#: parole del registro di cancelleria (SICID/SIECIC) scritte in maiuscolo: vanno in carattere normale
_PAROLE_REGISTRO = frozenset("""
DEPOSITATO DEPOSITATA DEPOSITATE DEPOSITATI DEPOSITO ATTO ATTI DA PARTE DI DEL DELLA DELLE DEI DEGLI IL LO LA LE GLI E ED A
NOTE SCRITTE UDIENZA UDIENZE FISSATO FISSATA FISSAZIONE TERMINE TERMINI PER IN SOSTITUZIONE RINVIO RINVIATA RINVIATO AL ALLA
ADEMPIMENTI EVENTI FASE ISTRUTTORIA DISCUSSIONE COMUNICAZIONE NOTIFICA RICORSO SENTENZA DECRETO ORDINANZA VERBALE ISTANZA
ISTANZE GENERICHE NON CODIFICATO RIASSEGNAZIONE RIASSEGNATO REVOCA REVOCATA COSTITUZIONE COSTITUITO COSTITUITA DESIGNAZIONE
GIUDICE ISCRIZIONE RUOLO GENERALE ISCRITTO ANNOTAZIONE INSERITA OGGETTO CON NUMERO PUBBLICATA PUBBLICAZIONE ESTINZIONE
FASCICOLO ASSEGNATO COMPARIZIONE PARTI
""".split())


def parole_del_registro(testo: str) -> str:
    """Le parole del registro in minuscolo; sigle e nomi propri restano come sono scritti."""
    parole = []
    for parola in str(testo or "").split(" "):
        nuda = re.sub(r"[^\wÀ-Ýà-ý]", "", parola)
        parole.append(parola.lower() if nuda.isupper() and nuda in _PAROLE_REGISTRO and nuda not in _SIGLE else parola)
    return " ".join(parole)


def titolo_cancelleria(sintesi: str, *, rg: str = "", ufficio: str = "") -> str:
    """«Comunicazione di cancelleria: rigetto dell'istanza – RG 1263/2026 – Tribunale di Brescia»."""
    parti = [f"Comunicazione di cancelleria: {sintesi}"]
    if rg:
        parti.append(f"RG {rg}")
    if ufficio:
        parti.append(nome_proprio(ufficio) if ufficio.isupper() else ufficio)
    return " – ".join(parti)


def riga_contesto(*, client: str = "", numero_fascicolo: str = "", rg: str = "", ufficio: str = "") -> str:
    """Sotto il titolo: «Gramuglia Caterina · Fascicolo 2026/327 · RG 901/2026 · Tribunale di Vicenza»."""
    rg_pulito = re.sub(r"^\s*(?:R\.?\s?G\.?|RG)\s*(?:n\.\s*)?", "", str(rg or "")).strip()
    parti = [
        nome_proprio(client) if str(client or "").isupper() else str(client or "").strip(),
        f"Fascicolo {numero_fascicolo}" if numero_fascicolo else "",
        f"RG {rg_pulito}" if rg_pulito and rg_pulito != numero_fascicolo else "",
        nome_proprio(ufficio) if str(ufficio or "").isupper() else str(ufficio or "").strip(),
    ]
    return " · ".join(dict.fromkeys(p for p in parti if p))


_SINTESI_STORICHE = (
    (r"^udienza revocata: note scritte entro il (.+)$", "udienza sostituita da note scritte (art. 127-ter c.p.c.), termine al {0}"),
    (r"^rinvio udienza al (.+)$", "rinvio dell'udienza al {0}"),
    (r"^udienza differita al (.+)$", "differimento dell'udienza al {0}"),
    (r"^udienza anticipata al (.+)$", "anticipazione dell'udienza al {0}"),
    (r"^udienza revocata(?: al (.+))?$", "revoca dell'udienza"),
    (r"^termine modificato al (.+)$", "modifica del termine al {0}"),
    (r"^termine fissato al (.+)$", "assegnazione del termine al {0}"),
    (r"^fissazione udienza al (.+)$", "fissazione dell'udienza del {0}"),
    (r"^sentenza n\. (.+)$", "deposito della sentenza n. {0}"),
    (r"^sentenza$", "deposito della sentenza"),
    (r"^estinzione del processo$", "dichiarazione di estinzione del giudizio"),
)
_RE_SUFFISSO_CAUSA = re.compile(r"\s+[–-]\s+(?:RG|R\.G\.)\s+\S+.*$")


def titolo_storico(titolo: str, descrizione: str = "") -> str:
    """I titoli scritti dalle versioni precedenti («PEC ricevuta: …») in linguaggio legale, solo per la lettura.

    Il dato salvato non cambia: RG e ufficio restano nella riga di contesto sotto il titolo, quindi si tolgono dal titolo.
    """
    testo = " ".join(str(titolo or "").split())
    if testo.lower().startswith("udienza da comunicazione di cancelleria"):
        return "Udienza"
    if testo.startswith("Comunicazione di cancelleria:"):
        return _RE_SUFFISSO_CAUSA.sub("", testo)
    if not testo.lower().startswith("pec ricevuta:"):
        return testo
    sintesi = _RE_SUFFISSO_CAUSA.sub("", testo[len("PEC ricevuta:"):].strip())
    for espressione, legale in _SINTESI_STORICHE:
        trovato = re.match(espressione, sintesi, re.I)
        if trovato:
            return f"Comunicazione di cancelleria: {legale.format(*(g or '' for g in trovato.groups()))}"
    giudice = re.match(r"^designazione del giudice (.+)$", sintesi, re.I)
    if giudice:
        return f"Comunicazione di cancelleria: designazione del giudice dott. {nome_proprio(giudice.group(1))}"
    parte = re.match(r"^costituzione di (.+)$", sintesi, re.I)
    if parte:
        return f"Comunicazione di cancelleria: costituzione in giudizio di {nome_proprio(parte.group(1))}"
    evento, _, dettaglio = sintesi.partition(":")
    # Le versioni precedenti troncavano il dettaglio a 60 caratteri: la descrizione completa resta nelle note.
    return f"Comunicazione di cancelleria: {evento_registro(evento, descrizione or dettaglio)}"


__all__ = ["EVENTI_REGISTRO", "MODALITA_UDIENZA", "evento_registro", "modalita_legale", "nome_proprio", "parole_del_registro", "riga_contesto", "titolo_cancelleria", "titolo_storico"]
