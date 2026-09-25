"""Procedimento penale (PDP) impostato già all'apertura del fascicolo.

Nella creazione del fascicolo penale (completa o «Fascicolo Veloce») l'avvocato
può indicare subito i dati che la maschera del PDP chiede: tipo di ufficio,
registro, numero e anno, magistrato, ruolo dell'assistito ed eventuale altro
soggetto rappresentato (manuale PDP, «Ufficio Destinazione» e
«Identificazione Procedimento»; ruoli dei codificati tipi-parte). Il
fascicolo resta salvato anche se questa parte non va a buon fine: si segnala
e si completa dalla sezione «Deposito penale».
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from flask import current_app

from pct.penale_pdp import catalogo
from web.services import penale_pdp_contesto as contesto

CAMPI = ("pdp_ufficio", "pdp_registro", "pdp_numero", "pdp_anno", "pdp_magistrato", "pdp_ruolo",
         "pdp_altro_nome", "pdp_altro_ruolo", "pdp_autorizzato")


def catalogo_apertura(ufficio_nome: str = "", ufficio_codice: str = "PM-U") -> dict[str, Any]:
    """Le scelte della maschera di apertura (uffici, registri, ruoli del PDP) e, se c'è l'ufficio
    del fascicolo, distretto, circondario e sede da scegliere nella maschera «Ufficio Destinazione»."""
    esito: dict[str, Any] = {"ok": True, "uffici": catalogo.uffici(), "registri": catalogo.registri(),
                             "ruoli": catalogo.ruoli()}
    if ufficio_nome.strip():
        from pct.penale_pdp.sede import sede_pdp
        from pct.uffici_giudiziari import get_gestore

        esito["sede"] = sede_pdp(ufficio_nome, get_gestore().carica(), ufficio_codice.upper() or "PM-U")
    return esito


def _valore(form: Mapping[str, Any], chiave: str) -> str:
    return str(form.get(chiave) or "").strip()


def _registro_da_form(fascicolo: Any, form: Mapping[str, Any], ufficio: str) -> dict[str, Any] | None:
    numero = re.sub(r"\D", "", _valore(form, "pdp_numero") or str(fascicolo.numero_rg or ""))
    anno = re.sub(r"\D", "", _valore(form, "pdp_anno") or str(fascicolo.anno_rg or ""))
    if not (ufficio and numero and len(anno) == 4):
        return None
    return {"ufficio": ufficio, "registro": _valore(form, "pdp_registro") or "N", "numero": numero, "anno": anno,
            "magistrato": _valore(form, "pdp_magistrato") or str(fascicolo.giudice or ""),
            "ufficioNome": str(fascicolo.tribunale or ""), "corrente": True}


def _togli_automatici(arch: Any, caso_id: str, *, registro: dict[str, Any] | None, ruolo: str) -> None:
    """Quanto dedotto in automatico dal fascicolo lascia il posto a quanto indicato dall'avvocato."""
    if registro:
        for voce in arch.registri(caso_id):
            if voce["source"] == "fascicolo" and (voce["office_code"], voce["register_number"].lstrip("0")) != (
                    registro["ufficio"], str(int(registro["numero"]))):
                arch.elimina_registro(caso_id, voce["id"])
    if ruolo:
        for voce in arch.soggetti(caso_id):
            if voce["source"] == "fascicolo" and voce["role_code"] != ruolo:
                arch.elimina_soggetto(caso_id, voce["id"])


def applica(fid: str, form: Mapping[str, Any]) -> str:
    """Imposta il procedimento PDP dai campi ``pdp_*`` del modulo; restituisce il messaggio per l'avvocato."""
    if not any(_valore(form, chiave) for chiave in CAMPI):
        return ""
    try:
        fascicolo = contesto.fascicolo_penale(fid)
        caso = contesto.caso(fid)
        ufficio = _valore(form, "pdp_ufficio").upper() or contesto.ufficio_da_nome(fascicolo.tribunale)
        dati_caso: dict[str, Any] = {"ufficio": ufficio} if ufficio else {}
        if _valore(form, "pdp_autorizzato") in {"1", "on", "true", "si"}:
            dati_caso.update({"autorizzato": True, "fonte": "Indicato all'apertura del fascicolo"})
        if dati_caso:
            contesto.aggiorna_procedimento(fid, dati_caso)
        registro = _registro_da_form(fascicolo, form, ufficio)
        ruolo = _valore(form, "pdp_ruolo").upper()
        _togli_automatici(contesto.archivio(), caso["id"], registro=registro, ruolo=ruolo if fascicolo.nome_cliente else "")
        if registro:
            contesto.salva_registro(fid, registro)
        if ruolo and fascicolo.nome_cliente:
            contesto.salva_soggetto(fid, {"nome": fascicolo.nome_cliente, "ruolo": ruolo})
        if _valore(form, "pdp_altro_nome") and _valore(form, "pdp_altro_ruolo"):
            contesto.salva_soggetto(fid, {"nome": _valore(form, "pdp_altro_nome"), "ruolo": _valore(form, "pdp_altro_ruolo")})
        return " Procedimento penale (PDP) impostato: prosegui dalla sezione «Deposito penale»."
    except Exception as exc:
        current_app.logger.warning("Procedimento PDP non impostato all'apertura di %s: %s", fid, exc)
        return f" Procedimento penale (PDP) da completare nella sezione «Deposito penale»: {exc}"


__all__ = ["CAMPI", "applica", "catalogo_apertura"]
