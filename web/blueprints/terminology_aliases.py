"""Alias URL professionali per superfici storiche dell'applicativo."""

from __future__ import annotations

from urllib.parse import urlencode

from flask import Blueprint, redirect, request, url_for


terminology_aliases = Blueprint("terminology_aliases", __name__)


def _redirect_to(endpoint: str, **values):
    query = request.args.to_dict(flat=True)
    query.update(values)
    return redirect(url_for(endpoint, **query), code=302)


def _redirect_path(path: str, **values):
    query = request.args.to_dict(flat=True)
    query.update(values)
    suffix = f"?{urlencode(query)}" if query else ""
    return redirect(f"{path}{suffix}", code=302)


@terminology_aliases.get("/redazione-atti")
def redazione_atti():
    return _redirect_to("template_atti.lista")


@terminology_aliases.get("/redazione-atti/catalogo")
def redazione_atti_catalogo():
    return _redirect_to("template_atti.catalogo")


@terminology_aliases.get("/redazione-atti/redigi/<codice>")
def redazione_atti_redigi(codice: str):
    return _redirect_to("template_atti.compila", model_code=codice)


@terminology_aliases.get("/servizi-telematici")
def servizi_telematici():
    return _redirect_to("telematico_dashboard")


@terminology_aliases.get("/studio")
def studio():
    return _redirect_to("telematico_dashboard")


@terminology_aliases.get("/regia-operativa")
def regia_operativa():
    return _redirect_to("workspace_intelligente")


@terminology_aliases.get("/ricerca-studio")
def ricerca_studio():
    return _redirect_to("global_search.index")


@terminology_aliases.get("/ricerca-legale")
def ricerca_legale():
    return _redirect_path("/legal-intelligence/ricerca")


@terminology_aliases.get("/strumenti-operativi")
def strumenti_operativi():
    return _redirect_to("applicazioni.index")


@terminology_aliases.get("/compensi-forensi")
def compensi_forensi():
    return _redirect_to("tariffario")


@terminology_aliases.get("/notifiche-whatsapp")
def notifiche_whatsapp():
    return _redirect_path("/notifiche/")


@terminology_aliases.get("/incassi-pagamenti")
def incassi_pagamenti():
    return _redirect_path("/impostazioni/pagamenti")


@terminology_aliases.get("/impostazioni-studio")
def impostazioni_studio():
    return _redirect_path("/impostazioni")


@terminology_aliases.get("/sincronizzazione-calendari")
def sincronizzazione_calendari():
    return _redirect_path("/impostazioni/calendario")


@terminology_aliases.get("/amministrazione")
def amministrazione():
    return _redirect_path("/utenti")


@terminology_aliases.get("/registro-attivita")
def registro_attivita():
    return _redirect_path("/audit")


@terminology_aliases.get("/database")
def database():
    return _redirect_path("/admin/database")


@terminology_aliases.get("/registro-gdpr")
def registro_gdpr():
    return _redirect_path("/privacy/registro")
