from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

import scripts.verifica_catena_letture as verifica_catena


def test_verifica_catena_letture_itera_tutti_gli_studi_attivi(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY=str(tmp_path / "tenants.json"))
    studi = [
        SimpleNamespace(slug="studio-a", nome="Studio A"),
        SimpleNamespace(slug="studio-b", nome="Studio B"),
    ]
    visti: list[str] = []

    monkeypatch.setattr(
        "web.services.fascicoli_presidi_runtime._active_tenants",
        lambda app_arg: studi,
    )
    monkeypatch.setattr(
        "web.services.fascicoli_presidi_runtime._attach_tenant_context",
        lambda manager, studio: (
            setattr(g, "tenant_context_slug", studio.slug),
            setattr(g, "data_paths", {"FASCICOLI_DB": f"/data/{studio.slug}/fascicoli.json"}),
        ),
    )
    monkeypatch.setattr(
        "pct.tenant.GestioneTenant",
        lambda registry_path: SimpleNamespace(registry_path=registry_path),
    )

    def fake_verifica(fascicolo_id: str = ""):
        slug = g.tenant_context_slug
        visti.append(slug)
        return {
            "ok": True,
            "problemi": [],
            "fascicoli": [{"id": f"{slug}-1"}],
            "ciclo": {"fermo": 1, "da_leggere": 0, "in_errore": 0},
            "registro": {"tenant": slug},
            "fatti": {},
            "presidi": {},
            "sprechi": {},
        }

    monkeypatch.setattr(verifica_catena, "verifica", fake_verifica)

    esito = verifica_catena.verifica_tutti(app)

    assert esito["ok"] is True
    assert visti == ["studio-a", "studio-b"]
    assert esito["totali"] == {"tenants": 2, "fascicoli": 2, "fermo": 2, "da_leggere": 0, "in_errore": 0}
    assert [t["studio"]["slug"] for t in esito["tenants"]] == ["studio-a", "studio-b"]


def test_verifica_catena_letture_filtra_tenant(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY=str(tmp_path / "tenants.json"))
    studi = [
        SimpleNamespace(slug="studio-a", nome="Studio A"),
        SimpleNamespace(slug="studio-b", nome="Studio B"),
    ]

    monkeypatch.setattr("web.services.fascicoli_presidi_runtime._active_tenants", lambda app_arg: studi)
    monkeypatch.setattr(
        "web.services.fascicoli_presidi_runtime._attach_tenant_context",
        lambda manager, studio: setattr(g, "tenant_context_slug", studio.slug),
    )
    monkeypatch.setattr("pct.tenant.GestioneTenant", lambda registry_path: SimpleNamespace())
    monkeypatch.setattr(
        verifica_catena,
        "verifica",
        lambda fascicolo_id="": {
            "ok": True,
            "problemi": [],
            "fascicoli": [{"id": g.tenant_context_slug}],
            "ciclo": {"fermo": 1},
        },
    )

    esito = verifica_catena.verifica_tutti(app, tenant_slug="studio-b")

    assert esito["totali"]["tenants"] == 1
    assert esito["tenants"][0]["studio"]["slug"] == "studio-b"


def test_stato_fascicolo_segnala_ciclo_incoerente(monkeypatch):
    class RegistroFinto:
        def stato_fascicolo(self, tenant, fascicolo_id, *, lettori):
            return SimpleNamespace(
                lettori=[
                    SimpleNamespace(lettore="motore_documenti", da_leggere=3, errori=0),
                    SimpleNamespace(lettore="motore_pec", da_leggere=0, errori=1),
                ]
            )

        def fatti(self, tenant, fascicolo_id, verifiche=None):
            return []

    monkeypatch.setattr(
        "web.services.archivio_letture_runtime.stato_ciclo_fascicolo",
        lambda fascicolo_id, registro, tenant, impronta="": SimpleNamespace(stato="fermo", motivo="tutto letto"),
    )
    monkeypatch.setattr("web.services.archivio_letture_runtime._impronta_viva", lambda fascicolo: "impronta")
    monkeypatch.setattr("pct.archivio_letture.fatti_canonici", lambda fatti: fatti)

    riga = verifica_catena._stato_fascicolo(SimpleNamespace(id="F1", titolo="Pratica"), RegistroFinto(), "studio")

    assert riga["ciclo"] == "da_leggere"
    assert riga["oggetti_da_leggere"] == 3
    assert riga["oggetti_errori"] == 1
    assert "dettaglio dei motori" in riga["motivo"]
