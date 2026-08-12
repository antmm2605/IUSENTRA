"""Generatore DatiAtto.xml UNEP conforme al flusso Studio Telematico."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from lxml import etree


ROOT_NS = "http://schemi.processotelematico.giustizia.it/unep/atti/parte/v1"
ATTI_NS = "http://schemi.processotelematico.giustizia.it/unep/tipi/atti/v1"
ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/unep/tipi/anagrafiche"
ALLEGATI_NS = "http://schemi.processotelematico.giustizia.it/unep/tipi/allegati/v1"
TIPI_NS = "http://schemi.processotelematico.giustizia.it/unep/tipi"
BASE_UNEP_NS = "http://schemi.processotelematico.giustizia.it/unep/tipiBaseUnep"
SIECIC_NS = "http://schemi.processotelematico.giustizia.it/unep/siecic/tipibase"

_TIPI_NOTIFICA = {"Mani", "Posta", "Estero", "Telematica"}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _required(value: Any, label: str) -> str:
    clean = _text(value)
    if not clean:
        raise ValueError(f"Dato UNEP mancante: {label}.")
    return clean


def _date(value: Any, label: str) -> str:
    clean = _required(value, label)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Data UNEP non valida per {label}.")


def _money(value: Any, label: str, *, default_zero: bool = False) -> str:
    clean = _text(value).replace("€", "").replace(" ", "")
    if not clean and default_zero:
        return "0.00"
    clean = clean.replace(".", "").replace(",", ".") if "," in clean else clean
    try:
        return f"{Decimal(clean):.2f}"
    except (InvalidOperation, ValueError):
        raise ValueError(f"Importo UNEP non valido per {label}.") from None


def _xml_id(value: Any, prefix: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", _text(value)).strip("_.-")
    if not clean:
        clean = prefix
    if not re.match(r"[A-Za-z_]", clean):
        clean = f"{prefix}_{clean}"
    return clean


def _q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _node(parent: etree._Element, namespace: str, name: str, value: Any = None, **attrs: str) -> etree._Element:
    child = etree.SubElement(parent, _q(namespace, name), **attrs)
    if value is not None:
        child.text = _text(value)
    return child


def _address(parent: etree._Element, name: str, data: dict[str, Any], *, namespace: str = ROOT_NS) -> etree._Element:
    address = _node(parent, namespace, name)
    _node(address, ANAGRAFICHE_NS, "via", data.get("via"))
    civico = _text(data.get("civico"))
    if civico:
        _node(address, ANAGRAFICHE_NS, "civico", civico)
    _node(address, ANAGRAFICHE_NS, "cap", data.get("cap"))
    _node(address, ANAGRAFICHE_NS, "localita", data.get("citta") or data.get("localita"))
    _node(address, ANAGRAFICHE_NS, "provincia", data.get("provincia"))
    _node(address, ANAGRAFICHE_NS, "nazione", data.get("nazione"))
    return address


def _surname(data: dict[str, Any]) -> str:
    return _required(data.get("cognome") or data.get("denominazione"), "cognome o denominazione")


def _party_with_flat_address(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("indirizzo"), dict):
        return data
    return {
        **data,
        "indirizzo": {
            "via": data.get("via"),
            "civico": data.get("civico"),
            "cap": data.get("cap"),
            "localita": data.get("localita") or data.get("citta"),
            "provincia": data.get("provincia"),
            "nazione": data.get("nazione"),
        },
    }


def _subject(parent: etree._Element, data: dict[str, Any], *, address: bool, address_name: str = "indirizzo") -> None:
    _node(parent, ANAGRAFICHE_NS, "cognome", _surname(data))
    nome = _text(data.get("nome"))
    if nome:
        _node(parent, ANAGRAFICHE_NS, "nome", nome)
    _node(parent, ANAGRAFICHE_NS, "codiceFiscale", _required(data.get("codice_fiscale"), "codice fiscale"))
    if address:
        _address(parent, address_name, dict(data.get("indirizzo") or {}))


def _party(parent: etree._Element, data: dict[str, Any], *, party_id: str, forced_nature: str = "") -> None:
    parent.set("naturaGiuridica", forced_nature or _required(data.get("natura_giuridica"), "natura giuridica"))
    parent.set("ID", party_id)
    _node(parent, ANAGRAFICHE_NS, "denominazione", _surname(data))
    nome = _text(data.get("nome"))
    if nome:
        _node(parent, ANAGRAFICHE_NS, "nome", nome)
    cf = _text(data.get("codice_fiscale"))
    if cf:
        _node(parent, ANAGRAFICHE_NS, "codiceFiscale", cf)
    _address(parent, "indirizzo", dict(data.get("indirizzo") or {}), namespace=ANAGRAFICHE_NS)


def _split_parties(dati: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    extra = dict(getattr(dati, "datiatto_extra", {}) or {})
    changes = {
        _text(item.get("id")): item
        for item in list(extra.get("unep_destinatari") or [])
        if isinstance(item, dict) and _text(item.get("id"))
    }
    parties: list[dict[str, Any]] = []
    for raw in list(getattr(dati, "parti", []) or []):
        if not isinstance(raw, dict):
            continue
        party = dict(raw)
        party.update(changes.get(_text(raw.get("id")), {}))
        parties.append(party)
    procedenti = [item for item in parties if _text(item.get("gruppo")).casefold() == "parte"]
    debitori = [item for item in parties if _text(item.get("gruppo")).casefold() == "controparte"]
    terzi = [
        item
        for item in parties
        if _text(item.get("ruolo")).upper() in {"TERZO", "TERZO_PIGNORATO", "TERZO PIGNORATO"}
    ]
    if not procedenti:
        raise ValueError("Dato UNEP mancante: parte istante o procedente.")
    if not debitori:
        raise ValueError("Dato UNEP mancante: destinatario o debitore.")
    return procedenti, debitori, terzi


def _professional(dati: Any) -> dict[str, Any]:
    professional = dict(getattr(dati, "professionista", {}) or {})
    _required(professional.get("cognome"), "cognome dell'avvocato")
    _required(professional.get("codice_fiscale"), "codice fiscale dell'avvocato")
    return professional


def _destination(parent: etree._Element, dati: Any, *, role: str, rite: str = "") -> None:
    attrs = {"ufficio": _required(getattr(dati, "codice_ufficio", ""), "ufficio UNEP"), "ruolo": role}
    if rite:
        attrs["rito"] = rite
    _node(parent, ATTI_NS, "destinazione", **attrs)


def _contribution(parent: etree._Element, mode: str, amount: float) -> None:
    if mode not in {"pagato", "prenotato_a_debito"}:
        return
    contribution = _node(parent, ATTI_NS, "ContributoUnificato")
    attrs = {"debito": "true"} if mode == "prenotato_a_debito" else {}
    _node(contribution, ATTI_NS, "Importo", f"{amount:.2f}", **attrs)


def _index(parent: etree._Element, parts: Iterable[Any]) -> None:
    items = list(parts)
    main = next((part for part in items if bool(getattr(part, "is_main", False))), None)
    if main is None:
        raise ValueError("Atto principale mancante nell'indice UNEP.")
    index = _node(parent, ATTI_NS, "IndiceBusta")
    _node(index, ALLEGATI_NS, "AttoPrincipale", id=_required(getattr(main, "content_id", ""), "ID atto principale"))
    for part in items:
        if part is main:
            continue
        role = _text(getattr(part, "ruolo_indice", "")) or "AllegatoSemplice"
        if role == "ProcuraLiti":
            role = "AllegatoSemplice"
        _node(index, ALLEGATI_NS, role, id=_required(getattr(part, "content_id", ""), "ID allegato"))


def _intro_base(
    root: etree._Element,
    dati: Any,
    parts: Iterable[Any],
    *,
    role: str,
    rite: str = "",
    contribution_mode: str,
    contribution_amount: float,
    value_cause: bool = False,
) -> None:
    _destination(root, dati, role=role, rite=rite)
    _node(root, ATTI_NS, "Oggetto", _required(getattr(dati, "oggetto", ""), "codice oggetto UNEP"))
    if value_cause:
        _node(root, ATTI_NS, "ValoreCausa", f"{float(getattr(dati, 'valore_causa', 0) or 0):.2f}")
    _contribution(root, contribution_mode, contribution_amount)
    _index(root, parts)


def _atto_unep_base(root: etree._Element, dati: Any, parts: Iterable[Any], *, role: str, rite: str = "") -> None:
    _destination(root, dati, role=role, rite=rite)
    _index(root, parts)


def _dati_fascicolo(parent: etree._Element, extra: dict[str, Any], *, role: str, rite: str) -> None:
    proceeding = _node(
        parent,
        ATTI_NS,
        "Procedimento",
        ufficio=_required(extra.get("unep_causa_ufficio"), "ufficio del procedimento UNEP"),
        ruolo=role,
        rito=rite,
    )
    number_attrs: dict[str, str] = {}
    if _text(extra.get("unep_causa_sub")):
        number_attrs["sub"] = _text(extra.get("unep_causa_sub"))
    if _text(extra.get("unep_causa_cci")):
        number_attrs["numeroCCI"] = _text(extra.get("unep_causa_cci"))
    _node(proceeding, ATTI_NS, "numero", _required(extra.get("unep_causa_numero"), "numero del procedimento UNEP"), **number_attrs)
    _node(proceeding, ATTI_NS, "anno", _required(extra.get("unep_causa_anno"), "anno del procedimento UNEP"))
    _node(parent, ATTI_NS, "DataUdienza", _date(extra.get("unep_causa_data_udienza"), "data udienza UNEP"))


def _tipo_richiesta_notifica(root: etree._Element, key: str, extra: dict[str, Any]) -> None:
    wrapper = _node(root, ATTI_NS, "TipoRichiesta")
    if key.endswith("AttoCivileAPagamento"):
        _node(wrapper, ATTI_NS, "AttoCivile")
    elif key.endswith("AttoPenaleAPagamento"):
        _node(wrapper, ATTI_NS, "AttoPenale")
    elif key.endswith("AttoEsenteLavoro"):
        branch = _node(wrapper, ATTI_NS, "AttoEsenteLavoro")
        _dati_fascicolo(branch, extra, role="Lavoro", rite="AttoCivileEsenteLavoro")
    elif key.endswith("AttoCivileDebito"):
        branch = _node(wrapper, ATTI_NS, "AttoCivileDebito")
        _dati_fascicolo(branch, extra, role="Notifiche", rite="AttoCivileDebito")
    elif key.endswith("AttoPenaleDebito"):
        branch = _node(wrapper, ATTI_NS, "AttoPenaleDebito")
        _dati_fascicolo(branch, extra, role="Notifiche", rite="AttoPenaleDebito")
    else:
        raise ValueError(f"Tipo richiesta UNEP non riconosciuto: {key}.")


def _notification_rite(key: str) -> str:
    return {
        "Atti_UNEP::AttoCivileAPagamento": "AttoCivileAPagamento",
        "Atti_UNEP::AttoPenaleAPagamento": "AttoPenaleAPagamento",
        "Atti_UNEP::AttoEsenteLavoro": "AttoCivileEsenteLavoro",
        "Atti_UNEP::AttoCivileDebito": "AttoCivileDebito",
        "Atti_UNEP::AttoPenaleDebito": "AttoPenaleDebito",
    }[key]


def _urgency(root: etree._Element, extra: dict[str, Any]) -> None:
    urgent = bool(extra.get("unep_urgente"))
    label = _required(extra.get("unep_urgenza_testo"), "descrizione urgenza") if urgent else "NON URGENTE"
    code = _required(extra.get("unep_urgenza_codice"), "codice urgenza") if urgent else "1"
    _node(root, ROOT_NS, "Urgenza", label, codiceUrgenza=code)


def _notification(dati: Any, parts: Iterable[Any], mode: str, amount: float, *, debt: bool) -> etree._Element:
    key = _text(dati.datiatto_catalog_key)
    extra = dict(dati.datiatto_extra or {})
    procedenti, destinatari, _ = _split_parties(dati)
    professional = _professional(dati)
    root_name = "RichiestaParteDebito" if debt else "RichiestaParte"
    root = _root(root_name)
    _intro_base(
        root,
        dati,
        parts,
        role="Notifiche",
        rite=_notification_rite(key),
        contribution_mode=mode,
        contribution_amount=amount,
        value_cause=True,
    )
    _node(root, ROOT_NS, "DataRichiesta", _date(extra.get("unep_data_richiesta"), "data richiesta"))
    if _text(extra.get("unep_data_scadenza")):
        _node(root, ROOT_NS, "DataScadenza", _date(extra.get("unep_data_scadenza"), "data scadenza"))
    if debt:
        _node(root, ROOT_NS, "EntitaConcedenteDebito", _required(extra.get("unep_ente_debito"), "ente concedente il debito"))
        _node(root, ROOT_NS, "DataConcessioneDebito", _date(extra.get("unep_data_debito"), "data concessione a debito"))
        _node(root, ROOT_NS, "NumeroConcessioneDebito", _required(extra.get("unep_numero_debito"), "numero concessione a debito"))
    istante = _node(root, ROOT_NS, "Istante")
    _subject(istante, procedenti[0], address=True)
    lawyer = _node(root, ROOT_NS, "Avvocato")
    lawyer_data = {**professional, "indirizzo": professional}
    _subject(lawyer, lawyer_data, address=True)
    _tipo_richiesta_notifica(root, key, extra)
    for position, party in enumerate(destinatari, start=1):
        notice_type = _required(party.get("tipo_notifica"), f"tipo notifica di {_surname(party)}")
        if notice_type not in _TIPI_NOTIFICA:
            raise ValueError(f"Tipo notifica UNEP non valido per {_surname(party)}.")
        nature = _text(party.get("natura_giuridica"))
        recipient = _node(
            root,
            ROOT_NS,
            "Destinatario",
            progDestinatario=str(position),
            tipoNotifica=notice_type,
            PubbAmm="true" if nature == "PAM" else "false",
            PersonaFisica="true" if nature == "PFI" else "false",
        )
        _subject(recipient, party, address=True)
    _node(
        root,
        ROOT_NS,
        "NaturaAtto",
        _required(extra.get("unep_natura_atto"), "natura dell'atto UNEP"),
        codiceNatura=_required(extra.get("unep_codice_natura"), "codice natura UNEP"),
    )
    _urgency(root, extra)
    return root


def _right(parent: etree._Element, raw: dict[str, Any]) -> None:
    attrs = {"quota": _required(raw.get("quota"), "quota del diritto reale")}
    if _text(raw.get("stato")):
        attrs["stato"] = _text(raw.get("stato"))
    if _text(raw.get("stima")):
        attrs["stima"] = _money(raw.get("stima"), "stima del diritto reale")
    _node(parent, ROOT_NS, "dirittiReali", _required(raw.get("tipo"), "tipo del diritto reale"), **attrs)


def _assets(root: etree._Element, extra: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    raw_assets = [item for item in list(extra.get("unep_beni") or []) if isinstance(item, dict)]
    if not raw_assets:
        raise ValueError("Dato UNEP mancante: beni da pignorare.")
    wrapper = _node(root, ROOT_NS, "Beni")
    references: list[tuple[str, list[dict[str, Any]]]] = []
    for position, raw in enumerate(raw_assets, start=1):
        asset_id = _xml_id(raw.get("id") or position, "bene")
        rights = [item for item in list(raw.get("diritti") or []) if isinstance(item, dict)]
        if not rights:
            raise ValueError(f"Dato UNEP mancante: diritti reali del bene {position}.")
        kind = _text(raw.get("tipo")).casefold()
        if kind in {"immobile", "bene_immobile"}:
            asset = _node(wrapper, SIECIC_NS, "beneImmobile", ID=asset_id)
            _node(asset, SIECIC_NS, "descrizione", _required(raw.get("descrizione"), "descrizione bene immobile"))
            _address(asset, "indirizzo", dict(raw.get("indirizzo") or {}), namespace=SIECIC_NS)
            _node(asset, SIECIC_NS, "catasto", _required(raw.get("catasto"), "catasto bene immobile"))
            cadastral = _node(asset, SIECIC_NS, "datiCatastali")
            cadastral_data = dict(raw.get("dati_catastali") or {})
            _node(cadastral, SIECIC_NS, "sezione", _required(cadastral_data.get("sezione"), "sezione catastale"))
            _node(cadastral, SIECIC_NS, "foglio", _required(cadastral_data.get("foglio"), "foglio catastale"))
            _node(cadastral, SIECIC_NS, "particella", _required(cadastral_data.get("particella"), "particella catastale"))
            for field in ("subparticella", "subalterno", "subalterno2", "graffato"):
                if _text(cadastral_data.get(field)):
                    _node(cadastral, SIECIC_NS, field, cadastral_data.get(field))
            _node(
                asset,
                SIECIC_NS,
                "classe",
                _required(raw.get("classe"), "classe del bene immobile"),
                classato="true" if bool(raw.get("classato", True)) else "false",
            )
        else:
            asset = _node(wrapper, SIECIC_NS, "beneMobile", ID=asset_id)
            _node(asset, SIECIC_NS, "tipologia", _required(raw.get("tipologia"), "tipologia bene mobile"))
            _node(asset, SIECIC_NS, "descrizione", _required(raw.get("descrizione"), "descrizione bene mobile"))
            if isinstance(raw.get("ubicazione"), dict):
                _address(asset, "ubicazione", dict(raw["ubicazione"]), namespace=SIECIC_NS)
            _node(asset, SIECIC_NS, "valoreBene", _money(raw.get("valore"), "valore bene mobile", default_zero=True))
        references.append((asset_id, rights))
    return references


def _title(root: etree._Element, raw: dict[str, Any], *, party_id: str, debtor_tax_codes: list[str]) -> None:
    title = _node(root, ROOT_NS, "Titolo", ref=party_id)
    executive = str(raw.get("fattispecie") or "").casefold() in {"titolo esecutivo", "esecutivo"} or bool(raw.get("esecutivo"))
    if executive:
        detail = _node(title, SIECIC_NS, "titoloEsecutivo", tipologia=_required(raw.get("tipologia"), "tipologia titolo esecutivo"))
        _node(detail, SIECIC_NS, "descrizione", _required(raw.get("descrizione"), "descrizione titolo esecutivo"))
        if _text(raw.get("numero")):
            _node(detail, SIECIC_NS, "numero", raw.get("numero"))
        emission = _text(raw.get("data_emissione"))
        if not emission:
            emission = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        _node(detail, SIECIC_NS, "dataEmissione", _date(emission, "data emissione titolo"))
    else:
        _node(title, SIECIC_NS, "titoloNonEsecutivo", tipologia=_required(raw.get("tipologia"), "tipologia titolo non esecutivo"))
    for tax_code in debtor_tax_codes:
        _node(title, SIECIC_NS, "debitore", codiceFiscale=tax_code)


def _pignoramento(dati: Any, parts: Iterable[Any], mode: str, amount: float, *, debt: bool) -> etree._Element:
    key = _text(dati.datiatto_catalog_key)
    extra = dict(dati.datiatto_extra or {})
    procedenti, debitori, terzi = _split_parties(dati)
    professional = _professional(dati)
    root = _root("RichiestaPignoramentoDebito" if debt else "RichiestaPignoramento")
    labor = mode == "esente"
    debt_mode = mode == "prenotato_a_debito"
    rite = "EsecuzioniLavoro" if labor else "EsecuzioniDebito" if debt_mode else "Esecuzioni"
    _intro_base(
        root,
        dati,
        parts,
        role="EsecuzioniCivili",
        rite=rite,
        contribution_mode=mode,
        contribution_amount=amount,
    )
    _node(root, ROOT_NS, "inoltroUG", _required(extra.get("unep_inoltro_ufficiale_giudiziario"), "ufficio giudiziario di inoltro"))
    party_ids: dict[str, str] = {}
    for position, party in enumerate(procedenti, start=1):
        party_id = _xml_id(party.get("id") or position, "procedente")
        party_ids[_text(party.get("id")) or str(position)] = party_id
        claimant = _node(root, ROOT_NS, "Procedente")
        _party(claimant, party, party_id=party_id)
        lawyer = _node(claimant, ROOT_NS, "Avvocato")
        _subject(lawyer, professional, address=False)
        _address(claimant, "domicilio", dict(party.get("domicilio") or {}))
    if debt:
        _node(root, ROOT_NS, "EntitaConcedenteDebito", _required(extra.get("unep_ente_debito"), "ente concedente il debito"))
        _node(root, ROOT_NS, "DataConcessioneDebito", _date(extra.get("unep_data_debito"), "data concessione a debito"))
        _node(root, ROOT_NS, "NumeroConcessioneDebito", _required(extra.get("unep_numero_debito"), "numero concessione a debito"))
    _node(root, ROOT_NS, "ImportoPrecetto", _money(extra.get("unep_importo_precetto"), "importo del precetto", default_zero=True))
    debtor_tax_codes: list[str] = []
    debtor_nodes: list[etree._Element] = []
    for position, party in enumerate(debitori, start=1):
        notice_type = _required(party.get("tipo_notifica"), f"tipo notifica di {_surname(party)}")
        if notice_type not in _TIPI_NOTIFICA:
            raise ValueError(f"Tipo notifica UNEP non valido per {_surname(party)}.")
        debtor = _node(root, ROOT_NS, "Debitore", tipoNotifica=notice_type)
        _party(debtor, party, party_id=_xml_id(party.get("id") or position, "debitore"), forced_nature="PFI")
        _address(debtor, "Domicilio", dict(party.get("domicilio") or {}))
        _node(debtor, ROOT_NS, "formaSocietaria", "N/A")
        _node(debtor, ROOT_NS, "dataNotificaPrecetto", _date(party.get("data_notifica_precetto"), f"data notifica precetto di {_surname(party)}"))
        debtor_nodes.append(debtor)
        debtor_tax_codes.append(_required(party.get("codice_fiscale"), f"codice fiscale di {_surname(party)}"))
    asset_refs = _assets(root, extra)
    for debtor in debtor_nodes:
        insert_at = len(debtor)
        for asset_id, rights in asset_refs:
            item = etree.Element(_q(ROOT_NS, "benePignorato"), refBene=asset_id)
            for raw_right in rights:
                _right(item, raw_right)
            debtor.insert(insert_at, item)
            insert_at += 1
    if key in {
        "Atti_UNEP::RichiestaPignoramentoPressoTerzi",
        "Atti_UNEP::RichiestaPignoramentoPressoTerziMateriaLavoro",
        "Atti_UNEP::RichiestaPignoramentoPressoTerziADebito",
    }:
        if not terzi:
            terzi = [
                _party_with_flat_address(item)
                for item in list(extra.get("unep_terzi") or [])
                if isinstance(item, dict)
            ]
        for position, party in enumerate(terzi, start=1):
            third = _node(root, ROOT_NS, "TerzoPignorato")
            _party(third, party, party_id=_xml_id(party.get("id") or position, "terzo"), forced_nature="PFI")
    titles = [item for item in list(extra.get("unep_titoli") or []) if isinstance(item, dict)]
    for position, party in enumerate(procedenti, start=1):
        party_key = _text(party.get("id")) or str(position)
        raw_title = next((item for item in titles if _text(item.get("parte_id")) == party_key), None)
        if raw_title is None and len(procedenti) == 1 and len(titles) == 1:
            raw_title = titles[0]
        if raw_title is None:
            raise ValueError(f"Dato UNEP mancante: titolo di {_surname(party)}.")
        _title(root, raw_title, party_id=party_ids[party_key], debtor_tax_codes=debtor_tax_codes)
    request = _node(root, ATTI_NS, "TipoRichiestaPign")
    if labor or debt_mode:
        branch_name = "EsecuzioneEsenteLavoro" if labor else "EsecuzioneDebito"
        branch = _node(request, ATTI_NS, branch_name)
        _dati_fascicolo(branch, extra, role="EsecuzioniCivili", rite=rite)
    else:
        _node(request, ATTI_NS, "Esecuzione")
    _node(root, ROOT_NS, "NaturaAtto", codiceNatura="1")
    _urgency(root, extra)
    return root


def _ricerca_beni(dati: Any, parts: Iterable[Any], mode: str, amount: float) -> etree._Element:
    extra = dict(dati.datiatto_extra or {})
    procedenti, debitori, _ = _split_parties(dati)
    professional = _professional(dati)
    root = _root("RichiestaRicercaBeni")
    _intro_base(
        root,
        dati,
        parts,
        role="EsecuzioniCivili",
        rite="RichiestaRicercaBeni",
        contribution_mode=mode,
        contribution_amount=amount,
    )
    authorization_date = _date(extra.get("unep_autorizzazione_data"), "data autorizzazione ricerca beni")
    _node(root, ROOT_NS, "DataAutorizzazione", authorization_date)
    _node(
        root,
        ROOT_NS,
        "NumeroAutorizzazione",
        _required(extra.get("unep_autorizzazione_numero"), "numero autorizzazione ricerca beni"),
    )
    _node(root, ROOT_NS, "AnnoAutorizzazione", authorization_date[:4])
    _node(root, ROOT_NS, "Rito", codiceRito=_text(extra.get("unep_rito_codice")) or "1")
    _node(
        root,
        ROOT_NS,
        "Autorita",
        _required(extra.get("unep_autorita_sede"), "autorità che ha autorizzato la ricerca"),
        codiceAutorita=_required(extra.get("unep_autorita_tipo"), "codice autorità ricerca beni"),
    )
    _node(root, ROOT_NS, "inoltroUG", _required(extra.get("unep_inoltro_ufficiale_giudiziario"), "ufficio giudiziario di inoltro"))
    creditor = _node(root, ROOT_NS, "Creditore")
    _subject(creditor, procedenti[0], address=True)
    lawyer = _node(root, ROOT_NS, "Avvocato")
    _subject(lawyer, {**professional, "indirizzo": {}}, address=True)
    _node(root, ROOT_NS, "dataNotificaPrecetto", _date(extra.get("unep_data_notifica_precetto"), "data notifica precetto"))
    _node(root, ROOT_NS, "ImportoPrecetto", _money(extra.get("unep_importo_precetto"), "importo precetto", default_zero=True))
    party = debitori[-1]
    debtor = _node(root, ROOT_NS, "Debitore")
    _party(debtor, party, party_id=_xml_id(party.get("id") or "666", "debitore"), forced_nature="PFI")
    _address(debtor, "Domicilio", dict(party.get("domicilio") or {}))
    _node(debtor, ROOT_NS, "formaSocietaria", "N/A")
    return root


def _payment(dati: Any, parts: Iterable[Any]) -> etree._Element:
    extra = dict(dati.datiatto_extra or {})
    root = _root("PagamentoRichiesta")
    rite = "AttoPenaleAPagamento" if _text(extra.get("unep_natura_atto")).startswith("002") else "AttoCivileAPagamento"
    _atto_unep_base(root, dati, parts, role="Notifiche", rite=rite)
    _node(root, ROOT_NS, "riferimentoRichiesta", _required(extra.get("unep_codice_pagamento"), "codice pagamento UNEP"))
    return root


def _restitution(dati: Any, parts: Iterable[Any]) -> etree._Element:
    extra = dict(dati.datiatto_extra or {})
    professional = _professional(dati)
    root = _root("RichiestaRestituzioneSomme")
    _intro_base(
        root,
        dati,
        parts,
        role="Pagamenti",
        contribution_mode="",
        contribution_amount=0,
    )
    request_date = _date(extra.get("data_atto_deposito"), "data bilancio UNEP")
    _node(root, ROOT_NS, "DataRichiesta", request_date)
    _node(root, ROOT_NS, "DataRichiestaIntegrazione", request_date)
    _node(root, ROOT_NS, "IBAN", _required(extra.get("unep_iban"), "IBAN restituzione UNEP"))
    lawyer = _node(root, ROOT_NS, "Avvocato")
    _subject(lawyer, professional, address=False)
    protocol = _node(root, BASE_UNEP_NS, "Protocollo")
    _node(
        protocol,
        BASE_UNEP_NS,
        "Ufficio",
        _text(extra.get("unep_ufficio_descrizione")),
        CodiceUfficio=_required(getattr(dati, "codice_ufficio", ""), "ufficio UNEP"),
    )
    _node(protocol, BASE_UNEP_NS, "Anno", _required(extra.get("unep_anno_bilancio"), "anno bilancio UNEP"))
    _node(protocol, BASE_UNEP_NS, "Registro", _required(extra.get("unep_registro_bilancio"), "registro bilancio UNEP"))
    _node(protocol, BASE_UNEP_NS, "Cronologico", _required(extra.get("unep_codice_pagamento"), "codice pagamento UNEP"))
    return root


def _root(name: str) -> etree._Element:
    return etree.Element(
        _q(ROOT_NS, name),
        nsmap={
            None: ROOT_NS,
            "pt": ATTI_NS,
            "at": ANAGRAFICHE_NS,
            "all": ALLEGATI_NS,
            "bt": TIPI_NS,
            "bu": BASE_UNEP_NS,
            "st": SIECIC_NS,
        },
    )


def build_unep_datiatto(
    dati: Any,
    document_parts: Iterable[Any],
    *,
    contribution_mode: str,
    contribution_amount: float,
) -> bytes:
    """Genera uno dei sette DatiAtto UNEP usati dai 18 tipi del catalogo."""

    key = _required(getattr(dati, "datiatto_catalog_key", ""), "tipo deposito UNEP")
    root_name = _required(getattr(dati, "datiatto_root_name", ""), "radice DatiAtto UNEP")
    if root_name == "RichiestaParte":
        root = _notification(dati, document_parts, contribution_mode, contribution_amount, debt=False)
    elif root_name == "RichiestaParteDebito":
        root = _notification(dati, document_parts, contribution_mode, contribution_amount, debt=True)
    elif root_name == "RichiestaPignoramento":
        root = _pignoramento(dati, document_parts, contribution_mode, contribution_amount, debt=False)
    elif root_name == "RichiestaPignoramentoDebito":
        root = _pignoramento(dati, document_parts, contribution_mode, contribution_amount, debt=True)
    elif root_name == "RichiestaRicercaBeni":
        root = _ricerca_beni(dati, document_parts, contribution_mode, contribution_amount)
    elif root_name == "PagamentoRichiesta":
        root = _payment(dati, document_parts)
    elif root_name == "RichiestaRestituzioneSomme":
        root = _restitution(dati, document_parts)
    else:
        raise ValueError(f"Radice DatiAtto UNEP non prevista da Studio Telematico: {root_name} ({key}).")
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
