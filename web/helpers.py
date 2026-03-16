"""
web/helpers.py — Factory functions condivise tra app.py e blueprint.

Ogni funzione usa `current_app` e `g` di Flask, quindi deve essere chiamata
dentro un application context (durante una request o with app.app_context()).
"""
from __future__ import annotations
import os
from flask import current_app, g

from pct.agenda import Agenda
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.scadenziario import GestioneScadenziario
from pct.auth import GestioneUtenti
from pct.search_index import IndiceRicerca


# ---------------------------------------------------------------- gestori dati

def get_agenda() -> Agenda:
    return Agenda(db_path=current_app.config["AGENDA_DB"])


def get_clienti() -> GestioneClienti:
    return GestioneClienti(db_path=current_app.config["CLIENTI_DB"])


def get_fascicoli() -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=current_app.config["FASCICOLI_DB"],
        documents_dir=current_app.config["FASCICOLI_DOCS"],
        archive_dir=current_app.config["FASCICOLI_ARCH"],
    )


def get_scadenziario() -> GestioneScadenziario:
    return GestioneScadenziario(db_path=current_app.config["SCADENZIARIO_DB"])


def get_utenti() -> GestioneUtenti:
    return GestioneUtenti(
        db_path=current_app.config["AUTH_DB"],
        audit_path=current_app.config["AUDIT_DB"],
        secret_key=current_app.secret_key,
    )


def get_indice() -> IndiceRicerca:
    return IndiceRicerca(index_path=current_app.config["SEARCH_INDEX"])


# ---------------------------------------------------------------- auth API

def utente_corrente():
    """Restituisce l'utente corrente dalla request o None."""
    return g.get("utente_corrente")


# ---------------------------------------------------------------- paginazione

def pagina(lista: list, page: int = 1, per_page: int = 20) -> dict:
    """Restituisce un dict paginato compatibile con il formato API v1."""
    per_page = max(1, min(int(per_page), 100))
    page = max(1, int(page))
    total = len(lista)
    start = (page - 1) * per_page
    return {
        "data": lista[start: start + per_page],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        },
    }
