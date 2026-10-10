"""Date nominate della fonte: riusa il calendario e l'identità condivisi."""
from __future__ import annotations

import re

from legal_ocr.formulario.date import trova_date
from pct.pec_case_identity import document_case_identity_evidence, client_tax_code_from_documents
from pct.registro_letture.fatti_repository import Fatto

VERSIONE_DATE_CAMPI_MODELLI = '2026.10.10.date-campi-modello.v3'

CAMPI_DATE = {
    "data_deposito_ricorso": "Data di deposito del ricorso",
    "data_emissione_decreto": "Data di emissione del decreto",
    "data_pronuncia_sentenza": "Data di pronuncia della sentenza",
}
_ANCORE = {
    "data_deposito_ricorso": r"\bricorso\s+(?:telematico\s+)?depositato\s+(?:telematicamente\s+)?(?:in\s+data|il|in\s+cancelleria\s+il)\s*$",
    "data_emissione_decreto": r"\bdecreto\s+(?:(?:di\s+)?fissazione\s+(?:dell[’']|della\s+)?udienza[\s,]+)?(?:emesso\s+(?:dal\s+[^;\n]{1,100}\s+)?)?(?:in\s+data|del)\s*$",
    "data_pronuncia_sentenza": r"\bsentenza\s+(?:pronunciata|emessa)\s+(?:in\s+data|il)\s*$",
}


def estrai_date_modello(testo, *, fascicolo, origine="nativo", codice_fiscale_cliente=""):
    """Non deduce date da upload, termini futuri, citazioni o bozza dell'editor."""
    if fascicolo is None:
        return []
    raw = str(testo or "")
    identity = document_case_identity_evidence(raw, fascicolo)
    if not identity["complete_match"]:
        return []
    tax = client_tax_code_from_documents(
        {"cliente": fascicolo.nome_cliente}, [{"text": raw[:6000], "filename": "provvedimento.pdf"}]
    )
    if tax.get("codice_fiscale_cliente_stato") in {"letto_non_valido", "fonti_discordanti"}:
        return []
    declared = tax.get("codice_fiscale_cliente", "")
    if declared and declared != codice_fiscale_cliente.strip().upper():
        return []
    # La fonte deve essere un provvedimento del procedimento, non un modello
    # dell'avvocato che ne ripete una data ancora da verificare.
    attestation = bool(
        re.search(r"(?im)^\s*ATTESTAZIONE\s+DI\s+CONFORMIT[ÀA]\b", raw[:1000])
        and re.search(r"sono\s+conformi\s+alle\s+copie\s+informatiche\s+presenti\s+nel\s+fascicolo\s+informatico", raw, re.I)
    )
    if not attestation and not re.search(r"(?im)^\s*(?:SENTENZA|DECRETO|ORDINANZA|VERBALE)\b", raw[:6000]):
        return []
    result = []
    for token in trova_date(raw):
        if token.sostituzioni:
            continue
        before = raw[max(0, token.inizio - 150):token.inizio]
        for field, pattern in _ANCORE.items():
            match = re.search(pattern, before, re.I)
            if match is None:
                continue
            passage = before[match.start():] + token.letto
            result.append(Fatto(
                categoria="metadato_fascicolo", campo=field,
                valore=token.data.isoformat(), valore_letto=token.letto,
                etichetta=CAMPI_DATE[field], contesto=passage,
                posizione=token.inizio, origine=origine, confidenza=1.0 if origine == "nativo" else 0.7,
                verifica="verificata" if origine == "nativo" else "plausibile", prove=[
                    {"codice": "identita_congiunta_provvedimento", "esito": "ok", "dettaglio": identity},
                    {"codice": "data_processuale_nominata", "esito": "ok", "dettaglio": passage},
                    *([{"codice": "attestazione_copie_fascicolo_informatico", "esito": "ok", "dettaglio": "Identità congiunta verificata nella stessa attestazione."}] if attestation else []),
                ],
            ))
    return result
