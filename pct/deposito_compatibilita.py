"""Report di compatibilità per la prova deposito senza invio PEC reale."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from pct.atto_enc_validation import inspect_atto_enc_payload
from pct.path_security import UnsafeRuntimePath, resolve_runtime_path


REFERENCE_SAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "tribunale_palmi_accettazione_deposito",
        "label": "Campione Tribunale Palmi - accettazione deposito telematico",
        "scope": "deposito_pct",
        "office": "tribunale",
        "subject_tokens": ("POSTA CERTIFICATA", "ACCETTAZIONE DEPOSITO TELEMATICO", "RG:", "RefID"),
        "receipt_artifacts": ("postacert.eml", "daticert.xml", "EsitoAtto.xml", "smime.p7s"),
        "body_tokens": ("Codice esito", "IDBUSTA", "Accettazione manuale avvenuta con successo"),
    },
    {
        "id": "gdp_palmi_notificazione_cancelleria",
        "label": "Campione Giudice di Pace Palmi - notifica di cancelleria",
        "scope": "ricezione_ptel_gdp",
        "office": "gdp",
        "subject_tokens": ("POSTA CERTIFICATA", "GIUDICE DI PACE", "D.L. 179/2012"),
        "receipt_artifacts": ("postacert.eml", "daticert.xml", "IndiceBusta.xml", "Comunicazione.xml"),
        "body_tokens": ("Numero di Ruolo generale", "CodiceUG", "relazione di notificazione"),
    },
)


RECEIPT_PLAN: tuple[dict[str, Any], ...] = (
    {
        "id": "accettazione",
        "label": "Ricevuta di accettazione PEC",
        "artifacts": ("postacert.eml", "daticert.xml", "smime.p7s"),
        "reference": "Campione Tribunale Palmi",
    },
    {
        "id": "rdac",
        "label": "RdAC / avvenuta consegna",
        "artifacts": ("postacert.eml", "daticert.xml", "smime.p7s"),
        "reference": "Schema PEC certificata osservato nei campioni",
    },
    {
        "id": "controlli",
        "label": "Esito controlli automatici",
        "artifacts": ("postacert.eml", "daticert.xml", "EsitoAtto.xml", "smime.p7s"),
        "reference": "Campione Tribunale Palmi",
    },
    {
        "id": "cancelleria",
        "label": "Esito cancelleria",
        "artifacts": ("postacert.eml", "daticert.xml", "EsitoAtto.xml", "smime.p7s"),
        "reference": "Campione Tribunale Palmi",
    },
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _casefold(value: Any) -> str:
    return _clean(value).casefold()


def _has_token(text: str, token: str) -> bool:
    return token.casefold() in text.casefold()


def _file_info(path_value: str) -> dict[str, Any]:
    if not path_value:
        return {"exists": False, "name": "", "size_bytes": 0, "sha256": ""}
    try:
        path = resolve_runtime_path(path_value, extra_roots=(tempfile.gettempdir(), Path.cwd())).resolve()
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath):
        return {"exists": False, "name": Path(str(path_value)).name, "size_bytes": 0, "sha256": ""}
    if not path.is_file():
        return {"exists": False, "name": path.name, "size_bytes": 0, "sha256": ""}
    payload = path.read_bytes()
    cms_info = inspect_atto_enc_payload(payload) if path.name.lower() == "atto.enc" else {"valid": False}
    return {
        "exists": True,
        "name": path.name,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "cms_enveloped_data": cms_info.get("valid") is True,
        "cms_content_type": cms_info.get("content_type", ""),
        "cms_encryption_algorithm": cms_info.get("encryption_algorithm", ""),
        "cms_encryption_algorithm_oid": cms_info.get("encryption_algorithm_oid", ""),
    }


def _check(
    checks: list[dict[str, Any]],
    *,
    code: str,
    label: str,
    ok: bool,
    weight: int,
    detail: str,
    warning: bool = False,
    evidence: str = "",
) -> None:
    status = "ok" if ok else "warning" if warning else "blocco"
    score = weight if ok else max(1, weight // 2) if warning else 0
    checks.append(
        {
            "code": code,
            "label": label,
            "status": status,
            "weight": weight,
            "score": score,
            "detail": detail,
            "evidence": evidence,
        }
    )


def build_deposito_compatibility_report(
    *,
    id_deposito: str,
    pec_dest: str,
    oggetto_pec: str,
    corpo_pec: str,
    documenti_busta: list[str] | tuple[str, ...],
    attachment_path: str,
    busta_audit: dict[str, Any] | None,
    validation: Any,
    codice_ufficio: str = "",
    ufficio_nome: str = "",
    tipo_atto: str = "",
    numero_rg: str | None = None,
    anno_rg: int | str | None = None,
    simulazione_senza_invio: bool = True,
) -> dict[str, Any]:
    """Confronta il pacchetto generato con i campioni PEC reali allegati dall'utente.

    Il report non certifica un invio PEC: misura se la prova ha prodotto gli
    stessi artefatti strutturali richiesti per il deposito e per il presidio
    delle ricevute successive.
    """

    audit = dict(busta_audit or {})
    docs = [_clean(item) for item in documenti_busta if _clean(item)]
    docs_text = " ".join(docs)
    body = _clean(corpo_pec)
    subject = _clean(oggetto_pec)
    pec = _clean(pec_dest)
    file_info = _file_info(attachment_path)
    checks: list[dict[str, Any]] = []
    has_indice_busta = any(item.casefold() == "indicebusta.xml" for item in docs)
    has_datiatto_signed = any(item.casefold() == "datiatto.xml.p7m" for item in docs)
    audit_indice_busta = audit.get("indice_busta_xml_generated", audit.get("indice_busta_generated")) is True
    audit_datiatto_signed = audit.get("dati_atto_signed") is True

    real_enc = (
        audit.get("uses_real_encryption") is True
        and str(audit.get("required_encryption_algorithm") or "").upper() == "AES256"
        and "AES256" in str(audit.get("transport_mode") or "").upper()
        and audit_indice_busta
        and audit_datiatto_signed
        and file_info["exists"]
        and file_info["name"] == "Atto.enc"
        and file_info.get("cms_enveloped_data") is True
    )
    _check(
        checks,
        code="ATTO_ENC_AES256",
        label="Atto.enc ministeriale AES256",
        ok=real_enc,
        weight=18,
        detail=(
            "Atto.msg cifrato in Atto.enc con algoritmo AES256 e certificato PST."
            if real_enc
            else "Atto.enc AES256 non risulta generato, collegato o riconoscibile come CMS ministeriale."
        ),
        evidence=str(audit.get("content_encryption_algorithm") or file_info.get("cms_encryption_algorithm") or audit.get("transport_mode") or ""),
    )

    has_datiatto = has_datiatto_signed
    _check(
        checks,
        code="DATI_ATTO_XML_P7M",
        label="DatiAtto.xml.p7m firmato",
        ok=has_datiatto and has_datiatto_signed and audit_datiatto_signed,
        weight=10,
        detail="DatiAtto.xml è incluso nella busta." if has_datiatto else "DatiAtto.xml non compare tra i documenti busta.",
    )

    _check(
        checks,
        code="INDICE_BUSTA_XML",
        label="IndiceBusta.xml ministeriale",
        ok=has_indice_busta and audit_indice_busta,
        weight=12,
        detail=(
            "IndiceBusta.xml ministeriale generato e incluso in Atto.msg."
            if has_indice_busta and audit_indice_busta
            else "IndiceBusta.xml ministeriale non risulta incluso: il PST può rifiutare la busta."
        ),
    )

    has_index = any(item.casefold() == "indicedocumentidepositati.pdf" for item in docs)
    audit_index = audit.get("indice_documenti_generated") is not False
    _check(
        checks,
        code="INDICE_DOCUMENTI",
        label="IndiceDocumentiDepositati.PDF",
        ok=has_index and audit_index,
        weight=10,
        detail=(
            "Indice documenti depositati generato e incluso."
            if has_index and audit_index
            else "Indice documenti depositati non risulta completo nel pacchetto."
        ),
    )

    operational_docs = [
        item
        for item in docs
        if item.casefold() not in {"datiatto.xml", "datiatto.xml.p7m", "indicebusta.xml", "indicedocumentidepositati.pdf"}
    ]
    _check(
        checks,
        code="DOCUMENTI_SELEZIONATI",
        label="Atto principale e allegati controllati",
        ok=bool(operational_docs),
        weight=8,
        detail=(
            f"{len(operational_docs)} documenti operativi indicati nella busta."
            if operational_docs
            else "Nessun atto principale/allegato operativo indicato nella busta."
        ),
        evidence=", ".join(operational_docs[:5]),
    )

    pec_ok = "@" in pec and ("giustiziacert.it" in pec.casefold() or "ptel" in pec.casefold())
    _check(
        checks,
        code="PEC_UFFICIO",
        label="PEC ufficio giudiziario",
        ok=pec_ok,
        weight=8,
        detail=(
            "Destinatario PEC ministeriale valorizzato."
            if pec_ok
            else "Destinatario PEC non riconoscibile come casella ministeriale del deposito."
        ),
        evidence=pec,
    )

    rg_ok = not (numero_rg and anno_rg) or f"{numero_rg}/{anno_rg}" in subject or (str(numero_rg) in subject and str(anno_rg) in subject)
    subject_ok = _has_token(subject, "DEPOSITO TELEMATICO") and rg_ok
    _check(
        checks,
        code="OGGETTO_PEC",
        label="Oggetto PEC deposito",
        ok=subject_ok,
        weight=8,
        detail=(
            "Oggetto compatibile con deposito telematico e riferimento RG."
            if subject_ok
            else "Oggetto PEC non contiene tutti i riferimenti minimi attesi per il deposito."
        ),
        evidence=subject,
    )

    body_reference_docs = operational_docs
    body_folded = _casefold(body)
    body_ok = _has_token(body, "Atto.enc") and bool(body_reference_docs) and all(item.casefold() in body_folded for item in body_reference_docs)
    _check(
        checks,
        code="CORPO_PEC",
        label="Corpo PEC verificabile",
        ok=body_ok,
        weight=8,
        detail=(
            "Il testo PEC richiama Atto.enc e i documenti contenuti."
            if body_ok
            else "Il testo PEC non documenta chiaramente Atto.enc e l'elenco dei documenti."
        ),
    )

    no_send_ok = bool(simulazione_senza_invio)
    _check(
        checks,
        code="NESSUN_INVIO_REALE",
        label="Simulazione senza invio SMTP",
        ok=no_send_ok,
        weight=8,
        detail=(
            "Il controllo è stato eseguito senza invio PEC reale; l'invio resta demandato al PC locale."
            if no_send_ok
            else "Il percorso non è marcato come prova senza invio reale."
        ),
    )

    receipt_ok = bool(RECEIPT_PLAN)
    _check(
        checks,
        code="PRESIDIO_RICEVUTE",
        label="Presidio ricevute successive",
        ok=receipt_ok,
        weight=12,
        detail="Sono presidiate accettazione, RdAC, controlli automatici ed esito cancelleria.",
        evidence=", ".join(item["label"] for item in RECEIPT_PLAN),
    )

    reference_tokens = set()
    reference_artifacts = set()
    for sample in REFERENCE_SAMPLES:
        reference_tokens.update(str(item) for item in sample.get("subject_tokens", ()))
        reference_artifacts.update(str(item) for item in sample.get("receipt_artifacts", ()))
    sample_ok = _has_token(subject, "DEPOSITO TELEMATICO") and {"postacert.eml", "daticert.xml", "EsitoAtto.xml"}.issubset(reference_artifacts)
    _check(
        checks,
        code="CONFRONTO_CAMPIONI",
        label="Confronto con campioni allegati",
        ok=sample_ok,
        weight=10,
        detail=(
            "Il pacchetto e il presidio ricevute corrispondono alla struttura dei campioni reali allegati."
            if sample_ok
            else "La struttura non raggiunge ancora il confronto minimo con i campioni allegati."
        ),
        evidence=", ".join(sorted(reference_artifacts)),
    )

    total_weight = sum(int(item["weight"]) for item in checks) or 1
    score = sum(int(item["score"]) for item in checks)
    percentage = round(score * 100 / total_weight)
    blockers = [item for item in checks if item["status"] == "blocco"]
    warnings = [item for item in checks if item["status"] == "warning"]

    return {
        "id": id_deposito,
        "percentuale": percentage,
        "status": "conforme" if percentage == 100 and not blockers else "da_completare" if blockers else "compatibile_con_avvisi",
        "summary": (
            f"Compatibilità {percentage}% con i campioni PEC reali allegati. "
            "Nessun invio PEC reale è stato eseguito."
        ),
        "checks": checks,
        "blockers": len(blockers),
        "warnings": len(warnings),
        "atto_enc": file_info,
        "pec": {
            "destinatario": pec,
            "oggetto": subject,
            "corpo_contiene_atto_enc": _has_token(body, "Atto.enc"),
        },
        "fascicolo": {
            "codice_ufficio": _clean(codice_ufficio),
            "ufficio": _clean(ufficio_nome),
            "tipo_atto": _clean(tipo_atto),
            "rg": f"{numero_rg}/{anno_rg}" if numero_rg and anno_rg else "",
            "documenti": docs,
        },
        "campioni_usati": [
            {
                "id": sample["id"],
                "label": sample["label"],
                "scope": sample["scope"],
                "artefatti": list(sample["receipt_artifacts"]),
            }
            for sample in REFERENCE_SAMPLES
        ],
        "ricevute_attese": [
            {
                "id": item["id"],
                "label": item["label"],
                "artefatti": list(item["artifacts"]),
                "reference": item["reference"],
                "status": "da_presidiare",
            }
            for item in RECEIPT_PLAN
        ],
        "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation,
    }
