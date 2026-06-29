"""Ministerial anagrafica helpers for PCT deposit packages."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from web.services.deposito_semantic_helpers import ministerial_valore_causa_for_context

_ATTI_NS = "http://schemi.processotelematico.giustizia.it/tipi/atti/v6"
_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/tipi/anagrafiche/v4"


def _clean_cf(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def _split_nome_cognome(value: str) -> tuple[str, str]:
    parts = [part for part in str(value or "").strip().split() if part]
    if len(parts) >= 2:
        return parts[-1], " ".join(parts[:-1])
    return "", parts[0] if parts else ""


def _cliente_deposito(get_clienti: Callable[[], Any], fascicolo: Any) -> Any | None:
    cliente_id = str(getattr(fascicolo, "id_cliente", "") or "").strip()
    if not cliente_id:
        return None
    try:
        return get_clienti().get(cliente_id)
    except Exception:
        return None


def _ministero_istruzione_counterparty(nome: str) -> dict[str, str] | None:
    text = str(nome or "").casefold()
    if "ministero" in text and ("istruzione" in text or "merito" in text or "mim" in text):
        return {
            "denominazione": "Ministero dell'Istruzione e del Merito",
            "codice_fiscale": "80185250588",
            "via": "Viale Trastevere 76 A",
            "cap": "00153",
            "localita": "Roma",
            "provincia": "RM",
        }
    return None


def _indirizzo_node(parent: Any, *, via: str, cap: str, localita: str, provincia: str) -> None:
    from lxml import etree

    indirizzo = etree.SubElement(parent, f"{{{_ANAGRAFICHE_NS}}}indirizzo")
    etree.SubElement(indirizzo, f"{{{_ANAGRAFICHE_NS}}}via").text = str(via or "").strip()
    etree.SubElement(indirizzo, f"{{{_ANAGRAFICHE_NS}}}cap").text = str(cap or "").strip()
    etree.SubElement(indirizzo, f"{{{_ANAGRAFICHE_NS}}}localita").text = str(localita or "").strip()
    etree.SubElement(indirizzo, f"{{{_ANAGRAFICHE_NS}}}provincia").text = str(provincia or "").strip().upper()
    etree.SubElement(indirizzo, f"{{{_ANAGRAFICHE_NS}}}stato").text = "IT"


def _anagrafica_procedimento_deposito_xml(
    *,
    fascicolo: Any,
    cliente: Any | None,
    cfg_studio: Any | None,
    operatore: str,
) -> bytes:
    from lxml import etree

    missing: list[str] = []
    parte_id = "parte_ricorrente_1"

    cliente_tipo = str(getattr(cliente, "tipo", "") or "")
    cliente_nome = str(getattr(cliente, "nome", "") or "").strip()
    cliente_cognome = str(getattr(cliente, "cognome", "") or "").strip()
    cliente_denominazione = str(getattr(cliente, "ragione_sociale", "") or "").strip()
    if not (cliente_nome or cliente_cognome or cliente_denominazione):
        fallback_nome, fallback_cognome = _split_nome_cognome(str(getattr(fascicolo, "nome_cliente", "") or ""))
        cliente_nome = cliente_nome or fallback_nome
        cliente_cognome = cliente_cognome or fallback_cognome
    cliente_cf = _clean_cf(
        getattr(cliente, "codice_fiscale", "")
        or getattr(cliente, "partita_iva", "")
        or ""
    )
    if not cliente_cf:
        missing.append("codice fiscale cliente")

    indirizzo_cliente = (
        getattr(cliente, "indirizzo_residenza", None)
        or getattr(cliente, "indirizzo_domicilio", None)
        or getattr(cliente, "indirizzo_sede_legale", None)
    )
    cliente_via = " ".join(
        part
        for part in (
            str(getattr(indirizzo_cliente, "via", "") or "").strip(),
            str(getattr(indirizzo_cliente, "civico", "") or "").strip(),
        )
        if part
    )
    cliente_cap = str(getattr(indirizzo_cliente, "cap", "") or "").strip()
    cliente_localita = str(getattr(indirizzo_cliente, "comune", "") or "").strip()
    cliente_provincia = str(getattr(indirizzo_cliente, "provincia", "") or "").strip().upper()
    # L'indirizzo del cliente completa l'anagrafica, ma non deve fermare il deposito.

    controparte_nome = str(getattr(fascicolo, "controparte", "") or "").strip()
    controparte_cf = _clean_cf(getattr(fascicolo, "cf_controparte", "") or "")
    controparte_addr = _ministero_istruzione_counterparty(controparte_nome)
    if controparte_addr:
        controparte_nome = controparte_addr["denominazione"]
        controparte_cf = controparte_cf or controparte_addr["codice_fiscale"]
    if not controparte_nome:
        missing.append("controparte")
    if not controparte_cf:
        missing.append("codice fiscale controparte")

    studio_cfg = getattr(cfg_studio, "studio", None) if cfg_studio else None
    firma_cfg = getattr(cfg_studio, "firma", None) if cfg_studio else None
    avvocato_cf = _clean_cf(
        getattr(studio_cfg, "codice_fiscale_avvocato", "")
        or getattr(firma_cfg, "cf_avvocato", "")
        or getattr(firma_cfg, "certificato_codice_fiscale", "")
        or ""
    )
    avvocato_nome_completo = str(getattr(studio_cfg, "avvocato", "") or operatore or "").strip()
    avvocato_nome, avvocato_cognome = _split_nome_cognome(avvocato_nome_completo)
    if not avvocato_cf:
        missing.append("codice fiscale avvocato")
    if not avvocato_cognome:
        missing.append("cognome avvocato")

    studio_via = str(getattr(studio_cfg, "indirizzo", "") or "").strip()
    studio_city = str(getattr(studio_cfg, "city", "") or "").strip()
    studio_province = str(getattr(studio_cfg, "province", "") or "").strip().upper()
    # Anche l'indirizzo dello studio e' informativo: non blocca la busta.
    if missing:
        raise ValueError("Dati anagrafici ministeriali mancanti: " + ", ".join(dict.fromkeys(missing)))

    root = etree.Element(f"{{{_ATTI_NS}}}AnagraficaProcedimento", nsmap={None: _ATTI_NS, "at": _ANAGRAFICHE_NS})
    partecipanti = etree.SubElement(root, f"{{{_ATTI_NS}}}Partecipanti")
    natura_cliente = "ENP" if ("GIURIDICA" in cliente_tipo.upper() or len(cliente_cf) == 11) else "PFI"
    parte = etree.SubElement(partecipanti, f"{{{_ATTI_NS}}}Parte", naturaGiuridica=natura_cliente, ID=parte_id)
    if natura_cliente == "PFI":
        etree.SubElement(parte, f"{{{_ANAGRAFICHE_NS}}}denominazione").text = cliente_cognome or cliente_nome
        if cliente_nome:
            etree.SubElement(parte, f"{{{_ANAGRAFICHE_NS}}}nome").text = cliente_nome
    else:
        etree.SubElement(parte, f"{{{_ANAGRAFICHE_NS}}}denominazione").text = (
            cliente_denominazione or " ".join(part for part in (cliente_cognome, cliente_nome) if part)
        )
    etree.SubElement(parte, f"{{{_ANAGRAFICHE_NS}}}codiceFiscale").text = cliente_cf
    _indirizzo_node(parte, via=cliente_via, cap=cliente_cap, localita=cliente_localita, provincia=cliente_provincia)

    controparte = etree.SubElement(partecipanti, f"{{{_ATTI_NS}}}ControParte", naturaGiuridica="ENP", ID="controparte_1")
    etree.SubElement(controparte, f"{{{_ANAGRAFICHE_NS}}}denominazione").text = controparte_nome
    etree.SubElement(controparte, f"{{{_ANAGRAFICHE_NS}}}codiceFiscale").text = controparte_cf
    _indirizzo_node(
        controparte,
        via=(controparte_addr or {}).get("via", ""),
        cap=(controparte_addr or {}).get("cap", ""),
        localita=(controparte_addr or {}).get("localita", ""),
        provincia=(controparte_addr or {}).get("provincia", ""),
    )

    soggetti = etree.SubElement(root, f"{{{_ATTI_NS}}}Soggetti")
    avvocato = etree.SubElement(soggetti, f"{{{_ATTI_NS}}}Avvocato")
    etree.SubElement(avvocato, f"{{{_ANAGRAFICHE_NS}}}cognome").text = avvocato_cognome
    if avvocato_nome:
        etree.SubElement(avvocato, f"{{{_ANAGRAFICHE_NS}}}nome").text = avvocato_nome
    etree.SubElement(avvocato, f"{{{_ANAGRAFICHE_NS}}}codiceFiscale").text = avvocato_cf
    _indirizzo_node(avvocato, via=studio_via, cap="", localita=studio_city, provincia=studio_province)
    etree.SubElement(avvocato, f"{{{_ANAGRAFICHE_NS}}}parteRappresentata", ref=parte_id)
    return etree.tostring(root, pretty_print=True, xml_declaration=False, encoding="UTF-8")


def anagrafica_xml_se_ricorso(
    *,
    tipo_atto: str,
    fascicolo: Any,
    get_clienti: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    operatore: str,
) -> bytes | None:
    if str(tipo_atto or "").strip().upper() != "RICORSO":
        return None
    cfg_studio = None
    try:
        cfg_studio = get_config_studio().config
    except Exception:
        cfg_studio = None
    return _anagrafica_procedimento_deposito_xml(
        fascicolo=fascicolo,
        cliente=_cliente_deposito(get_clienti, fascicolo),
        cfg_studio=cfg_studio,
        operatore=operatore,
    )


def valore_causa_fascicolo(fascicolo: Any) -> float | None:
    return ministerial_valore_causa_for_context(fascicolo)
