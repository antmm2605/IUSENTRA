"""Validazione deposito derivata dai metodi ``VerificaCampi*`` di Studio Telematico.

Il modulo non definisce policy autonome. Ogni esito restituito punta alla regola
estratta dal decompilato e conserva messaggio, severita' e riga sorgente.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from .deposito_studio_telematico_contract import (
    studio_telematico_document_requirements,
    studio_telematico_rule,
    studio_telematico_type_contract,
)


SOURCE_LABEL = "Studio Telematico 2026 Rel. 021 - FormSentMailBee.cs decompilato"

_BLOCKING_CONFIRMATION_RULES = {
    "VerificaCampiAnagraficaProcedimento:18485",
    "VerificaCampiAnagraficaProcedimento:18659",
    "VerificaCampiAnagraficaProcedimento:18675",
    "VerificaCampiEredit\u00c3\u00a0Successioni:19195",
}

FOLLOW_UP_MESSAGE_RULE_IDS = {
    "VerificaCampiAnagraficaProcedimento:18562",
    "VerificaCampiAnagraficaProcedimento:18576",
    "VerificaCampiAnagraficaProcedimento:18581",
}

# Questi rami esistono nel metodo comune decompilato, ma non sono raggiungibili
# quando il deposito proviene da una delle 270 chiavi catalogate. Restano
# censiti nell'audit, senza trasformarli in controlli autonomi IUSENTRA.
CATALOG_UNREACHABLE_RULE_IDS = {
    # Studio li usa soltanto quando AttoDaInviareKey e' vuota.
    "VerificaCampiAttoDaDepositare:17333",
    "VerificaCampiAttoDaDepositare:17340",
    # IsNotificaMezzoPEC appartiene al flusso notifica, non al deposito.
    "VerificaCampiAttoDaDepositare:17750",
    # Duplicati successivi a controlli identici che hanno gia' restituito false.
    "VerificaCampiAnagraficaProcedimento:18458",
    "VerificaCampiAnagraficaProcedimento:18467",
    # Il ramo esterno richiede Cassazione e quello interno richiede SIECIC.
    "VerificaCampiAnagraficaProcedimento:18579",
    # IsNotificaMezzoPEC appartiene alla notifica e non puo' essere vero nel
    # flusso dei 270 depositi, anche se il metodo sorgente e' condiviso.
    "VerificaCampiAnagraficaProcedimento:18659",
    # Nel controllo WinForms SelectedIndex e Value sono verificati in due rami
    # consecutivi. Il select React normalizza i due stati: una voce selezionata
    # ha sempre un value e l'assenza della voce e' gia' coperta dal primo ramo.
    "VerificaCampiIscrizioneRuolo:18853",
    "VerificaCampiIscrizioneRuolo:18888",
    "VerificaCampiIscrizioneRuolo:18923",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    raw = _text(value).replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    raw = _text(value)
    if not raw:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], pattern).date()
        except ValueError:
            continue
    return None


def _valid_year(value: Any) -> bool:
    raw = _text(value)
    return len(raw) == 4 and raw.isdigit()


def _valid_cf(value: Any) -> bool:
    raw = re.sub(r"[\s-]+", "", _text(value).upper())
    if not re.fullmatch(r"[A-Z0-9]{16}", raw):
        return False
    odd = {
        **{str(i): value for i, value in enumerate((1, 0, 5, 7, 9, 13, 15, 17, 19, 21))},
        **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23))),
    }
    even = {**{str(i): i for i in range(10)}, **{letter: index for index, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}}
    checksum = sum(odd[character] if index % 2 == 0 else even[character] for index, character in enumerate(raw[:15]))
    return raw[-1] == chr(ord("A") + checksum % 26)


def _valid_iban(value: Any) -> bool:
    raw = re.sub(r"\s+", "", _text(value).upper())
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", raw):
        return False
    rearranged = raw[4:] + raw[:4]
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    return int(numeric) % 97 == 1


def _finding(rule_id: str, field: str, *, fallback: str = "") -> dict[str, Any]:
    rule = studio_telematico_rule(rule_id) or {}
    outcome = _text(rule.get("outcome")) or "blocco"
    if rule_id in _BLOCKING_CONFIRMATION_RULES:
        outcome = "blocco"
    message = _text(rule.get("message")) or fallback
    return {
        "rule_id": rule_id,
        "source_line": int(rule.get("source_line") or 0),
        "method": _text(rule.get("method")),
        "outcome": outcome,
        "level": "BLOCK" if outcome == "blocco" else "WARNING",
        "field": field,
        "message": message,
        "source": f"{SOURCE_LABEL}, riga {int(rule.get('source_line') or 0)}",
    }


def _append(findings: list[dict[str, Any]], rule_id: str, field: str, condition: bool) -> None:
    if condition and all(item["rule_id"] != rule_id for item in findings):
        findings.append(_finding(rule_id, field))


def _extra(context: dict[str, Any]) -> dict[str, Any]:
    value = context.get("datiatto_extra")
    return value if isinstance(value, dict) else {}


def _enabled(controls: dict[str, Any], name: str, *, default: bool = False) -> bool:
    state = controls.get(name)
    if not isinstance(state, dict):
        return default
    value = _text(state.get("Enabled"))
    return value.casefold() == "true" if value else default


def _visible(controls: dict[str, Any], name: str, *, default: bool = False) -> bool:
    state = controls.get(name)
    if not isinstance(state, dict):
        return default
    value = _text(state.get("Visible"))
    return value.casefold() == "true" if value else default


def _digits(value: Any) -> bool:
    raw = _text(value)
    return not raw or raw.isdigit()


def _professionista(context: dict[str, Any]) -> dict[str, Any]:
    value = context.get("professionista")
    return value if isinstance(value, dict) else {}


def _role_text(context: dict[str, Any]) -> str:
    explicit = _text(context.get("ruolo_ministeriale"))
    if explicit:
        return explicit
    registry = _text(context.get("codice_registro")).upper()
    return {
        "CASSCI": "CassazioneCivile",
        "MIN": "Minorenni",
        "MINORI": "Minorenni",
        "RG": "Contenzioso",
        "RGE": "EsecuzioniCivili",
        "RGEI": "EspropriazioniImmobiliari",
        "RGL": "Lavoro",
        "SIECIC_CONCORSUALI": "VolontariaGiurisdizione",
        "SIECIC_ESIM": "EspropriazioniImmobiliari",
        "SIECIC_ESM": "EsecuzioniCivili",
        "SIGP": "GiudiceDiPace",
        "SIL": "Lavoro",
        "SIMIN": "Minorenni",
        "SIVG": "VolontariaGiurisdizione",
        "VG": "VolontariaGiurisdizione",
    }.get(registry, registry)


def _unep_parties(context: dict[str, Any]) -> list[dict[str, Any]]:
    changes = {
        _text(item.get("id")): item
        for item in list(_extra(context).get("unep_destinatari") or [])
        if isinstance(item, dict) and _text(item.get("id"))
    }
    parties: list[dict[str, Any]] = []
    for raw in list(context.get("parti") or []):
        if not isinstance(raw, dict):
            continue
        party = dict(raw)
        party.update(changes.get(_text(raw.get("id")), {}))
        parties.append(party)
    return parties


def _validate_documents(
    key: str,
    context: dict[str, Any],
    selected_documents: Iterable[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    documents = list(selected_documents)
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17766",
        "atto_principale_id",
        not _text(context.get("atto_principale_id")) and not documents,
    )
    classified = {_text(document.get("studio_document_type")) for document in documents}
    if classified.intersection({"ProcuraLiti", "ProcuraSpeciale", "ProcuraAttoPubblico"}):
        classified.add("Procura")
    for requirement in studio_telematico_document_requirements(key):
        code = _text(requirement.get("code"))
        if code and code not in classified:
            rule_id = _text(requirement.get("ruleId"))
            if rule_id:
                _append(findings, rule_id, "allegati_ids", True)

    if key.startswith("Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramento"):
        main_id = _text(context.get("atto_principale_id"))
        main_document = next((document for document in documents if _text(document.get("id")) == main_id), None)
        main_name = _text((main_document or {}).get("nome")).upper()
        _append(
            findings,
            "VerificaCampiAttoDaDepositare:17818",
            "atto_principale_id",
            bool(main_name) and "ISCRIZIONE A RUOLO" not in main_name,
        )

    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17902",
        "allegati_ids",
        key == "Parte_CASSAZIONE::IstanzaOpposizione380bis",
    )


def _validate_atto(
    key: str,
    contract: dict[str, Any],
    context: dict[str, Any],
    resolver: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    extra = _extra(context)
    controls = contract.get("controls") if isinstance(contract.get("controls"), dict) else {}
    office_found = bool(
        resolver.get("effective_office_found")
        or resolver.get("official_office_found")
        or _text(context.get("ufficio_giudiziario"))
    )
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17351" if key.startswith("Atti_UNEP::") else "VerificaCampiAttoDaDepositare:17355",
        "ufficio_giudiziario",
        not office_found,
    )

    is_cassazione = key.startswith("Parte_CASSAZIONE::")
    if is_cassazione:
        _append(
            findings,
            "VerificaCampiAttoDaDepositare:17398",
            "materia_ricorso_cassazione",
            not _text(extra.get("materia_ricorso_cassazione")),
        )
    else:
        _append(
            findings,
            "VerificaCampiAttoDaDepositare:17381",
            "oggetto",
            not _text(context.get("oggetto")),
        )
        _append(
            findings,
            "VerificaCampiAttoDaDepositare:17389",
            "codice_oggetto_pst",
            not _text(context.get("codice_oggetto_pst")),
        )

    if _enabled(controls, "txtRG"):
        rg = _text(context.get("numero_rg"))
        _append(findings, "VerificaCampiAttoDaDepositare:17409", "numero_rg", not rg)
        _append(findings, "VerificaCampiAttoDaDepositare:17417", "numero_rg", bool(rg) and not rg.isdigit())
    if _enabled(controls, "txtAnnoRuoloGen"):
        year = _text(context.get("anno_rg"))
        _append(findings, "VerificaCampiAttoDaDepositare:17436", "anno_rg", not year)
        _append(findings, "VerificaCampiAttoDaDepositare:17443", "anno_rg", bool(year) and not year.isdigit())
        _append(findings, "VerificaCampiAttoDaDepositare:17451", "anno_rg", bool(year) and len(year) != 4)
    cci = _text(extra.get("cci"))
    if _text(context.get("codice_registro")) == "ProcedimentoUnitario":
        _append(findings, "VerificaCampiAttoDaDepositare:17425", "cci", bool(cci) and not cci.isdigit())
    sub = _text(extra.get("sub_procedimento"))
    _append(findings, "VerificaCampiAttoDaDepositare:17459", "sub_procedimento", bool(sub) and not sub.isdigit())
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17467",
        "codice_registro",
        _enabled(controls, "cboRuolo", default=True) and not _text(context.get("codice_registro")),
    )
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17475",
        "rito",
        _enabled(controls, "cboRito") and not _text(extra.get("rito")),
    )

    role = _role_text(context)
    role_upper = role.upper()
    office_name = _text(
        resolver.get("effective_office_name")
        or resolver.get("official_office_name")
        or context.get("ufficio_giudiziario")
    ).upper()
    if "SICID" in key:
        _append(findings, "VerificaCampiAttoDaDepositare:17484", "codice_registro", "ESECUZION" in role_upper)
        _append(findings, "VerificaCampiAttoDaDepositare:17491", "codice_registro", "ESPROPRIAZION" in role_upper)
        _append(findings, "VerificaCampiAttoDaDepositare:17498", "codice_registro", "CONCORSUAL" in role_upper)
    if "SIECIC" in key:
        _append(findings, "VerificaCampiAttoDaDepositare:17505", "codice_registro", "CONTENZIOSO" in role_upper)
        _append(findings, "VerificaCampiAttoDaDepositare:17512", "codice_registro", "LAVORO" in role_upper)
        _append(findings, "VerificaCampiAttoDaDepositare:17519", "codice_registro", "AGRARIA" in role_upper)
        _append(findings, "VerificaCampiAttoDaDepositare:17526", "codice_registro", "SPECIALE" in role_upper)
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17533",
        "codice_registro",
        "PACE" in role_upper and "SIGP" not in key,
    )
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17540",
        "codice_registro",
        "CASSAZIONE" in office_name and "CASSAZIONE" not in role_upper,
    )
    _append(
        findings,
        "VerificaCampiAttoDaDepositare:17547",
        "codice_registro",
        "PACE" in office_name and "PACE" not in role_upper,
    )

    if _enabled(controls, "cboRiferimentoProvvedimento"):
        _append(findings, "VerificaCampiAttoDaDepositare:17556", "precedente_provvedimento_tipo", not _text(extra.get("precedente_provvedimento_tipo")))
    if _enabled(controls, "txtRiferimentoProvvedimentoNumero"):
        _append(findings, "VerificaCampiAttoDaDepositare:17564", "precedente_provvedimento_numero", not _text(extra.get("precedente_provvedimento_numero")))
    if _enabled(controls, "dtpDataPrecedenteProvvedimento"):
        previous_date = _text(extra.get("data_precedente_provvedimento"))
        _append(findings, "VerificaCampiAttoDaDepositare:17574", "data_precedente_provvedimento", not previous_date)
        _append(
            findings,
            "VerificaCampiAttoDaDepositare:17582",
            "data_precedente_provvedimento",
            bool(previous_date) and _date(previous_date) is None,
        )
    if _enabled(controls, "cboPrecedenteFascicolo"):
        _append(findings, "VerificaCampiAttoDaDepositare:17597", "precedente_fascicolo_ufficio", not _text(extra.get("precedente_fascicolo_ufficio")))
    if _enabled(controls, "txtPrecedenteFascicoloAnno"):
        previous_year = _text(extra.get("precedente_fascicolo_anno"))
        _append(findings, "VerificaCampiAttoDaDepositare:17608", "precedente_fascicolo_anno", not previous_year)
        _append(findings, "VerificaCampiAttoDaDepositare:17615", "precedente_fascicolo_anno", bool(previous_year) and not previous_year.isdigit())
        _append(findings, "VerificaCampiAttoDaDepositare:17623", "precedente_fascicolo_anno", bool(previous_year) and len(previous_year) != 4)
    if _enabled(controls, "txtPrecedenteFascicoloNumero"):
        _append(findings, "VerificaCampiAttoDaDepositare:17632", "precedente_fascicolo_numero", not _text(extra.get("precedente_fascicolo_numero")))
    if _enabled(controls, "dtpDataAttoDaDepositare"):
        missing_deposit_date = _date(extra.get("data_atto_deposito")) is None
        date_rule = (
            "VerificaCampiAttoDaDepositare:17644"
            if key == "Atti_UNEP::RichiestaRestituzioneSomme"
            else "VerificaCampiAttoDaDepositare:17648"
            if key.startswith("Atti_UNEP::")
            else "VerificaCampiAttoDaDepositare:17653"
        )
        _append(findings, date_rule, "data_atto_deposito", missing_deposit_date)
    if _enabled(controls, "cboIstanze"):
        instance_rule = (
            "VerificaCampiAttoDaDepositare:17754"
            if key.startswith("Atti_UNEP::")
            else "VerificaCampiAttoDaDepositare:17758"
        )
        _append(findings, instance_rule, "istanza", not _text(extra.get("istanza")))

    if "_SIGP::" in key:
        office = _text(resolver.get("effective_office_name") or context.get("ufficio_giudiziario")).upper()
        _append(findings, "VerificaCampiAttoDaDepositare:17364", "ufficio_giudiziario", bool(office) and "PACE" not in office)

    if key.startswith("Atti_UNEP::"):
        office = _text(resolver.get("effective_office_name") or context.get("ufficio_giudiziario")).upper()
        _append(findings, "VerificaCampiAttoDaDepositare:17372", "ufficio_giudiziario", bool(office) and not office.startswith("UNEP"))
        if _enabled(controls, "cboPrecedenteFascicolo"):
            _append(findings, "VerificaCampiAttoDaDepositare:17593", "unep_inoltro_ufficiale_giudiziario", not _text(extra.get("unep_inoltro_ufficiale_giudiziario")))
        if _visible(controls, "cboCodiciNaturaUNEP") and _enabled(
            controls,
            "cboCodiciNaturaUNEP",
            default=True,
        ):
            _append(findings, "VerificaCampiAttoDaDepositare:17675", "unep_natura_atto", not _text(extra.get("unep_natura_atto")))
            if "PagamentoRichiesta" not in key:
                _append(findings, "VerificaCampiAttoDaDepositare:17683", "unep_codice_natura", not _text(extra.get("unep_codice_natura")))
        if _visible(controls, "dataRichiestaNotificaUNEP"):
            _append(findings, "VerificaCampiAttoDaDepositare:17662", "unep_data_richiesta", _date(extra.get("unep_data_richiesta")) is None)
        if _visible(controls, "dataScadenzaNotificaUNEP"):
            _append(findings, "VerificaCampiAttoDaDepositare:17668", "unep_data_scadenza", _date(extra.get("unep_data_scadenza")) is None)
        if _visible(controls, "txtCodicePagamento"):
            payment_code_rule = (
                "VerificaCampiAttoDaDepositare:17693"
                if key == "Atti_UNEP::RichiestaRestituzioneSomme"
                else "VerificaCampiAttoDaDepositare:17696"
            )
            _append(
                findings,
                payment_code_rule,
                "unep_codice_pagamento",
                not _text(extra.get("unep_codice_pagamento")),
            )
        if _visible(controls, "txtRegistroUnep"):
            register = _text(extra.get("unep_registro_bilancio"))
            _append(findings, "VerificaCampiAttoDaDepositare:17706", "unep_registro_bilancio", not register)
            _append(findings, "VerificaCampiAttoDaDepositare:17712", "unep_registro_bilancio", bool(register) and register not in {"0", "1"})
        if _visible(controls, "txtAnnoUnep"):
            unep_year = _text(extra.get("unep_anno_bilancio"))
            _append(findings, "VerificaCampiAttoDaDepositare:17724", "unep_anno_bilancio", not unep_year)
            _append(
                findings,
                "VerificaCampiAttoDaDepositare:17731",
                "unep_anno_bilancio",
                bool(unep_year) and not unep_year.isdigit(),
            )
            _append(
                findings,
                "VerificaCampiAttoDaDepositare:17739",
                "unep_anno_bilancio",
                bool(unep_year) and unep_year.isdigit() and len(unep_year) != 4,
            )


def _validate_anagrafica(
    key: str,
    contract: dict[str, Any],
    context: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    professionista = _professionista(context)
    extra = _extra(context)
    controls = contract.get("controls") if isinstance(contract.get("controls"), dict) else {}
    role = _text(extra.get("professionista_ruolo") or professionista.get("ruolo"))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18401", "professionista_ruolo", not role)
    _append(findings, "VerificaCampiAnagraficaProcedimento:18417", "professionista_cognome", not _text(professionista.get("cognome")))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18425", "professionista_nome", not _text(professionista.get("nome")))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18433", "professionista_indirizzo", not _text(professionista.get("indirizzo")))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18441", "professionista_cap", not _text(professionista.get("cap")))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18449", "professionista_citta", not _text(professionista.get("citta")))
    cf = _text(professionista.get("codice_fiscale"))
    _append(findings, "VerificaCampiAnagraficaProcedimento:18476", "professionista_codice_fiscale", not cf)
    _append(findings, "VerificaCampiAnagraficaProcedimento:18485", "professionista_codice_fiscale", bool(cf) and not _valid_cf(cf))

    if role in {"SOLODIFENSORE", "SOLODOMICILIATARIO"}:
        other = extra.get("altri_difensori")
        _append(findings, "VerificaCampiAnagraficaProcedimento:18409", "altri_difensori", not isinstance(other, list) or not other)

    if _visible(controls, "txtPecProfessionista"):
        if key == "Atti_UNEP::RichiestaRestituzioneSomme":
            iban = _text(extra.get("unep_iban"))
            _append(findings, "VerificaCampiAnagraficaProcedimento:18511", "unep_iban", not iban)
            _append(findings, "VerificaCampiAnagraficaProcedimento:18524", "unep_iban", bool(iban) and not _valid_iban(iban))
        else:
            pec = _text(professionista.get("pec") or extra.get("professionista_pec"))
            _append(findings, "VerificaCampiAnagraficaProcedimento:18515", "professionista_pec", not pec)

    parties = _unep_parties(context) if key.startswith("Atti_UNEP::") else [item for item in context.get("parti") or [] if isinstance(item, dict)]
    if key in {
        "Parte_CASSAZIONE::Ricorso",
        "Parte_CASSAZIONE::ControRicorso",
        "Parte_CASSAZIONE::ControRicorsoIscrittoDalControricorrente",
        "Parte_CASSAZIONE::ControRicorsoIncidentale",
        "Parte_CASSAZIONE::ControRicorsoIncidentaleIscrittoDalControricorrente",
    }:
        for party in parties:
            if _text(party.get("natura_giuridica")) != "PFI" or _date(party.get("data_nascita")) is not None:
                continue
            is_counterparty = _text(party.get("ruolo")) in {"CONTROPARTE", "DEBITORE"}
            _append(
                findings,
                "VerificaCampiAnagraficaProcedimento:18574" if is_counterparty else "VerificaCampiAnagraficaProcedimento:18560",
                "parti",
                True,
            )

    domicile_keys = (
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoDebitore",
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi",
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoImmobiliare",
        "Atti_UNEP::RichiestaPignoramentoPressoTerzi",
        "Atti_UNEP::RichiestaPignoramentoImmobiliare",
    )
    if key.startswith(domicile_keys):
        missing_party = False
        missing_counterparty = False
        for party in parties:
            domicile = party.get("domicilio") if isinstance(party.get("domicilio"), dict) else {}
            missing = not _text(domicile.get("via")) and not _text(domicile.get("citta"))
            if not missing:
                continue
            if _text(party.get("ruolo")) in {"CONTROPARTE", "DEBITORE"}:
                missing_counterparty = True
            else:
                missing_party = True
        _append(findings, "VerificaCampiAnagraficaProcedimento:18629", "parti", missing_party)
        _append(findings, "VerificaCampiAnagraficaProcedimento:18638", "parti", missing_counterparty)

    if key.startswith(
        (
            "Introduttivi_SICID::RicorsoImmigrazioneConvalida",
            "Introduttivi_SICID::RicorsoReclamoSospensiva",
            "Introduttivi_SICID::RicorsoImmigrazione",
            "Introduttivi_SIGP::RicorsoImmigrazione",
        )
    ):
        _append(
            findings,
            "VerificaCampiAnagraficaProcedimento:18650",
            "codice_vestanet",
            not _text(extra.get("codice_vestanet")),
        )

    if key.startswith("Atti_UNEP::"):
        missing_notification_type = any(
            _text(party.get("ruolo")) in {"CONTROPARTE", "DEBITORE"}
            and not _text(party.get("tipo_notifica"))
            for party in parties
        )
        _append(findings, "VerificaCampiAnagraficaProcedimento:18675", "unep_destinatari", missing_notification_type)
    if key.startswith("Atti_UNEP::RichiestaPignoramento"):
        titles = [item for item in list(extra.get("unep_titoli") or []) if isinstance(item, dict)]
        procedenti = [
            party
            for party in parties
            if _text(party.get("gruppo")).casefold() == "parte"
            or _text(party.get("ruolo")).upper() in {"PARTE", "ASSISTITO", "CREDITORE", "INTERVENIENTE"}
        ]
        missing_title = False
        missing_title_type = False
        for position, party in enumerate(procedenti, start=1):
            party_id = _text(party.get("id")) or str(position)
            title = next((item for item in titles if _text(item.get("parte_id")) == party_id), None)
            if title is None and len(procedenti) == 1 and len(titles) == 1:
                title = titles[0]
            if title is None:
                missing_title = True
            elif not _text(title.get("fattispecie")):
                missing_title_type = True
        _append(findings, "VerificaCampiAnagraficaProcedimento:18603", "unep_titoli", missing_title)
        _append(findings, "VerificaCampiAnagraficaProcedimento:18617", "unep_titoli", missing_title_type)
    if key in {
        "Atti_UNEP::RichiestaPignoramentoMobiliareADebito",
        "Atti_UNEP::RichiestaPignoramentoMobiliare",
        "Atti_UNEP::RichiestaPignoramentoPressoTerziADebito",
        "Atti_UNEP::RichiestaPignoramentoPressoTerzi",
        "Atti_UNEP::RichiestaPignoramentoMobiliareMateriaLavoro",
        "Atti_UNEP::RichiestaPignoramentoPressoTerziMateriaLavoro",
    }:
        _append(
            findings,
            "VerificaCampiAnagraficaProcedimento:18706",
            "unep_beni",
            not list(extra.get("unep_beni") or []),
        )
    if key in {
        "Atti_UNEP::RichiestaPignoramentoImmobiliare",
        "Atti_UNEP::RichiestaPignoramentoImmobiliareADebito",
    }:
        _append(
            findings,
            "VerificaCampiAnagraficaProcedimento:18737",
            "unep_beni",
            not list(extra.get("unep_beni") or []),
        )


def _validate_contribution(
    key: str,
    contract: dict[str, Any],
    context: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    flags = contract.get("flags") if isinstance(contract.get("flags"), dict) else {}
    if not flags.get("needContributoUnificato"):
        return
    contribution = context.get("contributo_unificato")
    contribution = contribution if isinstance(contribution, dict) else {}
    mode = _text(contribution.get("mode"))
    amount = _number(contribution.get("importo"))
    missing_mode = mode in {"", "da_definire"}
    is_unep = key.startswith("Atti_UNEP::")
    _append(
        findings,
        "VerificaCampiIscrizioneRuolo:18781" if is_unep else "VerificaCampiIscrizioneRuolo:18785",
        "contributo_unificato",
        (amount is None or amount == 0) and missing_mode,
    )
    _append(
        findings,
        "VerificaCampiIscrizioneRuolo:18799" if is_unep else "VerificaCampiIscrizioneRuolo:18803",
        "contributo_unificato",
        amount not in {None, 0} and missing_mode,
    )
    _append(
        findings,
        "VerificaCampiIscrizioneRuolo:18811",
        "contributo_unificato",
        amount not in {None, 0} and not mode,
    )
    if mode == "pagato":
        _append(
            findings,
            "VerificaCampiIscrizioneRuolo:18821" if is_unep else "VerificaCampiIscrizioneRuolo:18825",
            "contributo_unificato",
            not contribution.get("payment_evidence"),
        )

    if flags.get("needValoreControversia"):
        controversy_value = _number(_extra(context).get("valore_controversia"))
        _append(
            findings,
            "VerificaCampiIscrizioneRuolo:18767",
            "valore_controversia",
            controversy_value is None,
        )

    extra = _extra(context)
    branches = (
        ("spese_integrazione_art13", "VerificaCampiIscrizioneRuolo:18837", "VerificaCampiIscrizioneRuolo:18846", "VerificaCampiIscrizioneRuolo:18861"),
        ("spese_diritti_art30", "VerificaCampiIscrizioneRuolo:18872", "VerificaCampiIscrizioneRuolo:18881", "VerificaCampiIscrizioneRuolo:18896"),
        ("spese_notifica_art34", "VerificaCampiIscrizioneRuolo:18907", "VerificaCampiIscrizioneRuolo:18916", "VerificaCampiIscrizioneRuolo:18931"),
    )
    controls = contract.get("controls") if isinstance(contract.get("controls"), dict) else {}
    for prefix, amount_rule, mode_rule, receipt_rule in branches:
        source_control = {
            "spese_integrazione_art13": "Importo_SpeseGiustiziaIntegrazione_69_2009_art_13_co_2_bis_tu",
            "spese_diritti_art30": "Importo_SpeseGiustiziaDiritti_registrazione_ruolo_tu_art_30",
            "spese_notifica_art34": "Importo_SpeseGiustiziaNotifica_avvocati_art_34_tu",
        }[prefix]
        if not _enabled(controls, source_control):
            continue
        amount = _number(extra.get(f"{prefix}_importo"))
        payment_mode = _text(extra.get(f"{prefix}_tipo_pagamento"))
        receipt = _text(extra.get(f"{prefix}_ricevuta"))
        exempt_mode = payment_mode in {"NonDovuto", "Esente", "ADebito"}
        _append(findings, amount_rule, f"{prefix}_importo", amount is None and not exempt_mode)
        _append(findings, mode_rule, f"{prefix}_tipo_pagamento", amount not in {None, 0} and not payment_mode)
        paid = payment_mode not in {"", "NonDovuto", "Esente", "ADebito"}
        _append(findings, receipt_rule, f"{prefix}_ricevuta", paid and not receipt)

    if is_unep:
        source_mode = {
            "non_dovuto": "NonDovuto",
            "esente": "Esente",
            "prenotato_a_debito": "ADebito",
            "pagato": "Pagato",
        }.get(mode, "")
        is_research = key == "Atti_UNEP::RichiestaRicercaBeni"
        cause_visible = is_research or source_mode in {"Esente", "ADebito"}
        if is_research and cause_visible:
            _append(findings, "VerificaCampiIscrizioneRuolo:18941", "unep_autorita_tipo", not _text(extra.get("unep_autorita_tipo")))
            _append(findings, "VerificaCampiIscrizioneRuolo:18949", "unep_autorita_sede", not _text(extra.get("unep_autorita_sede")))
            authorization_number = _text(extra.get("unep_autorizzazione_numero"))
            _append(findings, "VerificaCampiIscrizioneRuolo:18977", "unep_autorizzazione_numero", not authorization_number)
            _append(findings, "VerificaCampiIscrizioneRuolo:18984", "unep_autorizzazione_numero", bool(authorization_number) and not authorization_number.isdigit())
            _append(findings, "VerificaCampiIscrizioneRuolo:19018", "unep_autorizzazione_data", _date(extra.get("unep_autorizzazione_data")) is None)
            _append(findings, "VerificaCampiIscrizioneRuolo:19047", "unep_data_notifica_precetto", _date(extra.get("unep_data_notifica_precetto")) is None)
            _append(findings, "VerificaCampiIscrizioneRuolo:19055", "unep_importo_precetto", (_number(extra.get("unep_importo_precetto")) or 0) == 0)
        elif cause_visible:
            _append(findings, "VerificaCampiIscrizioneRuolo:18949", "unep_causa_ufficio", not _text(extra.get("unep_causa_ufficio")))
            cause_number = _text(extra.get("unep_causa_numero"))
            _append(findings, "VerificaCampiIscrizioneRuolo:18959", "unep_causa_numero", not cause_number)
            _append(findings, "VerificaCampiIscrizioneRuolo:18966", "unep_causa_numero", bool(cause_number) and not cause_number.isdigit())
            cause_sub = _text(extra.get("unep_causa_sub"))
            _append(findings, "VerificaCampiIscrizioneRuolo:18984", "unep_causa_sub", bool(cause_sub) and not cause_sub.isdigit())
            cause_year = _text(extra.get("unep_causa_anno"))
            _append(findings, "VerificaCampiIscrizioneRuolo:18995", "unep_causa_anno", not cause_year)
            _append(findings, "VerificaCampiIscrizioneRuolo:19002", "unep_causa_anno", bool(cause_year) and not cause_year.isdigit())
            _append(findings, "VerificaCampiIscrizioneRuolo:19010", "unep_causa_anno", bool(cause_year) and len(cause_year) != 4)
            _append(findings, "VerificaCampiIscrizioneRuolo:19018", "unep_causa_data_udienza", _date(extra.get("unep_causa_data_udienza")) is None)
        if source_mode == "ADebito" and key.endswith("Debito"):
            _append(findings, "VerificaCampiIscrizioneRuolo:19025", "unep_ente_debito", not _text(extra.get("unep_ente_debito")))
            _append(findings, "VerificaCampiIscrizioneRuolo:19032", "unep_numero_debito", not _text(extra.get("unep_numero_debito")))
            _append(findings, "VerificaCampiIscrizioneRuolo:19039", "unep_data_debito", _date(extra.get("unep_data_debito")) is None)


def _validate_cassazione(key: str, context: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    extra = _extra(context)
    _append(findings, "VerificaCampiIntroduttiviCassazione:17958", "tipo_ricorso_cassazione", not _text(extra.get("tipo_ricorso_cassazione")))
    _append(findings, "VerificaCampiIntroduttiviCassazione:17966", "parole_chiave_cassazione", not _text(extra.get("parole_chiave_cassazione")))
    first = _date(extra.get("data_richiesta_notifica_cassazione"))
    last = _date(extra.get("data_effettiva_notifica_cassazione"))
    today = date.today()
    _append(findings, "VerificaCampiIntroduttiviCassazione:17974", "data_richiesta_notifica_cassazione", first is None)
    _append(findings, "VerificaCampiIntroduttiviCassazione:17982", "data_richiesta_notifica_cassazione", first is not None and first > today)
    _append(findings, "VerificaCampiIntroduttiviCassazione:17990", "data_effettiva_notifica_cassazione", last is None)
    _append(findings, "VerificaCampiIntroduttiviCassazione:17998", "data_effettiva_notifica_cassazione", last is not None and last > today)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18008", "data_effettiva_notifica_cassazione", first is not None and last is not None and last < first)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18019", "data_effettiva_notifica_cassazione", last is not None and last < today - timedelta(days=20))
    first_year = _text(extra.get("inizio_primo_grado_anno"))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18030", "inizio_primo_grado_anno", not first_year)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18037", "inizio_primo_grado_anno", bool(first_year) and not first_year.isdigit())
    _append(findings, "VerificaCampiIntroduttiviCassazione:18045", "inizio_primo_grado_anno", bool(first_year) and len(first_year) != 4)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18053", "inizio_primo_grado_ufficio", not _text(extra.get("inizio_primo_grado_ufficio")))
    provvedimento = extra.get("provvedimento_impugnato")
    provvedimento = provvedimento if isinstance(provvedimento, dict) else {}
    _append(findings, "VerificaCampiIntroduttiviCassazione:18059", "provvedimento_impugnato", not _text(provvedimento.get("natura")))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18065", "provvedimento_impugnato", not _text(provvedimento.get("numero")))
    decision_year = _text(provvedimento.get("anno"))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18071", "provvedimento_impugnato", not decision_year)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18077", "provvedimento_impugnato", not _text(provvedimento.get("tipo")))
    deposit_date = _date(provvedimento.get("data_deposito"))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18083", "provvedimento_impugnato", deposit_date is None)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18091", "provvedimento_impugnato", deposit_date is not None and deposit_date > today)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18097", "provvedimento_impugnato", not _text(provvedimento.get("ufficio")))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18103", "provvedimento_impugnato", not _text(provvedimento.get("numero_fascicolo")))
    file_year = _text(provvedimento.get("anno_fascicolo"))
    _append(findings, "VerificaCampiIntroduttiviCassazione:18109", "provvedimento_impugnato", not file_year)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18115", "provvedimento_impugnato", bool(file_year) and not file_year.isdigit())
    _append(findings, "VerificaCampiIntroduttiviCassazione:18121", "provvedimento_impugnato", bool(file_year) and len(file_year) != 4)
    _append(findings, "VerificaCampiIntroduttiviCassazione:18127", "provvedimento_impugnato", not _text(provvedimento.get("ruolo")))
    reasons = list(extra.get("motivi_cassazione") or [])
    counter_reasons = list(extra.get("contromotivi_cassazione") or [])
    _append(findings, "VerificaCampiIntroduttiviCassazione:18135", "motivi_cassazione", not reasons and not counter_reasons)
    if key in {
        "Parte_CASSAZIONE::ControRicorsoIncidentale",
        "Parte_CASSAZIONE::ControRicorsoIncidentaleIscrittoDalControricorrente",
    }:
        _append(findings, "VerificaCampiIntroduttiviCassazione:18158", "motivi_cassazione", not reasons or not counter_reasons)


def _validate_execution(key: str, context: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    extra = _extra(context)
    _append(findings, "VerificaCampiProcessoEsecutivo:19083", "importo_precetto", (_number(extra.get("importo_precetto")) or 0) <= 0)
    _append(findings, "VerificaCampiProcessoEsecutivo:19090", "data_pignoramento", _date(extra.get("data_pignoramento")) is None)
    _append(findings, "VerificaCampiProcessoEsecutivo:19097", "data_consegna_pignoramento", _date(extra.get("data_consegna_pignoramento")) is None)
    if "MobiliarePressoTerzi" in key:
        _append(findings, "VerificaCampiProcessoEsecutivo:19104", "data_notifica_pignoramento", _date(extra.get("data_notifica_pignoramento")) is None)
        _append(findings, "VerificaCampiProcessoEsecutivo:19111", "data_citazione", _date(extra.get("data_citazione")) is None)
    if "MobiliarePressoDebitore" in key:
        custode = extra.get("custode") if isinstance(extra.get("custode"), dict) else {}
        _append(findings, "VerificaCampiProcessoEsecutivo:19118", "custode", not _text(custode.get("codice_fiscale")))
        _append(findings, "VerificaCampiProcessoEsecutivo:19125", "custode", not _text(custode.get("cognome")))


def _validate_succession(context: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    extra = _extra(context)
    checks = (
        ("successione_parte_istante", "VerificaCampiEreditàSuccessioni:19149"),
        ("successione_parte_agisce", "VerificaCampiEreditàSuccessioni:19155"),
        ("successione_tipo_atto", "VerificaCampiEreditàSuccessioni:19161"),
        ("defunto_cognome", "VerificaCampiEreditàSuccessioni:19168"),
        ("defunto_nome", "VerificaCampiEreditàSuccessioni:19175"),
        ("defunto_codice_fiscale", "VerificaCampiEreditàSuccessioni:19182"),
        ("testamento_tipo", "VerificaCampiEreditàSuccessioni:19212"),
    )
    for field, rule_id in checks:
        _append(findings, rule_id, field, not _text(extra.get(field)))
    cf = _text(extra.get("defunto_codice_fiscale"))
    _append(findings, "VerificaCampiEreditàSuccessioni:19195", "defunto_codice_fiscale", bool(cf) and not _valid_cf(cf))


def _validate_occ(context: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    extra = _extra(context)
    checks = (
        ("organo_crisi_tipo", "VerificaCampiTipoOrgano:19238"),
        ("organo_crisi_natura_giuridica", "VerificaCampiTipoOrgano:19245"),
        ("organo_crisi_denominazione", "VerificaCampiTipoOrgano:19252"),
        ("organo_crisi_codice_fiscale", "VerificaCampiTipoOrgano:19259"),
    )
    for field, rule_id in checks:
        _append(findings, rule_id, field, not _text(extra.get(field)))
    cf = _text(extra.get("organo_crisi_codice_fiscale"))
    _append(findings, "VerificaCampiTipoOrgano:19267", "organo_crisi_codice_fiscale", bool(cf) and not _valid_cf(cf))
    if extra.get("occ_referente_presente"):
        ref_checks = (
            ("occ_referente_qualifica", "VerificaCampiTipoOrgano:19276"),
            ("occ_referente_natura_giuridica", "VerificaCampiTipoOrgano:19283"),
            ("occ_referente_denominazione", "VerificaCampiTipoOrgano:19290"),
            ("occ_referente_codice_fiscale", "VerificaCampiTipoOrgano:19297"),
        )
        for field, rule_id in ref_checks:
            _append(findings, rule_id, field, not _text(extra.get(field)))
        ref_cf = _text(extra.get("occ_referente_codice_fiscale"))
        _append(findings, "VerificaCampiTipoOrgano:19305", "occ_referente_codice_fiscale", bool(ref_cf) and not _valid_cf(ref_cf))


def validate_studio_telematico_deposit(
    *,
    key: str,
    context: dict[str, Any],
    selected_documents: Iterable[dict[str, Any]],
    resolver: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Esegue solo i metodi associati al tipo nel contratto estratto."""

    contract = studio_telematico_type_contract(key)
    if not contract:
        return []
    methods = set(contract.get("validation_methods") or [])
    findings: list[dict[str, Any]] = []
    _validate_documents(key, context, selected_documents, findings)
    _validate_atto(key, contract, context, resolver or {}, findings)
    if "VerificaCampiAnagraficaProcedimento" in methods:
        _validate_anagrafica(key, contract, context, findings)
    if "VerificaCampiIscrizioneRuolo" in methods:
        _validate_contribution(key, contract, context, findings)
    if "VerificaCampiIntroduttiviCassazione" in methods:
        _validate_cassazione(key, context, findings)
    if "VerificaCampiProcessoEsecutivo" in methods:
        _validate_execution(key, context, findings)
    if "VerificaCampiEreditàSuccessioni" in methods:
        _validate_succession(context, findings)
    if "VerificaCampiTipoOrgano" in methods:
        _validate_occ(context, findings)
    if "VerificaCampiSanzioniGDP" in methods:
        _append(
            findings,
            "VerificaCampiSanzioniGDP:18185",
            "sanzioni_gdp",
            not list(_extra(context).get("sanzioni_gdp") or []),
        )
    allowed_ids = set(contract.get("validation_rule_ids") or [])
    return [
        finding
        for finding in findings
        if finding["rule_id"] in allowed_ids
        and finding["rule_id"] not in FOLLOW_UP_MESSAGE_RULE_IDS
    ]
