"""Cliente del fascicolo mostrato nel Profilo processuale PEC e nel salvataggio."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from flask import Flask, g

from pct.pec_fascicolo_cliente import resolve_pec_fascicolo_cliente, select_pec_fascicolo


class _User:
    id = "user-pec"
    username = "avvocato"
    tenant_slug = "default"

    @property
    def permessi_effettivi(self):
        return ["ai.usa", "messaggi.leggi", "fascicoli.leggi", "telematico.leggi"]

    def ha_permesso(self, permission: str) -> bool:
        return permission in self.permessi_effettivi


class _Archivio:
    def __init__(self, *items):
        self._items = {item.id: item for item in items}

    def get(self, item_id):
        return self._items.get(item_id)

    def tutti(self):
        return list(self._items.values())


def _fascicolo(**kwargs):
    base = dict(
        id="06928604",
        numero="2026/244",
        titolo="Giacobe c. MIM",
        stato="APERTO",
        id_cliente="cli-1",
        nome_cliente="Giacobe Anna",
        numero_rg="5478",
        anno_rg=2025,
        tribunale="Tribunale di Messina",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _cliente(**kwargs):
    base = dict(
        id="cli-1",
        tipo="PERSONA_FISICA",
        nome="Anna",
        cognome="Giacobe",
        ragione_sociale="",
        codice_fiscale="GCBNNA80A41F158X",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _detail(linked="", candidates=None):
    return {"message": {"linked_fascicolo_id": linked}, "fascicolo_link": {"candidates": candidates or []}}


def test_pec_collegata_espone_nome_e_cognome_dal_cliente_del_fascicolo():
    detail = _detail(
        linked="06928604",
        candidates=[{"id": "06928604", "reasons": ["RG certificato dall'XML ministeriale", "ufficio compatibile"]}],
    )

    result = resolve_pec_fascicolo_cliente(detail, fascicoli=_Archivio(_fascicolo()), clienti=_Archivio(_cliente()))

    assert result["stato"] == "collegato"
    assert result["cliente"]["nome"] == "Anna"
    assert result["cliente"]["cognome"] == "Giacobe"
    assert result["cliente"]["fonte"] == "anagrafica_cliente"
    assert result["fascicolo"]["rg"] == "5478/2025"
    assert result["fascicolo"]["aperto"] is True
    assert "codice_fiscale" not in result["cliente"]
    assert "GCBNNA80A41F158X" not in str(result)


def test_rg_solo_testuale_senza_ufficio_non_propone_cliente():
    detail = _detail(candidates=[{"id": "06928604", "reasons": ["RG coincidente"]}])

    result = resolve_pec_fascicolo_cliente(detail, fascicoli=_Archivio(_fascicolo()), clienti=_Archivio(_cliente()))

    assert result["stato"] == "non_collegato"
    assert result["cliente"] == {}
    assert result["fascicolo"] == {}


def test_rg_e_ufficio_coincidenti_propongono_fascicolo_da_confermare():
    selection = select_pec_fascicolo(_detail(candidates=[{"id": "06928604", "reasons": ["RG coincidente", "ufficio compatibile"]}]))

    assert selection == {"fascicolo_id": "06928604", "stato": "da_confermare", "motivazioni": ["RG coincidente", "ufficio compatibile"]}


def test_nome_denormalizzato_senza_anagrafica_univoca_non_viene_spezzato():
    fascicolo = _fascicolo(id_cliente="", nome_cliente="De Luca Maria Grazia")

    result = resolve_pec_fascicolo_cliente(_detail(linked="06928604"), fascicoli=_Archivio(fascicolo), clienti=_Archivio())

    assert result["cliente"]["nome_completo"] == "De Luca Maria Grazia"
    assert result["cliente"]["nome"] == ""
    assert result["cliente"]["cognome"] == ""
    assert result["cliente"]["fonte"] == "nome_cliente_fascicolo"


def test_persona_giuridica_usa_ragione_sociale():
    cliente = _cliente(tipo="PERSONA_GIURIDICA", nome="", cognome="", ragione_sociale="Alfa Srl")

    result = resolve_pec_fascicolo_cliente(_detail(linked="06928604"), fascicoli=_Archivio(_fascicolo()), clienti=_Archivio(cliente))

    assert result["cliente"]["ragione_sociale"] == "Alfa Srl"
    assert result["cliente"]["nome_completo"] == "Alfa Srl"
    assert result["cliente"]["nome"] == ""


def test_api_cliente_fascicolo_e_prepara_salvataggio_precompilato(tmp_path, monkeypatch):
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo
    from web.blueprints.pec_pipeline_api import pec_pipeline_api

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "PEC_AUDIT_DB": tmp_path / "email" / "pec_audit.sqlite",
        "CLIENTI_DB": tmp_path / "clienti" / "anagrafica.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
        "NOTIFICATIONS_DB": tmp_path / "notifications" / "notifications.db",
    }

    def fake_tenant_data_path(key, default, *aliases, require_tenant=True):
        value = paths.get(key)
        if not value:
            raise AssertionError(f"Path tenant non atteso: {key}")
        value.parent.mkdir(parents=True, exist_ok=True)
        return str(value)

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pec_pipeline_api, url_prefix="/api/pec")
    monkeypatch.setattr("web.blueprints.pec_pipeline_api.tenant_data_path", fake_tenant_data_path)

    clienti = GestioneClienti(str(paths["CLIENTI_DB"]))
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Anna", cognome="Giacobe")
    fascicoli = GestioneFascicoli(str(paths["FASCICOLI_DB"]), documents_dir=str(paths["FASCICOLI_DOCS"]))
    fascicolo = fascicoli.nuovo("Giacobe c. MIM", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente=cliente.nome_completo)
    altro = fascicoli.nuovo("Giacobe - recupero crediti", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente=cliente.nome_completo)

    @app.before_request
    def _inject_user():
        g.utente_corrente = _User()
        g.tenant_slug = "default"
        g.data_paths = {
            "PEC_AUDIT_DB": str(paths["PEC_AUDIT_DB"]),
            "NOTIFICATIONS_DB": str(paths["NOTIFICATIONS_DB"]),
        }

    client = app.test_client()
    assert client.post("/api/pec/demo/ingest").status_code == 200
    message_id = client.get("/api/pec/messages").get_json()["data"][0]["id"]

    with sqlite3.connect(paths["PEC_AUDIT_DB"]) as conn:
        conn.execute("UPDATE pec_messages SET linked_fascicolo_id=? WHERE id=?", (fascicolo.id, message_id))

    response = client.get(f"/api/pec/messages/{message_id}/cliente-fascicolo")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["stato"] == "collegato"
    assert payload["fascicolo"]["id"] == fascicolo.id
    assert payload["cliente"]["nome"] == "Anna"
    assert payload["cliente"]["cognome"] == "Giacobe"

    prepare = client.post(f"/api/pec/messages/{message_id}/salva-fascicolo", json={"prepara": True})
    assert prepare.status_code == 200
    prepared = prepare.get_json()
    assert prepared["requires_confirmation"] is True
    assert prepared["candidates"][0]["id"] == fascicolo.id
    assert prepared["candidates"][0]["pec_match"] is True
    assert {item["id"] for item in prepared["candidates"]} == {fascicolo.id}
    assert prepared["cliente"]["nome"] == "Anna"

    by_name = client.post(
        f"/api/pec/messages/{message_id}/salva-fascicolo",
        json={"prepara": True, "nome": "Anna", "cognome": "Giacobe"},
    ).get_json()
    assert by_name["candidates"][0]["id"] == fascicolo.id
    assert {item["id"] for item in by_name["candidates"]} == {fascicolo.id, altro.id}

    assert client.get("/api/pec/messages/inesistente/cliente-fascicolo").status_code == 404
