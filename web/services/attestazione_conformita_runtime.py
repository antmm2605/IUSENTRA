"""«Attesta» dal fascicolo: l'attestazione di conformità si scrive sul PDF e poi si firma digitalmente.

Il documento resta lo stesso: la versione con l'attestazione lo sostituisce e quella precedente resta
nello storico del documento. Dopo, l'avvocato passa subito alla firma PAdES con la firma visibile in
basso («Per autentica e sottoscrizione», nome, data e luogo): la sottoscrizione dell'attestazione è
con firma digitale (art. 22 e 23-bis CAD; art. 196-octies disp. att. c.p.c.; art. 136, comma 2-ter, c.p.a.).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from flask import current_app, g, jsonify, request

from pct import attestazione_conformita as att

ROMA = ZoneInfo("Europe/Rome")
MODO_FIRMA_VISIBILE = "basso_destra"


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


def gia_firmato(documento: Any) -> bool:
    from pct.document_signature_state import document_has_real_digital_signature

    return bool(getattr(documento, "firmato_digitalmente", False)) or document_has_real_digital_signature(
        documento, str(getattr(documento, "nome", "") or ""))


def pagine_url(id_fasc: str, id_doc: str) -> dict[str, str]:
    """Il lettore del documento: misure delle pagine e pagina come immagine, per disegnare i riquadri."""
    base = f"/api/editor/{quote(id_fasc, safe='')}/{quote(id_doc, safe='')}"
    return {"meta": f"{base}/pdf-meta", "pagina": f"{base}/pdf-pagina/{{n}}.png"}


def opzioni(documento: Any, id_fasc: str = "") -> dict[str, Any]:
    studio = dati_studio()
    return {"ok": True, "documento": {"id": documento.id, "nome": documento.nome}, **att.opzioni(),
            "firmato": gia_firmato(documento),
            "pagine": pagine_url(id_fasc, str(documento.id)),
            "predefiniti": {**studio, "firma": att.cognome_nome(studio["avvocato"]), "testoFirma": studio["avvocato"],
                            "data": datetime.now(ROMA).date().isoformat(), "tipo": "analogico",
                            "carattereTesto": "arial", "dimensioneTesto": 12, "carattereFirma": "great_vibes",
                            "stileFirma": "normale", "dimensioneFirma": 18, "posizione": "spazio_libero"},
            "mancano": [voce for voce, valore in (("nome dell'avvocato", studio["avvocato"]), ("città dello studio", studio["luogo"]))
                        if not valore]}


def prepara(pdf: bytes, dati: dict[str, Any]) -> att.Esito:
    studio = dati_studio()
    return att.applica_con_esito(pdf, att.da_dati(dati, avvocato=studio["avvocato"], luogo=studio["luogo"]))


def anteprima_pagine(esito: att.Esito) -> list[dict[str, Any]]:
    """Le pagine toccate, come immagini per il lettore: si vede il risultato prima di scriverlo."""
    from pct.rendering_pdf import pagina_png

    return [{"numero": numero, "immagine": "data:image/png;base64," + base64.b64encode(
        pagina_png(esito.pdf, numero_pagina=numero, scala=1.4)).decode("ascii")} for numero in esito.pagine]


def url_firma(id_fasc: str, id_doc: str, luogo: str) -> str:
    """La pagina «Firma» del documento, con la firma visibile in basso e il luogo dell'attestazione."""
    parametri = urlencode({"firma_visibile": MODO_FIRMA_VISIBILE, "luogo": luogo, "da": "attestazione"})
    return f"/fascicoli/{quote(id_fasc, safe='')}/documenti/{quote(id_doc, safe='')}/firma?{parametri}"


def applica(gestore: Any, id_fasc: str, documento: Any, esito: att.Esito, encrypt_doc: Any) -> Any:
    """La versione con l'attestazione sostituisce il documento; la precedente resta nello storico."""
    utente = getattr(g, "utente_corrente", None)
    aggiornato = gestore.sostituisci_documento(
        id_fasc, documento.id, nome_file=documento.nome, contenuto=encrypt_doc(esito.pdf),
        caricato_da=getattr(utente, "username", "") or "attestazione",
        note="Attestazione di conformità inserita: da firmare digitalmente.",
        preserve_version_snapshot=True, hash_contenuto_sha256=hashlib.sha256(esito.pdf).hexdigest(),
    )
    try:
        from web.services.registro_letture_runtime import documento_aggiornato

        documento_aggiornato(id_fasc, aggiornato)
    except Exception:
        current_app.logger.warning("Registro letture non aggiornato dopo l'attestazione", exc_info=True)
    try:
        from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache

        clear_react_fascicoli_list_cache()
    except Exception:
        current_app.logger.debug("Cache elenco fascicoli non svuotata", exc_info=True)
    return aggiornato


def risposta_rotta(gestore: Any, id_fasc: str, id_doc: str, *, decrypt_doc: Any, encrypt_doc: Any, audit: Any) -> Any:
    """GET: dati dello studio, scelte e lettore. POST con «anteprima»: le pagine risultanti. POST: scrive e passa alla firma.

    Nel POST arrivano anche i riquadri disegnati dall'avvocato nel lettore («riquadroAttestazione»,
    «riquadroFirma»: pagina e frazioni della pagina); senza riquadro l'attestazione va nello spazio libero.
    """
    fascicolo = gestore.get(id_fasc)
    documento = next((doc for doc in getattr(fascicolo, "documenti", []) or [] if doc.id == id_doc), None)
    if fascicolo is None or documento is None:
        return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
    if request.method == "GET":
        return jsonify(opzioni(documento, id_fasc))
    if not documento.nome.lower().endswith(".pdf"):
        return jsonify({"ok": False, "messaggio": "L'attestazione si scrive su un PDF: converti prima il documento."}), 400
    if gia_firmato(documento):
        return jsonify({"ok": False, "messaggio": "Il documento è già firmato: l'attestazione si scrive prima della firma, "
                        "altrimenti la firma non sarebbe più valida. Riparti dalla copia non firmata."}), 409
    dati = request.get_json(silent=True) or request.form.to_dict()
    try:
        esito = prepara(decrypt_doc(gestore.percorso_documento_lettura(id_fasc, id_doc).read_bytes()), dati)
    except ValueError as exc:
        return jsonify({"ok": False, "messaggio": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Attestazione di conformità non generata (%s, %s): %s", id_fasc, id_doc, exc)
        return jsonify({"ok": False, "messaggio": "Attestazione non generata: il PDF non è leggibile."}), 422
    if str(dati.get("anteprima") or "").lower() in {"1", "true"}:
        return jsonify({"ok": True, "esito": esito.descrizione(), "pagine": anteprima_pagine(esito)})
    applica(gestore, id_fasc, documento, esito, encrypt_doc)
    audit("fascicoli.documento.attestazione", "fascicolo", id_fasc,
          dettagli=f"doc {id_doc} — {documento.nome} (pagina {esito.pagina}{', aggiunta' if esito.pagina_aggiunta else ''})")
    luogo = str(dati.get("luogo") or dati_studio()["luogo"] or "").strip()
    return jsonify({"ok": True, "documento": {"id": documento.id, "nome": documento.nome},
                    "firmaUrl": url_firma(id_fasc, id_doc, luogo),
                    "messaggio": f"{esito.descrizione()} Ora firma digitalmente «{documento.nome}» per sottoscrivere l'attestazione."})


__all__ = ["anteprima_pagine", "applica", "dati_studio", "gia_firmato", "opzioni", "prepara", "risposta_rotta", "url_firma"]
