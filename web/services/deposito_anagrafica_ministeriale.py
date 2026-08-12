"""Ministerial anagrafica helpers for PCT deposit packages."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from pct.formatting import format_euro_it
from web.services.deposito_semantic_helpers import (
    ministerial_contributo_unificato_for_context,
    ministerial_valore_causa_for_context,
)

_ATTI_NS = "http://schemi.processotelematico.giustizia.it/tipi/atti/v6"
_ATTI_V7_NS = "http://schemi.processotelematico.giustizia.it/tipi/atti/v7"
_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/tipi/anagrafiche/v4"
_SIGP_ATTI_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/atti/v3"
_SIGP_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/anagrafiche/v2"
_CASSAZIONE_ATTI_NS = "http://schemi.processotelematico.giustizia.it/cassazione/tipi/atti/v13"
_CASSAZIONE_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/cassazione/tipi/anagrafiche/v13"


def _clean_cf(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def _split_nome_cognome(value: str) -> tuple[str, str]:
    clean = re.sub(r"^avv(?:ocato|ocata)?\.?\s+", "", str(value or "").strip(), flags=re.IGNORECASE)
    if "," in clean:
        cognome, nome = (part.strip() for part in clean.split(",", 1))
        return nome, cognome
    parts = [part for part in clean.split() if part]
    if len(parts) >= 2:
        surname_start = len(parts) - 1
        if len(parts) >= 3 and parts[-2].casefold() in {"da", "dal", "dalla", "de", "dei", "del", "della", "di", "la", "lo"}:
            surname_start -= 1
        return " ".join(parts[:surname_start]), " ".join(parts[surname_start:])
    return parts[0] if parts else "", ""


def _cliente_deposito(get_clienti: Callable[[], Any], fascicolo: Any) -> Any | None:
    cliente_id = str(getattr(fascicolo, "id_cliente", "") or "").strip()
    if not cliente_id:
        return None
    try:
        return get_clienti().get(cliente_id)
    except Exception:
        return None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _indirizzo_context(indirizzo: Any) -> dict[str, str]:
    return {
        "via": str(getattr(indirizzo, "via", "") or "").strip(),
        "civico": str(getattr(indirizzo, "civico", "") or "").strip(),
        "cap": str(getattr(indirizzo, "cap", "") or "").strip(),
        "citta": str(getattr(indirizzo, "comune", "") or "").strip(),
        "provincia": str(getattr(indirizzo, "provincia", "") or "").strip().upper(),
        "nazione": str(getattr(indirizzo, "nazione", "") or "").strip(),
    }


def deposito_professionista_context(
    get_config_studio: Callable[[], Any],
    *,
    operatore: str = "",
    ruolo: str = "",
) -> dict[str, str]:
    try:
        config = get_config_studio().config
    except Exception:
        return {}
    studio = getattr(config, "studio", None)
    firma = getattr(config, "firma", None)
    pec = getattr(config, "pec", None)
    nome, cognome = _split_nome_cognome(str(getattr(studio, "avvocato", "") or operatore or ""))
    return {
        "ruolo": str(ruolo or getattr(studio, "deposito_telematico_role", "") or "").strip(),
        "nome": nome,
        "cognome": cognome,
        "codice_fiscale": _clean_cf(
            getattr(studio, "codice_fiscale_avvocato", "")
            or getattr(firma, "cf_avvocato", "")
            or getattr(firma, "certificato_codice_fiscale", "")
            or ""
        ),
        "indirizzo": str(getattr(studio, "indirizzo", "") or "").strip(),
        "cap": str(getattr(studio, "cap", "") or "").strip(),
        "citta": str(getattr(studio, "city", "") or "").strip(),
        "provincia": str(getattr(studio, "province", "") or "").strip().upper(),
        "pec": str(getattr(pec, "indirizzo", "") or "").strip(),
        "iban": str(getattr(studio, "iban", "") or "").strip(),
    }


def deposito_parti_context(
    fascicolo: Any,
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cliente = _cliente_deposito(get_clienti, fascicolo)
    if cliente is not None:
        tipo = _enum_value(getattr(cliente, "tipo", ""))
        residenza = (
            getattr(cliente, "indirizzo_residenza", None)
            if tipo == "PERSONA_FISICA"
            else getattr(cliente, "indirizzo_sede_legale", None)
        )
        rows.append(
            {
                "id": str(getattr(cliente, "id", "") or "").strip(),
                "gruppo": "parte",
                "ruolo": "ASSISTITO",
                "nome": str(getattr(cliente, "nome", "") or "").strip(),
                "cognome": str(getattr(cliente, "cognome", "") or "").strip(),
                "denominazione": str(getattr(cliente, "ragione_sociale", "") or "").strip(),
                "codice_fiscale": _clean_cf(
                    getattr(cliente, "codice_fiscale", "")
                    or getattr(cliente, "partita_iva", "")
                    or ""
                ),
                "natura_giuridica": "PFI" if tipo == "PERSONA_FISICA" else "PGI",
                "data_nascita": str(getattr(cliente, "data_nascita", "") or "").strip(),
                "indirizzo": _indirizzo_context(residenza),
                "domicilio": _indirizzo_context(getattr(cliente, "indirizzo_domicilio", None)),
            }
        )

    linked: list[Any] = []
    if callable(get_soggetti):
        try:
            linked = list(get_soggetti().parti_fascicolo(str(getattr(fascicolo, "id", "") or "")))
        except Exception:
            linked = []
    known_ids = {str(row.get("id") or "") for row in rows if str(row.get("id") or "")}
    counter_roles = {"CONTROPARTE", "DEBITORE"}
    party_roles = {"ASSISTITO", "CREDITORE", "INTERVENIENTE"}
    for parte, soggetto in linked:
        subject_id = str(getattr(soggetto, "id", "") or "").strip()
        if subject_id and subject_id in known_ids:
            continue
        ruolo = _enum_value(getattr(parte, "ruolo", ""))
        if ruolo == "DIFENSORE_CONTROPARTE":
            continue
        tipo = _enum_value(getattr(soggetto, "tipo", ""))
        natura = (
            "PFI"
            if tipo in {"PERSONA_FISICA", "PROFESSIONISTA"}
            else "PAM"
            if tipo == "PUBBLICA_AMMINISTRAZIONE"
            else "PGI"
        )
        rows.append(
            {
                "id": subject_id,
                "gruppo": "controparte" if ruolo in counter_roles else "parte" if ruolo in party_roles else "altro",
                "ruolo": ruolo,
                "nome": str(getattr(soggetto, "nome", "") or "").strip(),
                "cognome": str(getattr(soggetto, "cognome", "") or "").strip(),
                "denominazione": str(getattr(soggetto, "ragione_sociale", "") or "").strip(),
                "codice_fiscale": _clean_cf(
                    getattr(soggetto, "codice_fiscale", "")
                    or getattr(soggetto, "partita_iva", "")
                    or ""
                ),
                "natura_giuridica": natura,
                "data_nascita": str(getattr(soggetto, "data_nascita", "") or "").strip(),
                "qualifica": str(getattr(soggetto, "qualifica", "") or "").strip(),
                "indirizzo": _indirizzo_context(getattr(soggetto, "indirizzo", None)),
                "domicilio": _indirizzo_context(getattr(soggetto, "indirizzo", None)),
            }
        )
        if subject_id:
            known_ids.add(subject_id)

    if not any(row.get("gruppo") == "controparte" for row in rows):
        nome = str(getattr(fascicolo, "controparte", "") or "").strip()
        if nome:
            rows.append(
                {
                    "id": "controparte_fascicolo",
                    "gruppo": "controparte",
                    "ruolo": "CONTROPARTE",
                    "nome": "",
                    "cognome": "",
                    "denominazione": nome,
                    "codice_fiscale": _clean_cf(getattr(fascicolo, "cf_controparte", "") or ""),
                    "natura_giuridica": "PGI",
                    "data_nascita": "",
                    "indirizzo": _indirizzo_context(None),
                    "domicilio": _indirizzo_context(None),
                }
            )
    return rows


def deposito_busta_anagrafica_context(
    fascicolo: Any,
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None,
    get_config_studio: Callable[[], Any],
    operatore: str,
    professionista_ruolo: str = "",
) -> dict[str, Any]:
    return {
        "professionista": deposito_professionista_context(
            get_config_studio,
            operatore=operatore,
            ruolo=professionista_ruolo,
        ),
        "parti": deposito_parti_context(fascicolo, get_clienti=get_clienti, get_soggetti=get_soggetti),
    }


def _indirizzo_node(
    parent: Any,
    *,
    via: str,
    cap: str,
    localita: str,
    provincia: str,
    anagrafiche_ns: str = _ANAGRAFICHE_NS,
) -> None:
    from lxml import etree

    indirizzo = etree.SubElement(parent, f"{{{anagrafiche_ns}}}indirizzo")
    if anagrafiche_ns == _SIGP_ANAGRAFICHE_NS:
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}indirizzo").text = str(via or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}cap").text = str(cap or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}localita").text = str(localita or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}provincia").text = str(provincia or "").strip().upper()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}nazione").text = "IT"
    else:
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}via").text = str(via or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}cap").text = str(cap or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}localita").text = str(localita or "").strip()
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}provincia").text = str(provincia or "").strip().upper()
        final_name = "nazione" if anagrafiche_ns == _CASSAZIONE_ANAGRAFICHE_NS else "stato"
        etree.SubElement(indirizzo, f"{{{anagrafiche_ns}}}{final_name}").text = "IT"


def _anagrafica_procedimento_deposito_xml(
    *,
    fascicolo: Any,
    cliente: Any | None,
    cfg_studio: Any | None,
    operatore: str,
    professionista_ruolo: str = "",
    controparte_soggetto: dict[str, Any] | None = None,
    atti_ns: str = _ATTI_NS,
    anagrafiche_ns: str = _ANAGRAFICHE_NS,
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

    controparte_soggetto = controparte_soggetto or {}
    controparte_nome = str(
        controparte_soggetto.get("denominazione")
        or " ".join(
            part
            for part in (
                str(controparte_soggetto.get("cognome") or "").strip(),
                str(controparte_soggetto.get("nome") or "").strip(),
            )
            if part
        )
        or getattr(fascicolo, "controparte", "")
        or ""
    ).strip()
    controparte_cf = _clean_cf(
        controparte_soggetto.get("codice_fiscale")
        or getattr(fascicolo, "cf_controparte", "")
        or ""
    )
    controparte_addr = controparte_soggetto.get("indirizzo")
    controparte_addr = controparte_addr if isinstance(controparte_addr, dict) else {}
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

    root = etree.Element(f"{{{atti_ns}}}AnagraficaProcedimento", nsmap={None: atti_ns, "at": anagrafiche_ns})
    partecipanti = etree.SubElement(root, f"{{{atti_ns}}}Partecipanti")
    natura_cliente = "ENP" if ("GIURIDICA" in cliente_tipo.upper() or len(cliente_cf) == 11) else "PFI"
    parte = etree.SubElement(partecipanti, f"{{{atti_ns}}}Parte", naturaGiuridica=natura_cliente, ID=parte_id)
    if natura_cliente == "PFI":
        etree.SubElement(parte, f"{{{anagrafiche_ns}}}denominazione").text = cliente_cognome or cliente_nome
        if cliente_nome:
            etree.SubElement(parte, f"{{{anagrafiche_ns}}}nome").text = cliente_nome
    else:
        etree.SubElement(parte, f"{{{anagrafiche_ns}}}denominazione").text = (
            cliente_denominazione or " ".join(part for part in (cliente_cognome, cliente_nome) if part)
        )
    etree.SubElement(parte, f"{{{anagrafiche_ns}}}codiceFiscale").text = cliente_cf
    _indirizzo_node(
        parte,
        via=cliente_via,
        cap=cliente_cap,
        localita=cliente_localita,
        provincia=cliente_provincia,
        anagrafiche_ns=anagrafiche_ns,
    )

    controparte = etree.SubElement(partecipanti, f"{{{atti_ns}}}ControParte", naturaGiuridica="ENP", ID="controparte_1")
    etree.SubElement(controparte, f"{{{anagrafiche_ns}}}denominazione").text = controparte_nome
    etree.SubElement(controparte, f"{{{anagrafiche_ns}}}codiceFiscale").text = controparte_cf
    _indirizzo_node(
        controparte,
        via=" ".join(
            part
            for part in (
                str(controparte_addr.get("via") or "").strip(),
                str(controparte_addr.get("civico") or "").strip(),
            )
            if part
        ),
        cap=str(controparte_addr.get("cap") or ""),
        localita=str(controparte_addr.get("citta") or ""),
        provincia=str(controparte_addr.get("provincia") or ""),
        anagrafiche_ns=anagrafiche_ns,
    )

    soggetti = etree.SubElement(root, f"{{{atti_ns}}}Soggetti")
    avvocato = etree.SubElement(soggetti, f"{{{atti_ns}}}Avvocato")
    etree.SubElement(avvocato, f"{{{anagrafiche_ns}}}cognome").text = avvocato_cognome
    if avvocato_nome:
        etree.SubElement(avvocato, f"{{{anagrafiche_ns}}}nome").text = avvocato_nome
    etree.SubElement(avvocato, f"{{{anagrafiche_ns}}}codiceFiscale").text = avvocato_cf
    _indirizzo_node(
        avvocato,
        via=studio_via,
        cap="",
        localita=studio_city,
        provincia=studio_province,
        anagrafiche_ns=anagrafiche_ns,
    )
    parte_rappresentata = etree.SubElement(
        avvocato,
        f"{{{anagrafiche_ns}}}parteRappresentata",
        ref=parte_id,
    )
    if anagrafiche_ns == _CASSAZIONE_ANAGRAFICHE_NS:
        tipo_difensore = {
            "SOLODIFENSORE": "DI",
            "DIFENSOREDOMICILIATARIO": "DD",
        }.get(str(professionista_ruolo or "").strip())
        if tipo_difensore:
            etree.SubElement(
                parte_rappresentata,
                f"{{{anagrafiche_ns}}}tipoDifensore",
            ).text = tipo_difensore
    return etree.tostring(root, pretty_print=True, xml_declaration=False, encoding="UTF-8")


def _namespace_anagrafica_per_generatore(
    generator_class: str,
    root_name: str = "",
) -> tuple[str, str]:
    if "SIGP" in generator_class:
        return _SIGP_ATTI_NS, _SIGP_ANAGRAFICHE_NS
    if generator_class.startswith("ParteCassazione"):
        return _CASSAZIONE_ATTI_NS, _CASSAZIONE_ANAGRAFICHE_NS
    if generator_class in {
        "IntroduttiviSiecicConcorsuali",
        "IntroduttiviSiecicEsecuzioni",
        "ParteSiecicConcorsuali",
        "ParteSiecicEsecuzioni",
        "CurSiecicConcorsuali",
        "CusSiecicEsecuzioni",
        "DelSiecicEsecuzioni",
        "ProfSiecicConcorsuali",
        "ProfSiecicEsecuzioni",
        "Professionista",
    } or (
        generator_class == "IntroduttiviSicid"
        and root_name in {"RicorsoImmigrazioneConvalida", "RicorsoReclamoSospensiva"}
    ):
        return _ATTI_V7_NS, _ANAGRAFICHE_NS
    return _ATTI_NS, _ANAGRAFICHE_NS


def anagrafica_xml_se_ricorso(
    *,
    tipo_atto: str,
    fascicolo: Any,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
    get_config_studio: Callable[[], Any],
    operatore: str,
    datiatto_root_name: str = "",
    datiatto_generator_class: str = "",
    professionista_ruolo: str = "",
) -> bytes | None:
    root_name = str(datiatto_root_name or "").strip()
    generator_class = str(datiatto_generator_class or "").strip()
    parte_roots_requiring_anagrafica = {
        "AttoCostituzioneNuovoAvvocato",
        "ComparsaCostituzioneAppello",
        "ComparsaCostituzioneAppelloIncidentale",
        "CostituzioneConRiconvenzionale",
        "CostituzioneSemplice",
        "NominaCTPexart87",
        "Reclamo",
        "RicorsoCautelareCorsoCausa",
        "RicorsoSequestroConservativoCorsoCausa",
        "RicorsoSequestroGiudiziarioCorsoCausa",
    }
    siecic_roots_requiring_anagrafica = {
        "AttoCostituzioneAvvocato",
        "AttoGenerico",
        "AttoIntervento",
        "IstanzaAssegnazione",
        "IstanzaDistribuzione",
        "NotaPrecisazioneCredito",
        "Opposizione",
        "RinunciaDebitori",
    }
    requires_anagrafica = (
        generator_class.startswith("Introduttivi")
        or generator_class.startswith("ParteCassazione")
        or root_name in {"AttoRichiestaVisibilita", "IstanzaVendita"}
        or (generator_class == "Parte" and root_name in parte_roots_requiring_anagrafica)
        or (
            generator_class in {"ParteSiecicEsecuzioni", "ParteSiecicConcorsuali"}
            and root_name in siecic_roots_requiring_anagrafica
        )
    )
    if str(tipo_atto or "").strip().upper() != "RICORSO" and not requires_anagrafica:
        return None
    atti_ns, anagrafiche_ns = _namespace_anagrafica_per_generatore(generator_class, root_name)
    cfg_studio = None
    try:
        cfg_studio = get_config_studio().config
    except Exception:
        cfg_studio = None
    parti = deposito_parti_context(
        fascicolo,
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
    )
    controparte = next((row for row in parti if row.get("gruppo") == "controparte"), None)
    return _anagrafica_procedimento_deposito_xml(
        fascicolo=fascicolo,
        cliente=_cliente_deposito(get_clienti, fascicolo),
        cfg_studio=cfg_studio,
        operatore=operatore,
        professionista_ruolo=professionista_ruolo,
        controparte_soggetto=controparte,
        atti_ns=atti_ns,
        anagrafiche_ns=anagrafiche_ns,
    )


def valore_causa_fascicolo(fascicolo: Any) -> float | None:
    return ministerial_valore_causa_for_context(fascicolo)


def contributo_unificato_fascicolo(
    fascicolo: Any,
    documents: Iterable[Any] | None = None,
) -> dict[str, Any]:
    return ministerial_contributo_unificato_for_context(fascicolo, documents=documents)


def deposito_ministerial_readiness(
    *,
    fascicolo: Any,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
    get_config_studio: Callable[[], Any],
    operatore: str,
    documents: Iterable[Any] | None = None,
) -> dict[str, Any]:
    contribution = contributo_unificato_fascicolo(fascicolo, documents=documents)
    contribution_mode = str(contribution.get("mode") or "da_definire")
    contribution_labels = {
        "esente": "Esente",
        "pagato": "Pagato",
        "prenotato_a_debito": "Prenotato a debito",
        "da_definire": "Da definire",
    }
    contribution_messages = {
        "esente": "Esenzione già rilevata nel fascicolo. Nessuna ricevuta è necessaria.",
        "pagato": "Pagamento e ricevuta telematica registrati per il deposito.",
        "prenotato_a_debito": "Prenotazione a debito registrata e pronta per i dati del deposito.",
        "da_definire": "Indica se il contributo è esente, pagato o prenotato a debito.",
    }
    contribution_ready = bool(contribution.get("resolved"))
    contribution_message = contribution_messages.get(contribution_mode, contribution_messages["da_definire"])
    if not contribution_ready and contribution_mode == "pagato":
        contribution_message = str(contribution.get("blocking_message") or "").strip() or (
            "Inserisci l'importo e la ricevuta telematica del contributo unificato per proseguire."
        )
    elif not contribution_ready and contribution_mode == "prenotato_a_debito":
        contribution_message = "Seleziona la prenotazione a debito per proseguire."

    value = valore_causa_fascicolo(fascicolo)
    value_derived_from_exemption = value is None and contribution_mode == "esente"
    effective_value = 0.0 if value_derived_from_exemption else value

    anagrafica_missing: list[str] = []
    try:
        anagrafica_xml_se_ricorso(
            tipo_atto="RICORSO",
            fascicolo=fascicolo,
            get_clienti=get_clienti,
            get_soggetti=get_soggetti,
            get_config_studio=get_config_studio,
            operatore=operatore,
            datiatto_root_name="Ricorso",
            datiatto_generator_class="Introduttivi",
        )
        anagrafica_ready = True
    except ValueError as exc:
        anagrafica_ready = False
        detail = str(exc).partition(":")[2] or str(exc)
        anagrafica_missing = [item.strip() for item in detail.split(",") if item.strip()]

    return {
        "contributoUnificato": {
            "ready": contribution_ready,
            "mode": contribution_mode,
            "label": contribution_labels.get(contribution_mode, "Da definire"),
            "amount": contribution.get("importo"),
            "amountLabel": format_euro_it(contribution.get("importo")) if contribution.get("importo") is not None else "",
            "source": str(contribution.get("source") or ""),
            "message": contribution_message,
        },
        "anagraficaProcedimento": {
            "ready": anagrafica_ready,
            "label": "Pronta" if anagrafica_ready else "Da completare",
            "missing": anagrafica_missing,
            "message": (
                "Dati di cliente, controparte e avvocato già pronti per il deposito."
                if anagrafica_ready
                else "Completa soltanto i dati indicati per proseguire."
            ),
        },
        "valoreCausa": {
            "ready": effective_value is not None,
            "value": effective_value,
            "valueLabel": format_euro_it(effective_value) if effective_value is not None else "",
            "derivedFromExemption": value_derived_from_exemption,
            "message": (
                "Valore già acquisito dal fascicolo."
                if value is not None
                else "Valore impostato a zero perché il deposito è esente."
                if value_derived_from_exemption
                else "Inserisci il valore della causa per proseguire."
            ),
        },
    }
