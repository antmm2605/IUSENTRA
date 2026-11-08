"""Controparte dal modulo di modifica del fascicolo: soggetto scelto, riusato per identificativo o creato.

Separato da ``web/bootstrap/fascicoli_management_routes.py`` (limite di 650 righe per i moduli bootstrap).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pct.clienti import Recapiti
from pct.soggetti import TipoSoggetto, soggetto_coincide_con_cliente


def _split_nome_persona(nome_completo: str) -> tuple[str, str]:
    parti = [parte for parte in str(nome_completo or "").strip().split() if parte]
    if not parti:
        return "", ""
    if len(parti) == 1:
        return parti[0], ""
    return parti[0], " ".join(parti[1:])


def _tipo_soggetto_da_form(valore: str) -> TipoSoggetto:
    try:
        return TipoSoggetto(str(valore or "").strip() or "PERSONA_GIURIDICA")
    except ValueError:
        return TipoSoggetto.PERSONA_GIURIDICA


def _soggetto_esistente_per_identificativo(gestore_soggetti: Any, identificativo: str):
    valore = str(identificativo or "").strip().casefold()
    if not valore:
        return None
    for soggetto in gestore_soggetti.cerca(q=identificativo):
        if str(getattr(soggetto, "identificativo", "") or "").strip().casefold() == valore:
            return soggetto
    return None


def _probe_controparte(nome: str, identificativo: str) -> SimpleNamespace:
    return SimpleNamespace(
        id_cliente="",
        nome="",
        cognome="",
        ragione_sociale=str(nome or "").strip(),
        codice_fiscale=str(identificativo or "").strip(),
        partita_iva=str(identificativo or "").strip(),
    )


def controparte_coincide_con_cliente(nome: str, identificativo: str, clienti: list[Any]) -> bool:
    """Vero se la controparte indicata nel modulo è uno dei clienti (mai controparte di sé stesso)."""
    return soggetto_coincide_con_cliente(_probe_controparte(nome, identificativo), clienti)


def crea_o_riusa_controparte(
    gestore_soggetti: Any,
    form: Any,
    *,
    nome_base: str,
    identificativo_base: str,
    clienti_propri: list[Any],
):
    """La controparte scelta o inserita nella modifica del fascicolo; nessuna se coincide con un cliente proprio."""
    propri = clienti_propri
    id_soggetto = str(form.get("id_soggetto_controparte", "") or "").strip()
    if id_soggetto:
        soggetto = gestore_soggetti.get(id_soggetto)
        if not soggetto:
            raise ValueError("La controparte selezionata non è più disponibile. Scegli un soggetto valido o inserisci i dati manualmente.")
        if soggetto_coincide_con_cliente(soggetto, propri):
            return None
        return soggetto

    nome_completo = str(form.get("nuovo_soggetto_nome_completo", "") or "").strip() or nome_base
    identificativo = str(form.get("nuovo_soggetto_identificativo", "") or "").strip() or identificativo_base
    if not nome_completo or not identificativo:
        return None

    esistente = _soggetto_esistente_per_identificativo(gestore_soggetti, identificativo)
    if esistente:
        if soggetto_coincide_con_cliente(esistente, propri):
            return None
        return esistente

    tipo = _tipo_soggetto_da_form(form.get("nuovo_soggetto_tipo", "PERSONA_GIURIDICA"))
    recapiti = Recapiti(
        telefono=str(form.get("nuovo_soggetto_telefono", "") or "").strip(),
        email=str(form.get("nuovo_soggetto_email", "") or "").strip(),
        pec=str(form.get("nuovo_soggetto_pec", "") or "").strip(),
    )
    common = {
        "recapiti": recapiti,
        "note": "Creato durante la modifica del fascicolo.",
        "tag": ["controparte"],
    }
    if tipo == TipoSoggetto.PERSONA_FISICA:
        nome, cognome = _split_nome_persona(nome_completo)
        return gestore_soggetti.crea(
            tipo=tipo,
            nome=nome,
            cognome=cognome,
            codice_fiscale=identificativo,
            **common,
        )
    partita_iva = identificativo if identificativo.isdigit() and len(identificativo) == 11 else ""
    return gestore_soggetti.crea(
        tipo=tipo,
        ragione_sociale=nome_completo,
        codice_fiscale="" if partita_iva else identificativo,
        partita_iva=partita_iva,
        **common,
    )
