from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.clienti import Cliente, Indirizzo, Recapiti, TipoCliente
from pct.fatturazione import GestioneFatturazione, VoceParcella
from web.services.react_fatturazione_bridge import (
    build_react_fatturazione_payload,
    create_react_fattura,
)


class _Loader:
    def __init__(self, *items):
        self._items = {getattr(item, "id", ""): item for item in items}

    def tutti(self):
        return list(self._items.values())

    def get(self, item_id: str):
        return self._items.get(item_id)


class _User:
    id = "user-1"
    username = "operatore"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"fatturazione.leggi", "fatturazione.scrivi"}


class _AuditUsers:
    def __init__(self):
        self.events: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def registra_evento(self, *args, **kwargs):
        self.events.append((args, kwargs))


def _cliente() -> Cliente:
    return Cliente(
        id="CLI-001",
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Beta Srl",
        partita_iva="12345678901",
        codice_fiscale="12345678901",
        indirizzo_sede_legale=Indirizzo(
            via="Via Garibaldi",
            civico="12",
            cap="20100",
            comune="Milano",
            provincia="MI",
            nazione="Italia",
        ),
        recapiti=Recapiti(
            telefono="021234567",
            email="amministrazione@beta.example",
            pec="beta@pec.example",
        ),
    )


def _fascicolo(cliente_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="FAS-001",
        id_cliente=cliente_id,
        titolo="Opposizione a decreto ingiuntivo",
        numero_rg="120/2026",
        tribunale="Tribunale di Milano",
        giudice="Dott.ssa Bianchi",
        oggetto="Opposizione e sospensione provvisoria esecuzione",
    )


def _studio_config() -> dict[str, str]:
    return {
        "STUDIO_NOME": "Studio Legale Rossi",
        "STUDIO_AVVOCATO": "Avv. Mario Rossi",
        "STUDIO_INDIRIZZO": "Via Verdi 8",
        "STUDIO_CAP": "00100",
        "STUDIO_CITY": "Roma",
        "STUDIO_PROVINCE": "RM",
        "STUDIO_PIVA": "09876543210",
        "STUDIO_CF": "RSSMRA80A01H501Z",
        "STUDIO_TELEFONO": "061234567",
        "STUDIO_EMAIL": "segreteria@studio-rossi.example",
        "STUDIO_IBAN": "IT60X0542811101000000123456",
        "STUDIO_BANCA": "Banca Forense",
    }


def test_bridge_fatturazione_prefila_nuova_parcella_personalizzata(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    manager.crea(
        id_cliente=cliente.id,
        voci=[VoceParcella(descrizione="Acconto", quantita=1, prezzo_unitario=100.0)],
        data_emissione=date.today().isoformat(),
    )

    payload = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        query={"id_cliente": cliente.id, "id_fascicolo": fascicolo.id},
        route="/fatturazione/nuova",
        config=_studio_config(),
    )

    defaults = payload["form"]["defaults"]
    personalized = defaults["dati_personalizzati"]

    assert payload["form"]["title"] == "Nuova parcella personalizzata"
    assert payload["nextNumber"].endswith("/002")
    assert payload["studioProfile"]["nome"] == "Mario"
    assert payload["studioProfile"]["cognome"] == "Rossi"
    assert personalized["transmission"]["identificativo_fiscale"] == "RSSMRA80A01H501Z"
    assert personalized["recipient"]["nome_denominazione"] == "Beta Srl"
    assert personalized["recipient"]["pec"] == "beta@pec.example"
    assert personalized["document"]["numero_documento"] == payload["nextNumber"]
    assert personalized["document"]["fascicolo_label"].startswith("Opposizione a decreto ingiuntivo")
    assert personalized["payment"]["iban"] == "IT60X0542811101000000123456"
    assert personalized["payment"]["modalita_pagamento_label"] == "Bonifico"


def test_create_react_fattura_salva_snapshot_personalizzato_e_registra_audit(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()

    payload = {
        "id_cliente": cliente.id,
        "id_fascicolo": fascicolo.id,
        "data_emissione": "2026-05-10",
        "data_scadenza": "2026-06-09",
        "note": "Parcella personalizzata per attivita giudiziale",
        "voci": [
            {"descrizione": "Compenso professionale", "quantita": "1", "prezzo_unitario": "240.00", "tipo": "ONORARIO"},
            {"descrizione": "Spese imponibili", "quantita": "1", "prezzo_unitario": "20.00", "tipo": "SPESE"},
        ],
        "opzioni_fiscali": {
            "applica_iva": True,
            "applica_cassa": True,
            "applica_ritenuta": False,
            "applica_bollo": False,
        },
        "percentuale_spese_generali": "15",
        "metodo_pagamento": "Bonifico",
        "dati_personalizzati": {
            "transmission": {
                "identificativo_fiscale": "RSSMRA80A01H501Z",
                "codice_invio": "A1202",
                "telefono": "061234567",
                "email": "segreteria@studio-rossi.example",
            },
            "studio": {
                "nome_denominazione": "Studio Legale Rossi",
                "partita_iva": "09876543210",
                "codice_fiscale": "RSSMRA80A01H501Z",
            },
            "recipient": {
                "denominazione": "Beta Srl",
                "nome_denominazione": "Beta Srl",
                "partita_iva": "12345678901",
                "codice_fiscale": "12345678901",
                "indirizzo": "Via Garibaldi 12",
                "cap": "20100",
                "citta": "Milano",
                "provincia": "MI",
                "nazione": "IT",
                "codice_destinatario": "0000000",
                "pec": "beta@pec.example",
            },
            "document": {
                "tipo_documento": "TD01",
                "numero_documento": "2026/010",
                "data_documento": "2026-05-10",
                "causale_oggetto": "Parcella fascicolo RG 120/2026",
                "regime_fiscale": "RF01",
                "esigibilita_iva": "I",
            },
            "payment": {
                "modalita_pagamento_label": "Bonifico",
                "modalita_pagamento_codice": "MP05",
                "beneficiario": "Studio Legale Rossi",
                "istituto_finanziario": "Banca Forense",
                "iban": "IT60X0542811101000000123456",
                "giorni_termini": "30",
            },
        },
    }

    result, status = create_react_fattura(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        get_utenti=lambda: audit_users,
        get_preventivi=None,
        current_user=_User(),
        payload=payload,
        config=_studio_config(),
        ip_address="127.0.0.1",
    )

    assert status == 200
    assert result["ok"] is True
    assert manager.tutte()
    parcella = manager.tutte()[0]
    assert parcella.percentuale_spese_generali == 15.0
    assert parcella.metodo_pagamento == "Bonifico"
    assert parcella.voci[1].tipo == "SPESE"
    assert parcella.dati_personalizzati["recipient"]["denominazione"] == "Beta Srl"
    assert parcella.dati_personalizzati["payment"]["iban"] == "IT60X0542811101000000123456"
    assert audit_users.events
    assert audit_users.events[0][0][0] == "fatturazione.crea"


def test_create_react_fattura_forfettaria_disattiva_iva_anche_se_selezionata(tmp_path):
    cliente = _cliente()
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()

    payload = {
        "id_cliente": cliente.id,
        "data_emissione": "2026-05-10",
        "data_scadenza": "2026-06-09",
        "note": "Parcella forfettaria",
        "voci": [
            {"descrizione": "Compenso professionale", "quantita": "1", "prezzo_unitario": "258.00", "tipo": "ONORARIO"},
        ],
        "opzioni_fiscali": {
            "applica_iva": True,
            "applica_cassa": True,
            "applica_ritenuta": False,
            "applica_bollo": False,
        },
        "percentuale_spese_generali": "15",
        "metodo_pagamento": "Bonifico",
        "dati_personalizzati": {
            "document": {
                "regime_fiscale": "RF19",
            },
        },
    }

    result, status = create_react_fattura(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(),
        get_utenti=lambda: audit_users,
        get_preventivi=None,
        current_user=_User(),
        payload=payload,
        config=_studio_config(),
        ip_address="127.0.0.1",
    )

    assert status == 200
    assert result["ok"] is True
    parcella = manager.tutte()[0]
    assert parcella.applica_iva is False
    assert parcella.iva == 0.0
