"""Workflow deposito telematico — checklist PST/PDP/PAT/PTT e diagnosi errori."""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = (
    "Sei Lex, il modulo deposito telematico di IUSENTRA.\n\n"
    "REGOLE ASSOLUTE:\n"
    "• Rispondi SEMPRE e SOLO in italiano.\n"
    "• Fornisci checklist operative, diagnosi errori e percorsi di correzione concreti.\n"
    "• Non aggiungere 'consulta il sito del tribunale' o 'contatta l'assistenza': dai il percorso diretto.\n"
    "• Distingui chiaramente PST/polisWeb (civile), PDP (penale) e PAT (amministrativo).\n"
    "• Non inventare stati o errori: se non riconosci l'errore, chiedilo con precisione.\n"
    "• Struttura: Portale → Checklist → Diagnosi errore (se presente) → Prossima azione.\n"
    "• Non usare disclaimer generici.\n"
    "• Tono operativo, diretto, professionale.\n"
)

_ERRORI_COMUNI_PST: dict[str, str] = {
    "errore firma": (
        "Verificare che la firma sia CAdES-BES (.p7m), non PAdES. "
        "Il certificato deve essere valido (non scaduto). "
        "Controllare che il file firmato abbia estensione .pdf.p7m."
    ),
    "errore datiatto": (
        "Controllare il namespace XML in DatiAtto.xml: deve essere corretto. "
        "Il tag dell'atto principale deve essere <Attoprincipale> (con A minuscola finale). "
        "Verificare hash SHA-256 di ciascun documento."
    ),
    "busta non accettata": (
        "Verificare oggetto PEC: deve iniziare con 'DEPOSITO TELEMATICO'. "
        "Controllare PEC del tribunale su ReGINde (giustiziapec.it). "
        "Verificare che la busta .enc contenga DatiAtto.xml + atti firmati."
    ),
    "pdf non conforme": (
        "Il PDF deve essere PDF/A-1b. "
        "Convertire con LibreOffice, Acrobat o strumenti online certificati. "
        "Evitare PDF protetti da password o con font non incorporati."
    ),
    "errore hash": (
        "Ricalcolare il hash SHA-256 per ogni documento e aggiornare DatiAtto.xml. "
        "Il hash deve corrispondere esattamente al file firmato."
    ),
}

_ERRORI_COMUNI_PDP: dict[str, str] = {
    "errore autenticazione": (
        "Verificare certificato mTLS (P12/PEM): deve essere valido e corrispondere alla CA del Ministero. "
        "Controllare URL endpoint: https://appweb.giustizia.it"
    ),
    "errore multipart": (
        "La richiesta deve essere multipart/form-data con campo 'atto'. "
        "I metadati vanno nel JSON allegato, non nel campo principale."
    ),
    "codice esito errore": (
        "Verificare il codiceEsito nella risposta JSON. "
        "Controllare log PDP per il codice specifico e il messaggio di errore."
    ),
}

_ERRORI_COMUNI_PAT: dict[str, str] = {
    "errore wsdl": (
        "Verificare WSDL SIGA: depositoAtto su giustizia-amministrativa.it/pac. "
        "Controllare certificato mTLS e endpoint corretto."
    ),
    "atto non in base64": (
        "L'atto nel payload SOAP deve essere codificato in base64. "
        "Verificare encoding prima dell'invio."
    ),
    "termine scaduto": (
        "Il ricorso al TAR ha termine di 60 giorni dalla notifica (art. 29 D.Lgs. 104/2010). "
        "Verificare la data di notifica del provvedimento impugnato."
    ),
}


def diagnosi_errore(messaggio_errore: str, portale: str = "PST") -> str:
    """Tenta di diagnosticare un errore telematico dal messaggio."""
    msg = str(messaggio_errore or "").lower()
    portale_upper = str(portale or "PST").strip().upper()

    errori_map = {
        "PST": _ERRORI_COMUNI_PST,
        "POLISWEB": _ERRORI_COMUNI_PST,
        "PDP": _ERRORI_COMUNI_PDP,
        "PAT": _ERRORI_COMUNI_PAT,
    }.get(portale_upper, _ERRORI_COMUNI_PST)

    for chiave, soluzione in errori_map.items():
        if any(token in msg for token in chiave.split()):
            return f"**Diagnosi {portale_upper} — {chiave}:**\n{soluzione}"

    return (
        f"Errore non riconosciuto automaticamente per {portale_upper}.\n"
        f"Messaggio ricevuto: `{messaggio_errore}`\n\n"
        "Per una diagnosi precisa, indica:\n"
        "1. Portale usato (PST/PDP/PAT)\n"
        "2. Fase in cui è avvenuto l'errore (firma, invio PEC, risposta portale)\n"
        "3. Codice errore esatto se disponibile"
    )


def checklist_portale(portale: str = "PST") -> str:
    """Ritorna checklist testuale in italiano per il portale."""
    portale_upper = str(portale or "PST").strip().upper()

    checklists: dict[str, list[str]] = {
        "PST": [
            "☐ PDF/A-1b per tutti gli atti (verificare con strumento di validazione)",
            "☐ Firma CAdES-BES (.p7m) sull'atto principale",
            "☐ DatiAtto.xml con namespace corretto e tag <Attoprincipale>",
            "☐ Hash SHA-256 di ciascun documento nel DatiAtto.xml",
            "☐ Busta .enc = ZIP contenente DatiAtto.xml + atti firmati",
            "☐ Oggetto PEC: 'DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}'",
            "☐ PEC tribunale da ReGINde (giustiziapec.it)",
            "☐ Certificato firma non scaduto",
        ],
        "PDP": [
            "☐ Endpoint: https://appweb.giustizia.it/depositi",
            "☐ Autenticazione mTLS (certificato P12/PEM valido)",
            "☐ Richiesta multipart/form-data con campo 'atto' e metadati JSON",
            "☐ Firma CAdES o PAdES sull'atto penale",
            "☐ Certificato CNS/CIE non scaduto",
            "☐ Polling ricevuta PEC accettazione e consegna (max 5 min)",
            "☐ Verifica codiceEsito nella risposta JSON",
        ],
        "PAT": [
            "☐ WSDL: depositoAtto su giustizia-amministrativa.it/pac",
            "☐ Atto codificato in base64 nel payload SOAP",
            "☐ Autenticazione mTLS (certificato P12/PEM)",
            "☐ PDF/A-1b per ogni allegato",
            "☐ Firma CAdES o PAdES sull'atto amministrativo",
            "☐ Verifica termine ricorso TAR (60 gg dalla notifica, art. 29 D.Lgs. 104/2010)",
            "☐ Verifica risposta SOAP con codice accettazione segreteria",
        ],
        "PTT": [
            "☐ Accesso con CNS/CIE/SPID al portale PTT",
            "☐ Firma digitale qualificata obbligatoria",
            "☐ Verifica dati fascicolo telematico prima dell'invio",
            "☐ Allegare tutti i documenti nella sequenza corretta",
        ],
    }

    items = checklists.get(portale_upper, checklists["PST"])
    normativa = {
        "PST": "D.M. 44/2011",
        "POLISWEB": "D.M. 44/2011",
        "PDP": "D.Lgs. 150/2022 + D.M. 217/2023",
        "PAT": "D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021",
        "PTT": "D.M. 44/2011",
    }.get(portale_upper, "D.M. 44/2011")

    lines = [f"**Checklist deposito {portale_upper}** ({normativa})\n"]
    lines.extend(items)
    return "\n".join(lines)


class DepositoTelematicoWorkflow:
    workflow_name = "deposito_telematico"
    system_prompt = SYSTEM_PROMPT
