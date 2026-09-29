"""Rotte della conservazione: pacchetto di versamento del fascicolo e registro dei versamenti.

Base normativa: artt. 43-44 CAD (D.Lgs. 82/2005); Linee guida AgID sulla formazione, gestione e
conservazione dei documenti informatici (§ 4, Allegati 2 e 5). IUSENTRA prepara il pacchetto di
versamento; la conservazione a norma la svolge il conservatore scelto dallo studio.
Lettura con ``fascicoli.leggi``, preparazione e registrazione con ``fascicoli.scrivi``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, Response, g, jsonify, request

ANNI_PREDEFINITI = 10  # prescrizione ordinaria (art. 2946 c.c.); art. 2220 c.c. per le scritture
MAX_DOCUMENTI = 300
MAX_BYTE = 400 * 1024 * 1024


def register_conservazione_routes(app: Flask, core: dict[str, Any]) -> None:
    get_fascicoli = core["get_fascicoli"]
    get_config_studio = core["get_config_studio"]
    audit = core["audit"]

    def _puo(permesso: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(permesso))
        except Exception:
            return False

    def _registro():
        from pct.conservazione.registro import RegistroVersamenti

        return RegistroVersamenti.accanto_a(get_config_studio().percorso)

    def _documenti_attivi(fascicolo) -> list:
        return [d for d in (getattr(fascicolo, "documenti", []) or []) if not getattr(d, "eliminato_il", "")]

    def _contenuto(id_fasc: str, documento) -> bytes:
        from web.services.document_crypto import decrypt_doc

        gestore = get_fascicoli()
        risolutore = getattr(gestore, "percorso_documento_lettura", None) or gestore.percorso_documento
        return decrypt_doc(Path(risolutore(id_fasc, documento.id)).read_bytes())

    @app.route("/api/v1/ui/fascicoli/<id_fasc>/conservazione")
    def conservazione_payload(id_fasc: str):
        from pct.conservazione.formati import formato_file

        if not _puo("fascicoli.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        fascicolo = get_fascicoli().get(id_fasc)
        if fascicolo is None:
            return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
        versamenti = _registro().per_fascicolo(id_fasc)
        versati = {d["id"] for v in versamenti if v.stato == "versato" for d in v.documenti}
        documenti = []
        for doc in _documenti_attivi(fascicolo):
            formato = formato_file(str(doc.nome or ""))
            documenti.append({"id": doc.id, "nome": doc.nome_originale or doc.nome, "tipo": getattr(doc.tipo, "value", str(doc.tipo)),
                              "data": str(doc.data_caricamento or "")[:10], "formato": formato["formato"], "idoneo": formato["idoneo"],
                              "nota": formato["nota"], "firmato": bool(doc.firmato_digitalmente), "versato": doc.id in versati})
        return jsonify({"ok": True, "puoModificare": _puo("fascicoli.scrivi"), "documenti": documenti,
                        "versamenti": [v.to_dict() for v in versamenti], "anniPredefiniti": ANNI_PREDEFINITI})

    @app.route("/fascicoli/<id_fasc>/conservazione/pacchetto", methods=["POST"])
    def conservazione_crea_pacchetto(id_fasc: str):
        from pct import __version__
        from pct.conservazione.metadati import impronta, metadati_documento
        from pct.conservazione.pacchetto import crea_pdv
        from pct.conservazione.registro import Versamento
        from web.services.document_crypto import encrypt_doc

        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        fascicolo = get_fascicoli().get(id_fasc)
        if fascicolo is None:
            return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
        dati = request.get_json(silent=True) or {}
        scelti = {str(i) for i in (dati.get("ids") or [])} if isinstance(dati.get("ids"), list) else set()
        documenti = [d for d in _documenti_attivi(fascicolo) if not scelti or d.id in scelti][:MAX_DOCUMENTI]
        try:
            anni = int(dati.get("anni") or ANNI_PREDEFINITI)
        except (TypeError, ValueError):
            anni = ANNI_PREDEFINITI
        anni = min(max(anni, 1), 9999)
        studio = get_config_studio().config.studio
        denominazione = str(studio.nome or "Studio legale")
        tipo_produttore = "PF" if str(studio.cf or "").strip()[:1].isalpha() else "PG"
        voci, mancanti, totale = [], [], 0
        for doc in documenti:
            try:
                contenuto = _contenuto(id_fasc, doc)
            except Exception:
                mancanti.append(doc.nome_originale or doc.nome)
                continue
            totale += len(contenuto)
            if totale > MAX_BYTE:
                return jsonify({"ok": False, "message": "Il pacchetto supera 400 MB: scegli meno documenti e crea più pacchetti."}), 400
            metadati = metadati_documento(doc, fascicolo, contenuto, produttore=denominazione, anni_conservazione=anni,
                                          riservato=bool(dati.get("riservato", True)), tipo_produttore=tipo_produttore,
                                          versione_software=__version__)
            voci.append((metadati, doc.nome_originale or doc.nome, contenuto))
        if not voci:
            return jsonify({"ok": False, "message": "Nessun documento leggibile da inserire nel pacchetto.", "mancanti": mancanti}), 400
        adesso = datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
        utente = g.get("utente_corrente")
        versamento = Versamento(fascicolo_id=id_fasc, creato_il=adesso, creato_da=str(getattr(utente, "username", "") or ""),
                                anni_conservazione=anni)
        oggetto = " ".join(p for p in (str(fascicolo.titolo or ""), f"R.G. {fascicolo.numero_rg}" if fascicolo.numero_rg else "") if p)
        pacchetto, elenco = crea_pdv(
            identificativo=versamento.id, creato_il=adesso,
            produttore={"Denominazione": denominazione, "TipoSoggetto": tipo_produttore, "CodiceFiscale": str(studio.cf or ""),
                        "PartitaIva": str(studio.piva or "")},
            fascicolo={"IdAggregazione": str(getattr(fascicolo, "numero", "") or fascicolo.id), "Oggetto": oggetto,
                       "DataApertura": str(getattr(fascicolo, "data_apertura", "") or "")[:10]},
            voci=voci)
        versamento.documenti = elenco
        versamento.impronta_pacchetto = impronta(pacchetto)
        versamento.dimensione = len(pacchetto)
        _registro().salva(versamento, encrypt_doc(pacchetto))
        audit("conservazione.pacchetto", "fascicolo", id_fasc, dettagli=f"{versamento.id}: {len(elenco)} documenti")
        messaggio = f"Pacchetto di versamento {versamento.id} pronto con {len(elenco)} documenti." + (
            f" {len(mancanti)} documenti non leggibili esclusi." if mancanti else "")
        return jsonify({"ok": True, "message": messaggio, "versamento": versamento.to_dict(), "mancanti": mancanti,
                        "download": f"/fascicoli/{id_fasc}/conservazione/{versamento.id}/pacchetto.zip"})

    @app.route("/fascicoli/<id_fasc>/conservazione/<vid>/pacchetto.zip")
    def conservazione_scarica(id_fasc: str, vid: str):
        from pct.conservazione.metadati import impronta
        from web.services.document_crypto import decrypt_doc

        if not _puo("fascicoli.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        registro = _registro()
        versamento = registro.get(vid)
        cifrato = registro.pacchetto(vid) if versamento and versamento.fascicolo_id == id_fasc else None
        if cifrato is None:
            return jsonify({"ok": False, "message": "Pacchetto non trovato."}), 404
        pacchetto = decrypt_doc(cifrato)
        if impronta(pacchetto) != versamento.impronta_pacchetto:
            return jsonify({"ok": False, "message": "Il pacchetto salvato non corrisponde all'impronta registrata."}), 409
        audit("conservazione.download", "fascicolo", id_fasc, dettagli=vid)
        return Response(pacchetto, mimetype="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{vid}.zip"', "X-Impronta-SHA256": versamento.impronta_pacchetto})

    @app.route("/fascicoli/<id_fasc>/conservazione/<vid>/esito", methods=["POST"])
    def conservazione_esito(id_fasc: str, vid: str):
        if not _puo("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        registro = _registro()
        versamento = registro.get(vid)
        if versamento is None or versamento.fascicolo_id != id_fasc:
            return jsonify({"ok": False, "message": "Pacchetto non trovato."}), 404
        dati = request.get_json(silent=True) or {}
        stato = str(dati.get("stato") or "")
        if stato not in {"versato", "rifiutato"}:
            return jsonify({"ok": False, "message": "Indica se il conservatore ha accettato o rifiutato il pacchetto."}), 400
        conservatore = str(dati.get("conservatore") or "").strip()[:120]
        try:
            data_versamento = date.fromisoformat(str(dati.get("data") or ""))
        except ValueError:
            return jsonify({"ok": False, "message": "Indica la data del rapporto di versamento."}), 400
        if not conservatore:
            return jsonify({"ok": False, "message": "Indica il conservatore."}), 400
        if data_versamento > datetime.now(ZoneInfo("Europe/Rome")).date():
            return jsonify({"ok": False, "message": "La data non può essere futura."}), 400
        versamento.stato, versamento.conservatore = stato, conservatore
        versamento.data_versamento = data_versamento.isoformat()
        versamento.id_rapporto = str(dati.get("idRapporto") or "").strip()[:120]
        versamento.note = str(dati.get("note") or "").strip()[:500]
        registro.salva(versamento)
        audit("conservazione.esito", "fascicolo", id_fasc, dettagli=f"{vid}: {stato} {conservatore}")
        return jsonify({"ok": True, "message": "Esito del versamento registrato.", "versamento": versamento.to_dict()})


__all__ = ["register_conservazione_routes"]
