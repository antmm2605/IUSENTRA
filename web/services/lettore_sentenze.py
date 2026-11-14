"""Lettore React dei provvedimenti (corpus, SentenzeWeb, traduzioni, testo ufficiale OpenGA).

Gli indirizzi restano quelli di prima (``...?embed=source``, aperti nelle finestre di lettura):
la pagina è una shell minima che monta ``LettoreSentenzaApp``; il testo arriva come JSON dallo
stesso indirizzo con ``?format=json`` e React lo mostra solo come testo (mai HTML interpretato).
Le risposte conservano ``Cache-Control: private, no-store`` e ``X-Content-Type-Options: nosniff``;
il JSON ha anche una CSP che non consente nulla (non è un documento da mostrare).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from flask import make_response, render_template, request

from pct.formatting import format_date_it

ENTRY_LETTORE = "src/lettoreSentenzaEntry.tsx"
CSP_JSON = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
NOTA_LETTURA = "Impaginazione di lettura del testo archiviato. Nessuna sintesi o approvazione giuridica aggiunta."


def richiesta_json() -> bool:
    return request.args.get("format") == "json"


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


def _url_esterno(valore: Any) -> str:
    url = _testo(valore)
    return url if urlparse(url).scheme in {"http", "https"} else ""


def _provenienza(documento: dict[str, Any]) -> str:
    ufficiale = documento.get("text_source_official")
    if ufficiale is False:
        return "Trascrizione da fonte non ufficiale"
    if ufficiale is True:
        return "Testo archiviato dalla fonte ufficiale"
    return "Testo archiviato · provenienza da verificare"


def _blocchi(documento: dict[str, Any]) -> list[dict[str, str]]:
    blocchi = []
    for blocco in documento.get("blocks") or []:
        titolo = blocco.get("kind") == "heading"
        blocchi.append({
            "tipo": "titolo" if titolo else "paragrafo",
            "testo": _testo(blocco.get("text")),
            "ancora": _testo(blocco.get("anchor")) if titolo else "",
        })
    return blocchi


def _avvisi_provvedimento(documento: dict[str, Any]) -> list[str]:
    avvisi = []
    if documento.get("status") == "source_notice":
        avvisi.append("La fonte contiene un avviso di oscuramento, non il testo della decisione.")
    if _testo(documento.get("source_notice")):
        avvisi.append(_testo(documento.get("source_notice")))
    for item in documento.get("documents") or []:
        lingua = _testo(item.get("language"))
        if lingua and lingua != "it":
            avvisi.append(f"Lingua del documento conservato: {lingua}. Nessuna traduzione automatica aggiunta.")
    return avvisi


def _integrita(documento: dict[str, Any]) -> list[dict[str, str]]:
    voci = [{"etichetta": "SHA-256 del testo visualizzato", "valore": _testo(documento.get("sha256"))}]
    if _testo(documento.get("original_sha256")):
        voci.append({"etichetta": "SHA-256 archiviato della versione", "valore": _testo(documento.get("original_sha256"))})
    return voci


def payload_corpus(documento: dict[str, Any]) -> dict[str, Any]:
    riga = [_testo(documento.get("authority"))]
    if _testo(documento.get("section")):
        riga.append(f"Sezione {_testo(documento.get('section'))}")
    if documento.get("date"):
        riga.append(f"{_testo(documento.get('date_label'))} {format_date_it(documento.get('date'))}".strip())
    fonte = _testo(documento.get("text_source_url"))
    return {
        "tipo": "provvedimento",
        "occhiello": "IUSENTRA · Lettura del provvedimento",
        "titolo": _testo(documento.get("title")) or "Provvedimento archiviato",
        "righe": [" · ".join(parte for parte in riga if parte)],
        "provenienza": _provenienza(documento),
        "fonteTesto": fonte,
        "fonteUrl": "",
        "avvisi": _avvisi_provvedimento(documento),
        "blocchi": _blocchi(documento),
        "integrita": _integrita(documento),
        "nota": NOTA_LETTURA,
        "testoSempliceUrl": "?format=txt",
    }


def payload_sentenzeweb(documento: dict[str, Any]) -> dict[str, Any]:
    riga = [_testo(documento.get("authority")), f"Sezione {_testo(documento.get('section'))}"]
    if documento.get("date"):
        riga.append(f"Deposito {format_date_it(documento.get('date'))}")
    return {
        "tipo": "provvedimento",
        "occhiello": "IUSENTRA · Lettura del provvedimento",
        "titolo": f"Cassazione {_testo(documento.get('number'))}/{_testo(documento.get('year'))}",
        "righe": [" · ".join(parte for parte in riga if parte)],
        "provenienza": _provenienza(documento),
        "fonteTesto": "",
        "fonteUrl": _url_esterno(documento.get("text_source_url")),
        "avvisi": _avvisi_provvedimento({**documento, "documents": [], "source_notice": ""}),
        "blocchi": _blocchi(documento),
        "integrita": _integrita(documento),
        "nota": NOTA_LETTURA,
        "testoSempliceUrl": "?format=txt",
    }


def payload_traduzione(dati: dict[str, Any]) -> dict[str, Any]:
    avvisi = ["Traduzione automatica in italiano, non ufficiale e non asseverata.",
              "Confronta i passaggi con l’originale prima della citazione o dell’uso professionale. "
              "La traduzione non sostituisce il provvedimento conservato."]
    if dati.get("avvisi"):
        avvisi.append(f"{dati['avvisi']} passaggi presentano difformità da verificare e sono segnalati sotto.")
    originale = _testo(dati.get("originale_url"))
    return {
        "tipo": "traduzione",
        "occhiello": "IUSENTRA · Traduzione di servizio",
        "titolo": _testo(dati.get("titolo")) or "Provvedimento conservato",
        "righe": [],
        "provenienza": "Traduzione automatica, non ufficiale",
        "avvisi": avvisi,
        "linguaOriginale": _testo(dati.get("source_language")),
        "originaleUrl": originale if originale.startswith("/giurisprudenza/") else "",
        "parti": [
            {"originale": _testo(parte.get("originale")), "traduzione": _testo(parte.get("traduzione")),
             "avviso": _testo(parte.get("avviso"))}
            for parte in dati.get("parti") or []
        ],
        "blocchi": [],
        "integrita": [
            {"etichetta": "Motore e modello", "valore": f"{_testo(dati.get('modello'))} · {_testo(dati.get('motore'))}"},
            {"etichetta": "Revisione", "valore": _testo(dati.get("revisione"))},
            {"etichetta": "Impronta dell’originale", "valore": _testo(dati.get("source_sha256"))},
        ],
        "nota": "Nessuna approvazione giuridica aggiunta.",
    }


def payload_testo_ufficiale(documento: dict[str, Any]) -> dict[str, Any]:
    provenienza = documento.get("provenienza") or {}
    paragrafi = [riga.strip() for riga in str(documento.get("testo") or "").splitlines() if riga.strip()]
    return {
        "tipo": "testo_ufficiale",
        "occhiello": "IUSENTRA · Testo del provvedimento",
        "titolo": "Testo del provvedimento",
        "righe": [f"Pubblicazione: {_testo(provenienza.get('versione'))}", f"Acquisizione: {_testo(provenienza.get('acquisita_il'))}"],
        "provenienza": "Documento acquisito dalla fonte ufficiale. La valutazione e l’utilizzo nell’atto restano dell’avvocato.",
        "fonteTesto": "",
        "fonteUrl": _url_esterno(provenienza.get("url")),
        "avvisi": [],
        "blocchi": [{"tipo": "paragrafo", "testo": paragrafo, "ancora": ""} for paragrafo in paragrafi],
        "integrita": [
            {"etichetta": "Fonte", "valore": _testo(provenienza.get("url"))},
            {"etichetta": "SHA-256 del testo", "valore": _testo(provenienza.get("sha256"))},
            {"etichetta": "SHA-256 dell’originale", "valore": _testo(documento.get("raw_sha256"))},
        ],
        "nota": "",
    }


def _intestazioni(response, *, json: bool):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if json:
        response.headers["Content-Security-Policy"] = CSP_JSON
    return response


def risposta_json(payload: dict[str, Any]):
    """JSON con < > & codificati (\u003c…): nemmeno un lettore che lo interpretasse come HTML vi troverebbe markup."""
    corpo = json.dumps({"ok": True, "documento": payload}, ensure_ascii=False)
    corpo = corpo.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    response = make_response(corpo)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return _intestazioni(response, json=True)


def _asset_lettore() -> dict[str, Any]:
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir

    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    entry = (manifest or {}).get(ENTRY_LETTORE) or {}
    entry_file = entry.get("file")
    if not entry_file:
        return {"ready": False}
    route = _cached_route_assets(manifest_path, manifest, ENTRY_LETTORE)
    entry_url = f"/static/react/{entry_file}"
    return {
        "ready": True,
        "entry": entry_url,
        "css": route["css"],
        "preload_js": [url for url in route["js"] if url != entry_url],
    }


def risposta_lettore(titolo: str):
    """Shell del lettore React: nessun testo del provvedimento nel documento, solo l'indirizzo del JSON."""
    html = render_template("lettore_sentenza_shell.html", react_assets=_asset_lettore(), titolo=titolo)
    return _intestazioni(make_response(html), json=False)


__all__ = [
    "payload_corpus",
    "payload_sentenzeweb",
    "payload_testo_ufficiale",
    "payload_traduzione",
    "richiesta_json",
    "risposta_json",
    "risposta_lettore",
]
