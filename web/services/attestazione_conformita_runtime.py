"""Attestazione di conformità dal fascicolo: dati dello studio, anteprima e copia attestata salvata.

La copia attestata diventa un nuovo documento del fascicolo, accanto all'originale, pronto per la firma
digitale dell'avvocato (la sottoscrizione dell'attestazione è con firma digitale: art. 22 CAD).
"""

from __future__ import annotations

import hashlib
import io
from datetime import date
from typing import Any

from flask import current_app, g, jsonify, request, send_file

from pct import attestazione_conformita as att


def _runtime(nome: str) -> Any:
    return current_app.extensions["core_runtime"][nome]()


def dati_studio() -> dict[str, str]:
    """Avvocato e città dello studio (Impostazioni → Studio), con il nome dell'utente come ripiego."""
    avvocato, luogo = "", ""
    try:
        studio = _runtime("get_config_studio").config.studio
        avvocato, luogo = str(studio.avvocato or "").strip(), str(studio.city or "").strip()
    except Exception:
        current_app.logger.warning("Dati dello studio non leggibili per l'attestazione", exc_info=True)
    if not avvocato:
        utente = getattr(g, "utente_corrente", None)
        avvocato = str(getattr(utente, "nome_completo", "") or "").strip()
    avvocato = avvocato.removeprefix("Avv.").removeprefix("avv.").strip()
    return {"avvocato": avvocato, "luogo": luogo}


def opzioni(documento: Any) -> dict[str, Any]:
    studio = dati_studio()
    return {"ok": True, "documento": {"id": documento.id, "nome": documento.nome}, **att.opzioni(),
            "predefiniti": {**studio, "firma": studio["avvocato"], "data": date.today().isoformat(), "tipo": "analogico",
                            "carattereTesto": "times", "dimensioneTesto": 11, "carattereFirma": "times",
                            "stileFirma": "corsivo", "dimensioneFirma": 14, "posizione": "pagina"},
            "mancano": [voce for voce, valore in (("nome dell'avvocato", studio["avvocato"]), ("città dello studio", studio["luogo"]))
                        if not valore]}


def nome_copia(nome: str) -> str:
    radice = nome[:-4] if nome.lower().endswith(".pdf") else nome
    return f"{radice} - copia conforme.pdf"


def prepara(pdf: bytes, dati: dict[str, Any]) -> bytes:
    studio = dati_studio()
    return att.applica(pdf, att.da_dati(dati, avvocato=studio["avvocato"], luogo=studio["luogo"]))


def salva(gestore: Any, id_fasc: str, documento: Any, contenuto: bytes, encrypt_doc: Any) -> Any:
    utente = getattr(g, "utente_corrente", None)
    return gestore.aggiungi_documento(
        id_fasc,
        nome_file=nome_copia(documento.nome),
        tipo=documento.tipo,
        contenuto=encrypt_doc(contenuto),
        note=f"Copia con attestazione di conformità di «{documento.nome}»: da firmare digitalmente.",
        caricato_da=getattr(utente, "username", "") or "attestazione",
        hash_contenuto_sha256=hashlib.sha256(contenuto).hexdigest(),
    )


def risposta_rotta(gestore: Any, id_fasc: str, id_doc: str, *, decrypt_doc: Any, encrypt_doc: Any, audit: Any) -> Any:
    """GET: dati dello studio e scelte. POST con «anteprima»: il PDF da vedere. POST: salva la copia attestata.

    Base normativa: art. 22 e 23-bis CAD; art. 196-octies disp. att. c.p.c.; art. 136, comma 2-ter, c.p.a.
    """
    fascicolo = gestore.get(id_fasc)
    documento = next((doc for doc in getattr(fascicolo, "documenti", []) or [] if doc.id == id_doc), None)
    if fascicolo is None or documento is None:
        return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
    if request.method == "GET":
        return jsonify(opzioni(documento))
    if not documento.nome.lower().endswith(".pdf"):
        return jsonify({"ok": False, "messaggio": "L'attestazione si appone su un PDF: converti prima il documento."}), 400
    dati = request.get_json(silent=True) or request.form.to_dict()
    try:
        contenuto = prepara(decrypt_doc(gestore.percorso_documento_lettura(id_fasc, id_doc).read_bytes()), dati)
    except ValueError as exc:
        return jsonify({"ok": False, "messaggio": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Attestazione di conformità non generata (%s, %s): %s", id_fasc, id_doc, exc)
        return jsonify({"ok": False, "messaggio": "Attestazione non generata: il PDF non è leggibile."}), 422
    if str(dati.get("anteprima") or "").lower() in {"1", "true"}:
        risposta = send_file(io.BytesIO(contenuto), mimetype="application/pdf", as_attachment=False,
                             download_name=nome_copia(documento.nome))
        risposta.headers["Cache-Control"] = "no-store"
        return risposta
    salvato = salva(gestore, id_fasc, documento, contenuto, encrypt_doc)
    audit("fascicoli.documento.attestazione", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome} → {salvato.id}")
    return jsonify({"ok": True, "documento": {"id": salvato.id, "nome": salvato.nome},
                    "messaggio": f"Copia conforme salvata: «{salvato.nome}». Firmala digitalmente per completare l'attestazione."})


__all__ = ["dati_studio", "nome_copia", "opzioni", "prepara", "risposta_rotta", "salva"]
