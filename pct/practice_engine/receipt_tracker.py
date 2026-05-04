"""Import guidato di ricevute ed esiti ufficiali."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import zipfile

from .messages import DEPOSIT_ACQUIRED, DEPOSIT_SENT_NOT_ACQUIRED, problem_action
from .models import DepositReceipt, DepositStatus, ReceiptType, new_id, utc_now
from .repository import PracticeEngineRepository
from .state_machine import has_final_positive_receipt


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guess_type(payload: dict[str, Any], name: str = "") -> str:
    raw = " ".join([str(payload.get("receipt_type") or payload.get("tipo") or ""), name]).upper()
    if "ACCETTAZ" in raw:
        return ReceiptType.ACCETTAZIONE_PEC.value
    if "CONSEG" in raw:
        return ReceiptType.CONSEGNA_PEC.value
    if "CONTROL" in raw:
        return ReceiptType.CONTROLLI_AUTOMATICI.value
    if "CANCELL" in raw:
        return ReceiptType.ESITO_CANCELLERIA.value
    if "PDP" in raw:
        return ReceiptType.ESITO_PDP.value
    if "PAT" in raw:
        return ReceiptType.ESITO_PAT.value
    if "PTT" in raw or "SIGIT" in raw:
        return ReceiptType.ESITO_PTT.value
    if "SIGP" in raw or "GDP" in raw:
        return ReceiptType.ESITO_SIGP.value
    if "PORTALE" in raw:
        return ReceiptType.ESITO_PORTALE.value
    return ReceiptType.ALTRO.value


def _positive(payload: dict[str, Any]) -> bool:
    raw = str(payload.get("status") or payload.get("esito") or payload.get("result") or "").lower()
    if isinstance(payload.get("positive"), bool):
        return bool(payload["positive"])
    return any(token in raw for token in ("ok", "positivo", "accettato", "acquisito", "success"))


def _status_for_receipt(receipt_type: str, positive: bool) -> str:
    if receipt_type == ReceiptType.ACCETTAZIONE_PEC.value:
        return DepositStatus.ACCETTATO_PEC.value
    if receipt_type == ReceiptType.CONSEGNA_PEC.value:
        return DepositStatus.CONSEGNATO.value
    if receipt_type == ReceiptType.CONTROLLI_AUTOMATICI.value:
        return DepositStatus.CONTROLLI_OK.value if positive else DepositStatus.CONTROLLI_ERRORE.value
    if receipt_type in {
        ReceiptType.ESITO_CANCELLERIA.value,
        ReceiptType.ESITO_PDP.value,
        ReceiptType.ESITO_PAT.value,
        ReceiptType.ESITO_PTT.value,
        ReceiptType.ESITO_SIGP.value,
        ReceiptType.ESITO_PORTALE.value,
    }:
        return DepositStatus.ACQUISITO.value if positive else DepositStatus.RIFIUTATO_CANCELLERIA.value
    return DepositStatus.INVIATO.value


def import_receipt(
    repository: PracticeEngineRepository,
    *,
    deposito_id: str,
    fascicolo_id: str,
    channel: str,
    payload: dict[str, Any] | None = None,
    original_bytes: bytes | None = None,
    original_name: str = "ricevuta.json",
    source: str = "import_guidato",
) -> dict[str, Any]:
    payload = dict(payload or {})
    if original_bytes is None:
        original_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    receipt_type = str(payload.get("receipt_type") or _guess_type(payload, original_name))
    positive = _positive(payload)
    status = _status_for_receipt(receipt_type, positive)
    receipt_id = new_id("rcp")
    target_dir = repository.receipts_dir / str(fascicolo_id) / str(deposito_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name or "ricevuta.json").name
    target = target_dir / f"{receipt_id}_{safe_name}"
    target.write_bytes(original_bytes)
    receipt = DepositReceipt(
        id=receipt_id,
        deposit_session_id=deposito_id,
        fascicolo_id=fascicolo_id,
        receipt_type=receipt_type,
        status=status,
        positive=positive,
        source=source,
        original_name=safe_name,
        original_hash_sha256=_sha256(original_bytes),
        original_path=str(target),
        payload=payload,
        message=str(payload.get("message") or payload.get("messaggio") or "Ricevuta importata."),
    )
    repository.add_receipt(receipt)
    session = repository.get_deposit_session(deposito_id)
    if session:
        receipts = repository.list_receipts(deposito_id)
        if has_final_positive_receipt(channel, receipts):
            session.status = DepositStatus.ACQUISITO.value
            session.acquired_at = utc_now()
            session.final_receipt_id = receipt.id
            session.messages = [DEPOSIT_ACQUIRED]
            repository.record_state(fascicolo_id, "ACQUISITO", reason="Esito finale positivo importato.", payload={"receipt_id": receipt.id})
        elif status == DepositStatus.RIFIUTATO_CANCELLERIA.value:
            session.status = DepositStatus.RIFIUTATO_CANCELLERIA.value
            session.messages = [problem_action("Deposito rifiutato dal canale ufficiale", "Analizza l'esito e prepara la correzione")]
            repository.record_state(fascicolo_id, "DA_CORREGGERE", reason="Esito finale negativo importato.", payload={"receipt_id": receipt.id})
        else:
            session.status = status
            session.messages = [DEPOSIT_SENT_NOT_ACQUIRED if status in {DepositStatus.ACCETTATO_PEC.value, DepositStatus.CONSEGNATO.value, DepositStatus.CONTROLLI_OK.value} else receipt.message]
        repository.update_deposit_session(session)
    repository.audit(fascicolo_id, "RECEIPT_IMPORTED", message=f"Ricevuta {receipt_type} importata.", payload={"receipt_id": receipt.id, "deposito_id": deposito_id})
    return {"receipt": receipt, "session": repository.get_deposit_session(deposito_id)}


def parse_receipt_upload(path: str) -> list[tuple[dict[str, Any], bytes, str]]:
    file_path = Path(path)
    if file_path.is_dir():
        rows = []
        for child in sorted(file_path.iterdir()):
            if child.is_file():
                rows.extend(parse_receipt_upload(str(child)))
        return rows
    data = file_path.read_bytes()
    suffix = file_path.suffix.lower()
    if suffix == ".zip":
        rows = []
        with zipfile.ZipFile(file_path) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                content = zf.read(name)
                rows.append((_payload_from_bytes(content, name), content, Path(name).name))
        return rows
    return [(_payload_from_bytes(data, file_path.name), data, file_path.name)]


def _payload_from_bytes(data: bytes, name: str) -> dict[str, Any]:
    if name.lower().endswith(".json"):
        try:
            raw = json.loads(data.decode("utf-8"))
            return raw if isinstance(raw, dict) else {"items": raw}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"receipt_type": _guess_type({}, name), "message": "JSON ricevuta non leggibile integralmente."}
    text = data[:4096].decode("utf-8", errors="ignore")
    return {"receipt_type": _guess_type({}, name), "message": text[:500], "original_format": Path(name).suffix.lower().lstrip(".")}
