"""Esegue un dry-run server del deposito senza invio PEC reale.

Lo script usa HTTP(S) contro l'ambiente indicato, legge il payload React del
fascicolo, costruisce la stessa proposta documentale della UI e chiama la route
reale di generazione busta. Non chiama mai le route di invio PEC.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import ssl
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


INDICE_DOCUMENTI_FILENAME = "IndiceDocumentiDepositati.PDF"


@dataclass(frozen=True)
class ServerResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", _text(value).lower()).strip()


def _doc_text(doc: dict[str, Any]) -> str:
    tags = " ".join(_text(item) for item in doc.get("tags") or [])
    return _norm(
        " ".join(
            [
                _text(doc.get("type")),
                _text(doc.get("name")),
                _text(doc.get("statusLabel")),
                _text(doc.get("portalClass")),
                _text(doc.get("portalName")),
                _text(doc.get("portalSender")),
                _text(tags),
            ]
        )
    )


def _record_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _is_portal_acquired(doc: dict[str, Any]) -> bool:
    text = _doc_text(doc)
    return bool(
        _text(doc.get("portalClass"))
        or _text(doc.get("portalName"))
        or _text(doc.get("portalDate"))
        or _text(doc.get("portalSender"))
        or re.search(r"portale|polisweb|pst|pdp|pat|ptt|sigit|telematico", text)
    )


def _is_communication(doc: dict[str, Any]) -> bool:
    return bool(
        re.search(
            r"pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion|consegna",
            _doc_text(doc),
        )
    )


def _notification_proof_kind(doc: dict[str, Any]) -> str:
    text = _doc_text(doc)
    notification_context = bool(
        re.search(r"notifica|notificaz|originale notificato|legge n\.?\s*53|l\.?\s*53|notifica[_\s-]*id", text)
    )
    if notification_context and "relata" in text:
        return "relata"
    if "originale notificato" in text and re.search(r"ricorso|citazione|comparsa|memoria|istanza|atto|decreto", text):
        return "atto_notificato"
    if notification_context and re.search(r"accettazione|rac", text):
        return "rac"
    if notification_context and re.search(r"consegna|rdac|avvenuta consegna", text):
        return "rdac"
    if notification_context and re.search(r"pec inviata|postacert|messaggio pec|\.eml", text):
        return "pec"
    if notification_context and "attestazione di conform" in text:
        return "attestazione"
    return ""


def _portal_catalog_role(value: object) -> dict[str, object]:
    text = _norm(value)
    if re.search(r"sentenza|ordinanza|decreto|provvediment|verbale", text):
        return {"depositCandidate": False}
    if re.search(r"ricevut|accettazion|consegna|rdac|rac|esito|cancelleria|pec|comunicazion", text):
        return {"depositCandidate": False}
    if re.search(r"atto principale|atto|ricorso|citazione|comparsa|memoria|istanza|deduzion|conclusionale", text):
        return {"depositCandidate": True}
    if re.search(r"allegato|procura|documento|contratto|quietanza", text):
        return {"depositCandidate": True}
    return {"depositCandidate": False}


def _is_deposit_candidate(doc: dict[str, Any]) -> bool:
    if _is_communication(doc):
        return False
    if not _is_portal_acquired(doc):
        return True
    return bool(_portal_catalog_role(f"{doc.get('portalClass', '')} {doc.get('type', '')} {doc.get('name', '')}")["depositCandidate"])


def _is_manual_selectable(doc: dict[str, Any]) -> bool:
    return not _is_communication(doc)


def _is_main_act(doc: dict[str, Any]) -> bool:
    text = _doc_text(doc)
    if re.search(r"procura|contributo|pagopa|marca|nota iscrizione|nir|ricevut|accettazion|consegna|rdac|rac|relata|pec|notifica_id", text):
        return False
    return bool(re.search(r"atto|ricorso|citazione|comparsa|memoria|istanza|appello|reclamo|opposizione|deduzion", text))


def _unique_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        doc_id = _text(doc.get("id"))
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc)
    return out


def _deposit_act_code(doc: dict[str, Any] | None, profile: dict[str, Any]) -> str:
    text = _norm(
        f"{_text((doc or {}).get('type'))} {_text((doc or {}).get('name'))} "
        f"{_record_text(profile, 'procedureCode')} {_record_text(profile, 'practiceId')}"
    )
    if "comparsa" in text:
        return "COMPARSA_RISPOSTA"
    if re.search(r"decreto ingiuntivo|ingiuntiv", text):
        return "DECRETO_INGIUNTIVO"
    if re.search(r"appello|impugnazion|reclamo", text):
        return "APPELLO"
    if "citazion" in text:
        return "ATTO_DI_CITAZIONE"
    if "ricorso" in text:
        return "RICORSO"
    if re.search(r"memoria|note scritte|conclusionale|replica", text):
        return "MEMORIA"
    if "istanza" in text:
        return "ISTANZA"
    return "ATTO_GENERICO"


def _registry_code(fascicolo: dict[str, Any]) -> str:
    text = _norm(f"{fascicolo.get('type', '')} {fascicolo.get('procedureType', '')} {fascicolo.get('rg', '')}")
    if re.search(r"lavoro|rgl", text):
        return "RGL"
    if re.search(r"volontaria|vg", text):
        return "VG"
    if re.search(r"esecuz|rge", text):
        return "RGE"
    return "RG"


def build_deposito_form(payload: dict[str, Any], *, include_all_candidates: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    fascicolo = payload.get("fascicolo") if isinstance(payload.get("fascicolo"), dict) else {}
    regia = payload.get("regia") if isinstance(payload.get("regia"), dict) else {}
    profile = regia.get("profile") if isinstance(regia.get("profile"), dict) else {}
    slots = regia.get("documentSlots") if isinstance(regia.get("documentSlots"), list) else []
    docs = [doc for doc in (payload.get("documents") or []) if isinstance(doc, dict) and _text(doc.get("id"))]
    by_id = {_text(doc.get("id")): doc for doc in docs}
    deposit_candidates = [doc for doc in docs if _is_deposit_candidate(doc)]
    notification_proofs = [doc for doc in docs if _notification_proof_kind(doc)]
    manual = [doc for doc in docs if _is_manual_selectable(doc)]
    selectable = _unique_docs([*deposit_candidates, *manual, *notification_proofs])

    linked_docs: list[dict[str, Any]] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        doc_id = _record_text(slot, "documentId", "documentoId")
        if doc_id and doc_id in by_id:
            linked_docs.append(by_id[doc_id])

    proposed = _unique_docs([*linked_docs, *notification_proofs])
    if not proposed:
        proposed = _unique_docs(deposit_candidates)
    if include_all_candidates:
        proposed = _unique_docs([*proposed, *deposit_candidates])
    if not proposed:
        raise RuntimeError("Nessun documento candidato alla busta nel payload server.")

    main_act = next((doc for doc in proposed if _is_main_act(doc)), None) or next((doc for doc in deposit_candidates if _is_main_act(doc)), None)
    if not main_act:
        raise RuntimeError("Atto principale non determinabile dal payload server.")
    if not any(_text(doc.get("id")) == _text(main_act.get("id")) for doc in proposed):
        proposed = _unique_docs([main_act, *proposed])

    package_ids = [_text(doc.get("id")) for doc in proposed]
    form = {
        "tipo_atto": _deposit_act_code(main_act, profile),
        "codice_registro": _registry_code(fascicolo),
        "oggetto": _record_text(fascicolo, "codiceOggettoPst", "object", "title"),
        "codice_oggetto_pst": _record_text(fascicolo, "codiceOggettoPst"),
        "numero_rg": _record_text(fascicolo, "rgNumber", "numeroRg"),
        "anno_rg": _record_text(fascicolo, "rgYear", "annoRg"),
        "atto_principale_id": _text(main_act.get("id")),
        "allegati_ids": [doc_id for doc_id in package_ids if doc_id != _text(main_act.get("id"))],
        "documenti_selezionati_ids": package_ids,
        "firma_unica": "1" if any(not bool(doc.get("signed")) for doc in proposed) else "0",
        "documenti_da_firmare_ids": [_text(doc.get("id")) for doc in proposed if not bool(doc.get("signed"))],
    }
    summary = {
        "fascicolo": {
            "id": _record_text(fascicolo, "id"),
            "ref": _record_text(fascicolo, "ref", "rg"),
            "title": _record_text(fascicolo, "title"),
            "client": _record_text(fascicolo, "client"),
            "codiceOggettoPst": _record_text(fascicolo, "codiceOggettoPst"),
        },
        "mainAct": {"id": _text(main_act.get("id")), "name": _text(main_act.get("name"))},
        "selectedDocuments": [{"id": _text(doc.get("id")), "name": _text(doc.get("name")), "signed": bool(doc.get("signed"))} for doc in proposed],
        "totalDocumentsInFascicolo": len(docs),
        "totalSelected": len(proposed),
    }
    return form, summary


class HttpSession:
    def __init__(self, base_url: str, *, insecure_tls: bool = False) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        context = ssl._create_unverified_context() if insecure_tls else None
        handlers = [HTTPCookieProcessor(CookieJar())]
        if context is not None:
            import urllib.request

            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = build_opener(*handlers)

    def request(self, method: str, path: str, *, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> ServerResponse:
        url = path if urlparse(path).scheme else urljoin(self.base_url, path.lstrip("/"))
        body = None
        request_headers = dict(headers or {})
        if data is not None:
            encoded_pairs: list[tuple[str, str]] = []
            for key, value in data.items():
                if isinstance(value, list):
                    encoded_pairs.extend((key, _text(item)) for item in value)
                else:
                    encoded_pairs.append((key, _text(value)))
            body = urlencode(encoded_pairs).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        request = Request(url, data=body, headers=request_headers, method=method.upper())
        try:
            with self.opener.open(request, timeout=60) as response:
                return ServerResponse(
                    status=int(response.status),
                    headers={key: value for key, value in response.headers.items()},
                    body=response.read(),
                    url=response.geturl(),
                )
        except HTTPError as exc:
            return ServerResponse(
                status=int(exc.code),
                headers={key: value for key, value in exc.headers.items()},
                body=exc.read(),
                url=exc.url,
            )


def run(args: argparse.Namespace) -> dict[str, Any]:
    session = HttpSession(args.base_url, insecure_tls=args.insecure_tls)
    login = session.request(
        "POST",
        "/login",
        data={"username": args.username, "password": args.password},
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    if login.status not in {200, 302, 303}:
        raise RuntimeError(f"Login non riuscito: HTTP {login.status}")

    payload_response = session.request(
        "GET",
        f"/api/v1/ui/fascicoli/{quote(args.fascicolo_id, safe='')}?include=all",
        headers={"Accept": "application/json"},
    )
    if payload_response.status != 200:
        raise RuntimeError(f"Payload fascicolo non disponibile: HTTP {payload_response.status} {payload_response.body[:200]!r}")
    payload = json.loads(payload_response.body.decode("utf-8"))
    if payload.get("notFound"):
        raise RuntimeError(f"Fascicolo non trovato sul server: {args.fascicolo_id}")

    form, summary = build_deposito_form(payload, include_all_candidates=args.include_all_candidates)
    if args.max_documents and len(form["documenti_selezionati_ids"]) > args.max_documents:
        selected_ids = list(form["documenti_selezionati_ids"])[: args.max_documents]
        form["documenti_selezionati_ids"] = selected_ids
        form["allegati_ids"] = [doc_id for doc_id in selected_ids if doc_id != form["atto_principale_id"]]
        summary["selectedDocuments"] = [
            doc for doc in summary["selectedDocuments"] if doc["id"] in set(selected_ids)
        ]
        summary["totalSelected"] = len(selected_ids)

    if not args.output_dir.exists():
        args.output_dir.mkdir(parents=True, exist_ok=True)
    package_response = session.request(
        "POST",
        f"/fascicoli/{quote(args.fascicolo_id, safe='')}/deposito/genera-busta",
        data=form,
        headers={"Accept": "application/octet-stream,application/json"},
    )
    content_type = package_response.headers.get("Content-Type", "")
    if package_response.status != 200 or "application/octet-stream" not in content_type:
        raise RuntimeError(
            "Generazione busta server non riuscita: "
            f"HTTP {package_response.status} {content_type} {package_response.body[:500]!r}"
        )
    filename = f"server-dry-run-{args.fascicolo_id}.enc"
    disposition = package_response.headers.get("Content-Disposition", "")
    match = re.search(r"filename=\"?([^\";]+)", disposition)
    if match:
        filename = Path(match.group(1)).name
    package_path = args.output_dir / filename
    package_path.write_bytes(package_response.body)

    report = {
        "ok": True,
        "serverDryRun": True,
        "baseUrl": args.base_url,
        "fascicoloId": args.fascicolo_id,
        "packagePath": str(package_path),
        "packageSize": package_path.stat().st_size,
        "mustNotSendRealPec": True,
        "usedRoute": f"/fascicoli/{args.fascicolo_id}/deposito/genera-busta",
        "payloadRoute": f"/api/v1/ui/fascicoli/{args.fascicolo_id}?include=all",
        "selection": summary,
        "formKeys": sorted(form.keys()),
        "note": "La prova ha generato la busta dal server e non ha chiamato alcuna route di invio PEC.",
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run server della busta deposito senza invio PEC.")
    parser.add_argument("--base-url", required=True, help="URL ambiente server, es. https://app.iusentra.it")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--fascicolo-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--include-all-candidates", action="store_true")
    parser.add_argument("--max-documents", type=int, default=0, help="Limite tecnico opzionale per dry-run controllato.")
    parser.add_argument("--insecure-tls", action="store_true")
    args = parser.parse_args(argv)
    try:
        run(args)
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
