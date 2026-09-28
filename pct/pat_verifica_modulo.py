"""Verifica del modulo PAT firmato, prima dell'invio.

Il modulo si firma in Adobe Reader sul suo campo firma (PAdES-BES), che prima esegue i controlli
bloccanti del modello; IUSENTRA non firma al posto dell'avvocato. Dopo la firma l'avvocato può caricare
il file e IUSENTRA controlla quello che le Istruzioni per la compilazione dei moduli di deposito
(v9.6.2, 18/07/2026) chiedono e che si può verificare sul file:

- versione del modulo uguale a quella pubblicata («un modulo di una versione precedente … potrebbe
  essere rifiutato»);
- firma PAdES presente, integra e sull'intero file (dopo la firma il modulo non si modifica più);
- certificato di firma non scaduto;
- nomi degli allegati incorporati composti solo da lettere, cifre, «_» e spazi;
- dimensioni: 10 MB per allegato e 30 MB per il modulo se l'invio è via PEC (30 e 50 MB via upload).
"""

from __future__ import annotations

import io
import re
from typing import Any

from pct.pat_anteprima import anteprima
from pct.pat_pdf_templates import PAT_PDF_TEMPLATES, read_compiled_template
from pct.pat_xfa_dati import valore

MB = 1024 * 1024
LIMITI = {"pec": {"allegato": 10 * MB, "modulo": 30 * MB}, "upload": {"allegato": 30 * MB, "modulo": 50 * MB}}
_NOME_ALLEGATO = re.compile(r"^[A-Za-z0-9_ ]+$")


def _esito(codice: str, livello: str, messaggio: str) -> dict[str, str]:
    return {"codice": codice, "livello": livello, "messaggio": messaggio}


def _intestazione(pdf: bytes) -> tuple[str, str]:
    radice = read_compiled_template(pdf)
    campi = {c.get("name"): valore(c) for c in radice.iter() if isinstance(c.tag, str) and c.tag.endswith("field")
             and c.get("name") in {"txtModuleName", "txtModuleVersion"}}
    return campi.get("txtModuleName", ""), campi.get("txtModuleVersion", "")


def _versione_pubblicata(codice: str) -> tuple[str, str]:
    for modulo_id, modello in PAT_PDF_TEMPLATES.items():
        if modello.official_code == codice:
            return modulo_id, _intestazione(modello.path.read_bytes())[1]
    return "", ""


def _firme(pdf: bytes) -> list[dict[str, Any]]:
    from datetime import datetime, timezone

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation.generic_cms import validate_sig_integrity

    firme = []
    for firma in PdfFileReader(io.BytesIO(pdf)).embedded_signatures:
        integra, valida = validate_sig_integrity(firma.signer_info, firma.signer_cert, expected_content_type="data",
                                                 actual_digest=firma.compute_digest())
        certificato = firma.signer_cert
        scadenza = certificato.not_valid_after
        copertura = firma.evaluate_signature_coverage()
        firme.append({
            "firmatario": certificato.subject.native.get("common_name") or certificato.subject.human_friendly,
            "integra": bool(integra and valida),
            "interoFile": copertura.name == "ENTIRE_FILE",
            "scaduto": scadenza < datetime.now(tz=timezone.utc),
            "campo": firma.field_name,
        })
    return firme


def _allegati(pdf: bytes) -> list[dict[str, Any]]:
    from pypdf import PdfReader

    elenco = []
    for nome, contenuti in (PdfReader(io.BytesIO(pdf)).attachments or {}).items():
        for contenuto in contenuti:
            elenco.append({"nome": nome, "byte": len(contenuto)})
    return elenco


def verifica(pdf: bytes, canale: str = "pec") -> dict[str, Any]:
    esiti: list[dict[str, str]] = []
    limiti = LIMITI.get(canale, LIMITI["pec"])
    if not pdf.startswith(b"%PDF"):
        return {"ok": False, "esiti": [_esito("NON_PDF", "errore", "Il file non è un PDF: carica il modulo firmato.")]}
    try:
        codice, versione = _intestazione(pdf)
    except Exception:
        return {"ok": False, "esiti": [_esito("NON_MODULO", "errore",
                                              "Il PDF non è un modulo di deposito PAT della Giustizia Amministrativa.")]}
    modulo_id, pubblicata = _versione_pubblicata(codice)
    if not modulo_id:
        esiti.append(_esito("MODULO_SCONOSCIUTO", "errore", f"Modulo «{codice or 'senza nome'}» non riconosciuto."))
    elif versione != pubblicata:
        esiti.append(_esito("VERSIONE", "errore", f"Modulo versione {versione or '?'}: quella pubblicata è la {pubblicata}. "
                            "Un modulo di una versione precedente può essere rifiutato: rigeneralo da IUSENTRA."))
    else:
        esiti.append(_esito("VERSIONE", "ok", f"Modulo {codice} versione {versione}, quella pubblicata."))

    firme = _firme(pdf)
    if not firme:
        esiti.append(_esito("FIRMA", "errore", "Il modulo non è firmato: firmalo in Adobe Reader sul campo firma in fondo al modulo."))
    for firma in firme:
        if not firma["integra"]:
            esiti.append(_esito("FIRMA", "errore", f"Firma di {firma['firmatario']} non integra: il file è stato alterato."))
        elif not firma["interoFile"]:
            esiti.append(_esito("FIRMA", "errore", "Il file è stato modificato dopo la firma: firma di nuovo scegliendo "
                                "«Blocca documento dopo la firma»."))
        else:
            esiti.append(_esito("FIRMA", "ok", f"Firma PAdES di {firma['firmatario']} integra sull'intero modulo."))
        if firma["scaduto"]:
            esiti.append(_esito("CERTIFICATO", "errore", "Il certificato di firma è scaduto."))

    allegati = _allegati(pdf)
    for allegato in allegati:
        radice = allegato["nome"].rsplit(".", 1)[0]
        if not _NOME_ALLEGATO.match(radice):
            esiti.append(_esito("NOME_ALLEGATO", "errore", f"«{allegato['nome']}»: nel nome solo lettere, cifre, «_» e spazi."))
        if allegato["byte"] > limiti["allegato"]:
            esiti.append(_esito("DIMENSIONE_ALLEGATO", "errore",
                                f"«{allegato['nome']}» supera {limiti['allegato'] // MB} MB ({canale})."))
    if len(pdf) > limiti["modulo"]:
        esiti.append(_esito("DIMENSIONE_MODULO", "errore", f"Il modulo supera {limiti['modulo'] // MB} MB ({canale})."))
    if not allegati:
        esiti.append(_esito("ALLEGATI", "avviso", "Nessun allegato incorporato: ricorso, procura e documenti si caricano "
                            "nel modulo con i pulsanti «Allega» prima della firma."))

    dati = anteprima(modulo_id, pdf) if modulo_id else None
    return {"ok": not any(e["livello"] == "errore" for e in esiti), "modulo": codice, "versione": versione,
            "firme": firme, "allegati": allegati, "esiti": esiti, "anteprima": dati}


__all__ = ["LIMITI", "verifica"]
