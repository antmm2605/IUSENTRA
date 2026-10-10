"""Magistrato del provvedimento, con identità congiunta della fonte.

Lavora sul testo del motore condiviso; non apre documenti e non scrive schede.
La firma laterale da sola non identifica il magistrato assegnatario.
"""
from __future__ import annotations

import re

from pct.pec_case_identity import document_case_identity_evidence, client_tax_code_from_documents
from pct.registro_letture.fatti_repository import Fatto

_NOME = r"[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý’'\-]+(?:[ \t]+[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý’'\-]+){1,4}"
_TITOLO = r"(?:dott(?:\.|or|ore|oressa)?(?:\s*\.\s*ssa)?|dr\.)"
_PATTERNS = (
    re.compile(r"\bIl\s+Giudice(?:\s+" + _TITOLO + r")?\s+(?P<nome>" + _NOME + r")(?=[,;\n]|\s+(?:letto|letta|ha|all[’']))"),
    re.compile(r"\bIl\s+Giudice\s+del\s+Lavoro\s+del\s+Tribunale\s+di\s+[^,\n]+,\s*" + _TITOLO + r"\s+(?P<nome>" + _NOME + r")(?=[,;\n])"),
    re.compile(r"\bin\s+(?:funzione|persona)\s+(?:di\s+giudice[^,\n]{0,80},\s*nella\s+persona\s+)?(?:del(?:la)?\s+)?" + _TITOLO + r"\s+(?P<nome>" + _NOME + r")(?=[,;\n])"),
)


def estrai_giudice(testo, *, fascicolo, origine="nativo", codice_fiscale_cliente=""):
    """Restituisce un fatto soltanto da un provvedimento pertinente verificabile."""
    if fascicolo is None:
        return []
    raw = str(testo or "")
    header = re.split(r"\b(?:motivazione|motivi\s+della\s+decisione|ragioni\s+della\s+decisione)\b", raw[:6000], maxsplit=1, flags=re.I)[0]
    if not re.search(r"(?im)^\s*(?:SENTENZA|DECRETO(?:\s+FISSAZIONE\s+UDIENZA)?|ORDINANZA|VERBALE)\b", header):
        return []
    identity = document_case_identity_evidence(raw, fascicolo)
    if not identity["complete_match"]:
        return []
    tax = client_tax_code_from_documents(
        {"cliente": fascicolo.nome_cliente}, [{"text": header, "filename": "provvedimento.pdf"}]
    )
    if tax.get("codice_fiscale_cliente_stato") in {"letto_non_valido", "fonti_discordanti"}:
        return []
    declared = tax.get("codice_fiscale_cliente", "")
    if declared and (not codice_fiscale_cliente or declared != codice_fiscale_cliente.strip().upper()):
        return []
    found = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(header):
            name = " ".join(match.group("nome").split())
            if name.casefold() not in {entry[0].casefold() for entry in found}:
                found.append((name, match))
    if len(found) != 1:
        return []
    name, match = found[0]
    native = origine == "nativo"
    proofs = [{"codice":"identita_congiunta_provvedimento", "esito":"ok", "dettaglio":identity},
              {"codice":"magistrato_intestazione", "esito":"ok", "dettaglio":match.group(0)}]
    # La decorrenza deve appartenere alla clausola di sostituzione, non a
    # un'udienza o alla data di caricamento del file.
    replacement = re.search(
        r"in\s+sostituzione\s+del(?:la)?\s+giudice\s+(?:" + _TITOLO + r"\s+)?"
        r"(?P<precedente>" + _NOME + r")[,;]?\s+con\s+decorrenza\s+dal\s+"
        r"(?P<data>\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", header,
    )
    if native and replacement:
        from legal_ocr.formulario.date import trova_date

        dates = trova_date(replacement.group("data"))
        if len(dates) == 1 and dates[0].sostituzioni == 0:
            proofs.append({"codice": "sostituzione_giudice", "esito": "ok", "dettaglio": {
                "precedente": " ".join(replacement.group("precedente").split()),
                "nuovo": name, "decorrenza": dates[0].data.isoformat(),
                "passaggio": replacement.group(0),
            }})
    return [Fatto(
        categoria="metadato_fascicolo", campo="giudice", valore=name,
        valore_letto=name, etichetta="Giudice del procedimento",
        contesto=header[max(0, match.start()-60):match.end()+100],
        posizione=match.start(), origine=origine, confidenza=1.0 if native else 0.7,
        verifica="verificata" if native else "plausibile",
        prove=proofs,
    )]
