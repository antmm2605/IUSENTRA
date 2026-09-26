"""Migrazione React 2.412.0: pagine che restavano sui template storici.

Lex operativo, scheda del preventivo, ripristino di un backup, modifica e
permessi del singolo utente si aprono nella shell React; le azioni restano
quelle del server (API JSON o POST esistenti) con i controlli di permesso.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.auth import GestioneUtenti, RuoloUtente
from pct.backup import GestioneBackup, TipoBackup
from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _login


@pytest.mark.parametrize(
    "percorso",
    ["/lex-operativo", "/preventivi/p/abc123", "/backup/xyz/ripristina", "/utenti/u1/permessi", "/utenti/u1/modifica"],
)
def test_pagine_migrate_servite_da_react(tmp_path, percorso):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        risposta = client.get(percorso, headers={"Accept": "text/html"})
        html = risposta.get_data(as_text=True)
        assert risposta.status_code == 200, percorso
        assert "iusentra-react-bootstrap" in html, percorso


def test_download_e_azioni_restano_del_server(tmp_path):
    from web.bootstrap.react_route_gate import _excluded

    assert _excluded("/backup/xyz/scarica")
    assert _excluded("/utenti/u1/elimina")
    assert _excluded("/preventivi/p/abc/pdf")
    assert not _excluded("/preventivi/p/abc")


def test_componenti_react_registrati():
    from web.blueprints import react_shell

    assert react_shell._route_component_key("/lex-operativo") == "src/components/LexOperativoPage.tsx"
    assert react_shell._route_component_key("/preventivi/p/abc") == "src/components/PreventiviPage.tsx"
    assert react_shell._route_component_key("/utenti/u1/permessi") == "src/components/UtentiPage.tsx"
    app_tsx = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "isLexOperativoPage?<LexOperativoPage/>" in app_tsx
    assert "\\/utenti\\/[^/]+\\/(modifica|permessi)$" in app_tsx
    assert "\\/backup\\/[^/]+\\/ripristina$" in app_tsx


def _backup_con_dati(tmp_path: Path) -> tuple[GestioneBackup, str]:
    dati = tmp_path / "dati"
    dati.mkdir()
    (dati / "agenda.json").write_text(json.dumps({"appuntamenti": [1, 2]}), encoding="utf-8")
    manager = GestioneBackup(directory_backup=str(tmp_path / "backup"), percorsi_dati={"agenda": str(dati / "agenda.json")})
    record = manager.esegui_backup(tipo=TipoBackup.COMPLETO)
    return manager, record.id


def test_ripristino_in_cartella_dedicata(tmp_path):
    from web.services.react_backup_bridge import restore_react_backup

    manager, backup_id = _backup_con_dati(tmp_path)
    eventi = []
    utenti = SimpleNamespace(registra_evento=lambda *a, **k: eventi.append((a, k)))
    utente = SimpleNamespace(id="u1", username="admin")

    # Percorsi arbitrari e nomi con separatori non sono ammessi.
    for cartella in ("../etc", "/tmp/x", "a/b", "..", "nome con spazi"):
        esito = restore_react_backup(
            get_backup=lambda: manager, get_utenti=lambda: utenti, current_user=utente,
            payload={"backupId": backup_id, "folder": cartella, "confirm": True},
        )
        assert esito["ok"] is False and "folder" in esito["errors"], cartella
    senza_conferma = restore_react_backup(
        get_backup=lambda: manager, get_utenti=lambda: utenti, current_user=utente,
        payload={"backupId": backup_id, "folder": "prova"},
    )
    assert "confirm" in senza_conferma["errors"]

    esito = restore_react_backup(
        get_backup=lambda: manager, get_utenti=lambda: utenti, current_user=utente,
        payload={"backupId": backup_id, "folder": "prova-1", "confirm": True},
    )
    assert esito["ok"] is True, esito
    assert esito["restore"]["folder"] == "ripristini/prova-1" and esito["restore"]["restored"] >= 1
    ripristinati = list((tmp_path / "ripristini" / "prova-1").rglob("agenda.json"))
    assert ripristinati and json.loads(ripristinati[0].read_text(encoding="utf-8")) == {"appuntamenti": [1, 2]}
    assert eventi and eventi[0][0][0] == "backup.ripristina"


def _utenti(tmp_path: Path) -> GestioneUtenti:
    gestore = GestioneUtenti(
        db_path=str(tmp_path / "utenti.json"),
        audit_path=str(tmp_path / "audit.json"),
        secret_key="test",
        bootstrap_admin_password="admin",
        bootstrap_admin_credentials_path=str(tmp_path / "bootstrap.json"),
    )
    for nome, ruolo in (("capo", RuoloUtente.AMMINISTRATORE), ("praticante", RuoloUtente.PRATICANTE)):
        gestore.crea(username=nome, password="Password123!", ruolo=ruolo, email=f"{nome}@example.it", nome_completo=nome.title(), must_change_password=False)
    return gestore


def test_permessi_personalizzati(tmp_path):
    from web.services.react_utenti_bridge import build_react_utenti_payload, update_react_utente_permessi

    gestore = _utenti(tmp_path)
    capo = next(u for u in gestore.tutti() if u.username == "capo")
    praticante = next(u for u in gestore.tutti() if u.username == "praticante")

    pagina = build_react_utenti_payload(get_utenti=lambda: gestore, current_user=capo)
    assert any(voce["key"] == "fascicoli.elimina" for voce in pagina["permissionCatalog"])
    riga = next(u for u in pagina["users"] if u["id"] == praticante.id)
    assert "fascicoli.leggi" in riga["rolePermissions"] and riga["extraPermissions"] == []

    esito = update_react_utente_permessi(
        get_utenti=lambda: gestore, current_user=capo, user_id=praticante.id,
        payload={"extra": ["fascicoli.elimina"], "denied": ["fascicoli.leggi"]},
    )
    assert esito["ok"] is True, esito
    aggiornato = gestore.get(praticante.id)
    assert aggiornato.permessi_extra == ["fascicoli.elimina"] and aggiornato.permessi_negati == ["fascicoli.leggi"]

    sconosciuto = update_react_utente_permessi(
        get_utenti=lambda: gestore, current_user=capo, user_id=praticante.id,
        payload={"extra": ["permesso.inventato"], "denied": []},
    )
    assert sconosciuto["ok"] is False
    conflitto = update_react_utente_permessi(
        get_utenti=lambda: gestore, current_user=capo, user_id=praticante.id,
        payload={"extra": ["agenda.leggi"], "denied": ["agenda.leggi"]},
    )
    assert conflitto["ok"] is False
    se_stesso = update_react_utente_permessi(
        get_utenti=lambda: gestore, current_user=capo, user_id=capo.id,
        payload={"extra": [], "denied": ["agenda.leggi"]},
    )
    assert se_stesso["ok"] is False
    # Chi non ha un permesso non può concederlo.
    limitato = SimpleNamespace(id="x", ha_permesso=lambda p: p == "utenti.scrivi", permessi_effettivi=["utenti.scrivi"])
    escalation = update_react_utente_permessi(
        get_utenti=lambda: gestore, current_user=limitato, user_id=praticante.id,
        payload={"extra": ["tenant.configura"], "denied": []},
    )
    assert escalation["ok"] is False and "extra" in escalation["errors"]


def test_scheda_preventivo_con_workflow(tmp_path):
    from pct.preventivi import GestionePreventivi, VocePreventivo
    from pct.clienti import GestioneClienti, TipoCliente
    app = _app_sessione(tmp_path)
    cliente = GestioneClienti(app.config["CLIENTI_DB"]).nuovo(TipoCliente.PERSONA_FISICA, nome="Maria", cognome="Verdi")
    preventivo = GestionePreventivi(app.config["PREVENTIVI_DB"]).crea_preventivo(
        cliente.id, "Recupero crediti", [VocePreventivo(descrizione="Studio", importo=500.0)]
    )
    with app.test_client() as client:
        _login(client)
        risposta = client.get(f"/api/v1/ui/preventivi/{preventivo.id}")
        dati = risposta.get_json()
    assert risposta.status_code == 200, dati
    item = dati["item"]
    assert item["nextStep"]["kind"] == "conferma"
    etichette = [azione["label"] for azione in item["nextStep"]["actions"]]
    assert "Accettazione in studio" in etichette
    assert all(azione["method"] == "POST" for azione in item["nextStep"]["actions"])
    assert item["pdfHref"].endswith(f"/preventivi/p/{preventivo.id}/pdf")
    assert item["deleteHref"] == f"/api/v1/ui/preventivi/{preventivo.id}/workflow/elimina"
    # Le azioni della scheda React passano da API JSON, non da moduli HTML.
    with app.test_client() as client:
        _login(client)
        invio = client.post(f"/api/v1/ui/preventivi/{preventivo.id}/workflow/invia", json={})
        assert invio.status_code == 200 and invio.get_json()["ok"] is True
        assert invio.get_json()["redirect_href"].endswith(f"/preventivi/p/{preventivo.id}")
        ignota = client.post(f"/api/v1/ui/preventivi/{preventivo.id}/workflow/sconosciuta", json={})
        assert ignota.status_code == 404
        eliminato = client.post(f"/api/v1/ui/preventivi/{preventivo.id}/workflow/elimina", json={})
        assert eliminato.get_json()["ok"] is True
        assert client.get(f"/api/v1/ui/preventivi/{preventivo.id}").status_code == 404


def test_copertine_sono_documenti_da_stampare(tmp_path):
    from web.bootstrap.react_route_gate import _excluded

    # La copertina del faldone finiva nella shell React, che mostrava la Panoramica.
    assert _excluded("/clienti/c1/faldone/copertina")
    assert _excluded("/fascicoli/f1/copertina")


def test_impostazioni_pagamenti_duplicate_portano_a_react(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        risposta = client.get("/pagamenti/impostazioni/pagamenti")
        assert risposta.status_code == 302 and risposta.headers["Location"].endswith("/impostazioni?tab=pagamenti")


def test_modifica_scheda_giurisprudenza(tmp_path):
    from pct.giurisprudenza import GestioneGiurisprudenza
    from web.services.react_giurisprudenza_bridge import (
        build_react_giurisprudenza_edit_payload,
        update_react_giurisprudenza_record,
    )

    gestore = GestioneGiurisprudenza(db_path=str(tmp_path / "giurisprudenza.json"))
    record = gestore.salva_da_form({
        "titolo": "Cass. civ. n. 100/2024",
        "massima": "Massima iniziale.",
        "norme_citate": "art. 2043 c.c., art. 2059 c.c.",
        "numero_provvedimento": "100/2024",
    })
    pagina, stato = build_react_giurisprudenza_edit_payload(get_giurisprudenza=lambda: gestore, judgment_id=record["id"])
    assert stato == 200 and pagina["recordId"] == record["id"]
    assert pagina["defaults"]["titolo"] == "Cass. civ. n. 100/2024"
    assert "art. 2043 c.c." in pagina["defaults"]["norme_citate"]
    assert pagina["forms"][0]["endpoint"].endswith(f"/giurisprudenza/{record['id']}/modifica")

    esito, stato = update_react_giurisprudenza_record(
        get_giurisprudenza=lambda: gestore,
        judgment_id=record["id"],
        payload={**pagina["defaults"], "massima": "Massima corretta."},
    )
    assert stato == 200 and esito["ok"] is True
    assert gestore.get(record["id"])["massima"] == "Massima corretta."
    assert len(gestore.cerca()) == 1  # aggiornata, non duplicata

    _, mancante = build_react_giurisprudenza_edit_payload(get_giurisprudenza=lambda: gestore, judgment_id="inesistente")
    assert mancante == 404


def test_modelli_di_studio_in_react(tmp_path):
    from web.bootstrap.react_route_gate import _excluded

    for percorso in ("/template-atti/nuovo", "/template-atti/scheda/t1", "/template-atti/t1/modifica", "/template-atti/t1/usa"):
        assert not _excluded(percorso), percorso
    assert _excluded("/template-atti/t1/pdf")

    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        base = "/api/v1/ui/template-atti/studio"
        modulo = client.get(f"{base}/nuovo").get_json()
        assert modulo["ok"] is True and modulo["categories"]
        mancante = client.post(f"{base}/nuovo", json={"titolo": "", "corpo": ""})
        assert mancante.status_code == 400 and set(mancante.get_json()["errors"]) >= {"titolo", "corpo"}
        creato = client.post(f"{base}/nuovo", json={
            "titolo": "Lettera di messa in mora",
            "categoria": modulo["categories"][0],
            "corpo": "Spett.le {{ destinatario_nome }}, entro {{ termine_giorni }} giorni.",
            "note": "",
        })
        assert creato.status_code == 201, creato.get_json()
        tid = creato.get_json()["item"]["id"]
        scheda = client.get(f"{base}/{tid}").get_json()
        assert scheda["item"]["title"] == "Lettera di messa in mora" and scheda["item"]["sections"]
        aggiornato = client.post(f"{base}/{tid}/modifica", json={**client.get(f"{base}/{tid}/modifica").get_json()["values"], "note": "Uso interno"})
        assert aggiornato.get_json()["ok"] is True
        uso = client.get(f"{base}/{tid}/usa").get_json()
        assert uso["ok"] is True and isinstance(uso["clients"], list)
        testo = client.post(f"{base}/{tid}/genera", json={"clientId": "", "matterId": "", "fields": {"destinatario_nome": "Rossi S.r.l.", "termine_giorni": "15"}}).get_json()
        assert testo["ok"] is True
        assert "Rossi S.r.l." in testo["text"] and "15 giorni" in testo["text"]
        assert testo["pdfAction"] == f"/template-atti/{tid}/pdf"
        pagina = client.get(f"/template-atti/{tid}/usa", headers={"Accept": "text/html"})
        assert "iusentra-react-bootstrap" in pagina.get_data(as_text=True)
        copia = client.post(scheda["item"]["cloneAction"], json={})
        assert copia.status_code == 201 and copia.get_json()["redirect_href"].endswith("/modifica")
        via = client.post(f"{base}/{tid}/elimina", json={})
        assert via.get_json()["ok"] is True
        assert client.get(f"{base}/{tid}").status_code == 404
