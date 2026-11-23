"""Domande di precisazione: quando un'impugnazione può essere civile o penale e il testo non dice quale, Lex non indovina.

Termini, giudice e forma dell'appello o del ricorso per cassazione cambiano del tutto fra processo civile (artt. 325, 327,
339 ss. e 360 ss. c.p.c.) e processo penale (artt. 585, 593 ss. e 606 ss. c.p.p.): una risposta sulla materia sbagliata
darebbe un termine sbagliato. Si chiede quindi di scegliere fra due domande complete, già pronte da rimandare.
"""
from __future__ import annotations

import re

from .norme import piano

# Si chiede solo per l'impugnazione di una sentenza (appello, cassazione, sentenza o condanna impugnata): l'impugnazione di
# atti amministrativi, rinunce o provvedimenti del giudice civile ha già la sua materia.
_IMPUGNAZIONE = r"\bappell|cassazione|\bimpugn\w*[^.?]{0,40}(?:sentenz|condann)|(?:sentenz|condann)[^.?]{0,80}\bimpugn"
_CIVILE = (r"civil|\battor|\bconvenut|citazion|c\.p\.c|giudice di pace|decreto ingiuntiv|\blavor|previdenz|tributar|\btar\b|"
           r"consiglio di stato|amministrativ|contratt|risarciment|condanna\w* (?:al|a) (?:pagare|pagamento|risarcire|rilasciare)|"
           r"sfratt|locazion|condomin|separazion|divorzi|precett|esecuzion|cartella|\beuro\b|€|caparra|credit|debit|fattur|"
           r"societ|eredit|testament|famiglia|figli|immobil|danni|assicura|consumator|banca|mutuo|tribunale civile|corte d appello civile|"
           # La sentenza «notificata» o «pubblicata» è il lessico dei termini civili (artt. 325 e 327 c.p.c.); nel processo
           # penale il termine decorre dal deposito o dalla lettura.
           r"sentenz\w*[^.?]{0,40}(?:notificat|pubblicat)|(?:notificat|pubblicat)\w*[^.?]{0,20}sentenz|"
           r"\bavvis|autotutela|accertament|\bimu\b|\btari\b|\biva\b|irpef|dopo la notifica|revocazion|opposizione di terzo|"
           r"regolamento di competenza|licenzia|dimission|protezione (?:internazionale|sussidiaria|speciale)|rifugiat|asilo|"
           r"permesso di soggiorno|espulsion|"
           r"verbale|sanzione amministrativ|ordinanza[- ]ingiunzion|delibera|lodo|provvediment\w* (?:amministrativ|del comune|della regione)")
_PENALE = (r"penal|imputat|\breat|pubblico ministero|\bpm\b|\bgip\b|\bgup\b|querel|c\.p\.p|\bpena\b|reclusion|\barrest|assolt|"
           r"assoluzion|patteggiament|parte civile|indagat|procura della repubblica|dibattiment|abbreviat|riesame|custodia|multa|"
           r"ammenda|furto|truffa|lesion|omicidi|rapina|spaccio|stupefacent|appropriazione|ricettazion|bancarotta|diffamazion|"
           r"corte d assise|tribunale di sorveglianza|esecuzione della pena|carcer|domiciliar|messa alla prova")


def materia_da_chiarire(domanda: str) -> list[str] | None:
    """Le due domande complete fra cui scegliere, se l'impugnazione non indica la materia; altrimenti None."""
    t = piano(domanda)
    # «Corte d'appello» che ha deciso non è una domanda di appello.
    # Si chiede quando la risposta cambia davvero fra i due processi: termini, motivi o redazione dell'impugnazione.
    if not re.search(r"entro|termin|quando|tempi|giorni|scade|prepar|redig|scriv|motiv|come (?:si |la |lo )?(?:propon|impugn)", t):
        return None
    if not re.search(_IMPUGNAZIONE, re.sub(r"(?:corte|sentenz\w*|giudizio|grado|giudice) d ?appello", "", t)) or re.search(_CIVILE, t) or re.search(_PENALE, t):
        return None
    base = domanda.strip()
    return [f"{base} (procedimento civile)", f"{base} (procedimento penale)"]


def testo_chiarimento(scelte: list[str]) -> str:
    return ("**Serve una precisazione**\n"
            "- La domanda riguarda un'impugnazione, ma non dice se il procedimento è civile o penale. Termini, giudice e "
            "forma cambiano del tutto fra i due processi: per non darti un termine sbagliato, ti chiedo di scegliere.\n\n"
            "**Scegli una delle due domande e rimandala**\n"
            f"1. {scelte[0]}\n"
            f"2. {scelte[1]}")


def testo_chiarimento_lato(scelte: list[str]) -> str:
    return ("**Serve una precisazione**\n"
            "- Lo stesso atto apre strade opposte secondo la parte che assisti: chi agisce ha i suoi passi e i suoi termini, "
            "chi lo subisce ha le opposizioni con termini diversi e spesso brevi. Per non darti lo strumento dell'altra "
            "parte, ti chiedo chi assisti.\n\n"
            "**Scegli una delle due domande e rimandala**\n"
            f"1. {scelte[0]}\n"
            f"2. {scelte[1]}")


def testo_chiarimento_strumento(scelte: list[str], nomi: list[str]) -> str:
    righe = "\n".join(f"{k}. {s}" for k, s in enumerate(scelte, 1))
    return ("**Serve una precisazione**\n"
            "- Dai fatti descritti non riconosco con certezza lo strumento. I più vicini sono: " + "; ".join(nomi) + ". "
            "Scegli quello che ti serve: rispondo con le norme vigenti di quello strumento.\n\n"
            "**Scegli una delle domande e rimandala**\n" + righe)


def testo_fuori_materia() -> str:
    return ("**Serve una precisazione**\n"
            "- La richiesta riguarda il diritto, ma non riconosco né la fattispecie né uno strumento vicino fra quelli che le "
            "regole di Lex sanno trattare con le norme vigenti. Per non indovinare, ti chiedo di indicare i fatti essenziali: "
            "chi assisti, che cosa è successo o quale atto hai ricevuto, e che cosa vuoi ottenere.\n"
            "- Se la questione è fuori dalle materie delle regole (per esempio una consulenza fiscale di pianificazione o una "
            "questione di diritto straniero), Lex non la tratta: va esaminata dall'avvocato.")
