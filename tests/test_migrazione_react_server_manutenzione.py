"""Migrazione React: pagina «Server e manutenzione» del pannello di piattaforma.

`/admin/server-manutenzione` si apre nell'applicazione React di piattaforma con
i dati di `/api/v1/ui/piattaforma/server-manutenzione`; le azioni passano da
`/api/v1/ui/piattaforma/server-manutenzione/azioni/<azione>` e chiamano gli
stessi servizi, con gli stessi argomenti, del blueprint storico
`web/blueprints/server_maintenance_admin.py`.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.test_migrazione_react_piattaforma import _app, _login_superadmin

BASE = "/api/v1/ui/piattaforma/server-manutenzione"

ANALISI = {
    "analizza-manutenzione-professionale",
    "analizza-retention-backup",
    "analizza-compattazione",
    "analizza-spazio-database",
    "analizza-ottimizzazione-massima",
    "analizza-cartelle-escluse",
    "analizza-copia-doppia-fascicoli",
    "analizza-normativa-globale",
    "analizza-collegamenti-pec",
    "analizza-chunk-rag",
}
MODIFICHE = {
    "applica-manutenzione-professionale",
    "applica-retention-backup",
    "backup-ora",
    "pulisci-log-sistema",
    "docker-prune",
    "compatta",
    "applica-compattazione-database",
    "applica-ottimizzazione-massima",
    "elimina-cartelle-escluse",
    "applica-copia-doppia-fascicoli",
    "pulisci-normativa-globale",
    "applica-collegamenti-pec",
    "applica-chunk-rag",
}
PAROLE_INGLESI = ("retention", "mirror", "docker", "chunk", "snapshot", "cache", "storage", "prune", "vacuum", "registry")


def _azioni(sezioni: list[dict]) -> list[dict]:
    trovate = []
    for sezione in sezioni:
        trovate += sezione.get("items", []) if sezione["kind"] == "actions" else []
        trovate += [sezione["action"]] if sezione["kind"] == "form" else []
        for riga in sezione.get("rows", []) if sezione["kind"] == "table" else []:
            trovate += riga.get("actions", [])
    return trovate


def _azione(client, chiave: str, *, params=None, values=None):
    return client.post(f"{BASE}/azioni/{chiave}", json={"params": params or {}, "values": values or {}})


def _testi_visibili(sezioni: list[dict]) -> list[str]:
    """Titoli, etichette e conferme: le parole scritte dalla pagina, non i dati misurati."""
    testi = []
    for sezione in sezioni:
        testi += [sezione.get("title", ""), sezione.get("subtitle", "")]
        testi += [c["label"] for c in sezione.get("columns", [])]
        if sezione["kind"] in {"metrics", "facts"}:
            testi += [i["label"] for i in sezione["items"]]
        if sezione["kind"] == "notes":
            testi += sezione["items"]
    testi += [a["label"] for a in _azioni(sezioni)] + [a["confirm"] for a in _azioni(sezioni)]
    return [t for t in testi if t]


def _archivio_studio(radice: Path, slug: str = "studio-prova") -> Path:
    """Un `studio.db` con un fascicolo che porta ancora la copia doppia in `dati_json`."""
    db = radice / "tenants" / slug / "studio.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE fascicoli (id TEXT PRIMARY KEY, dati_json TEXT)")
        conn.execute("INSERT INTO fascicoli VALUES ('f1', ?)", ('{"numero": "1/2026", "documenti": [{"nome": "atto.pdf"}]}',))
    return db


@pytest.fixture
def app(tmp_path: Path):
    applicazione = _app(tmp_path)
    radice = tmp_path / "dati-server"
    _archivio_studio(radice)
    applicazione.config["PCT_DATA_ROOT"] = str(radice)
    return applicazione


def test_pagina_server_manutenzione_dal_servizio(app):
    with app.test_client() as client:
        _login_superadmin(client)
        risposta = client.get(BASE)
        corpo = risposta.get_json()
    assert risposta.status_code == 200 and corpo["ok"] is True
    assert corpo["page"] == "server-manutenzione"
    assert corpo["title"] == "Server e manutenzione" and corpo["sections"]
    assert {c["href"] for c in corpo["links"]} == {"/admin/osservabilita"}
    for sezione in corpo["sections"]:
        assert sezione["kind"] in {"metrics", "status", "table", "facts", "notes", "shortcuts", "actions", "form"}
    titoli = {s["title"] for s in corpo["sections"]}
    assert {"Disco e backup", "Composizione fuori dagli studi", "Recupero dello spazio", "Aree del server", "Consumi per studio", "Aree di archiviazione principali"} <= titoli
    assert any(t.startswith("Console ") for t in titoli)
    # Nessun dato si perde nella redazione dei percorsi interni delle risposte JSON.
    assert "Operazione non completata." not in str(corpo["sections"])

    azioni = {a["key"]: a for a in _azioni(corpo["sections"])}
    assert ANALISI | MODIFICHE <= set(azioni)
    for chiave in MODIFICHE:
        assert azioni[chiave]["confirm"], chiave
    for chiave in ANALISI:
        assert not azioni[chiave]["confirm"], chiave

    for testo in _testi_visibili(corpo["sections"]):
        assert not any(parola in testo.lower() for parola in PAROLE_INGLESI), testo


def test_righe_degli_studi_con_collegamenti_e_compattazione(app, monkeypatch):
    import web.services.server_maintenance_surface as superficie

    studio = {
        "slug": "studio-a",
        "registry_slug": "studio-a",
        "display_name": "Studio A",
        "storage_status_label": "Studio attivo registrato",
        "total_label": "8.0 KiB",
        "file_count": 1,
        "directory_count": 3,
        "path": "/data/tenants/studio-a",
        "categories": [{"code": "backup", "label": "Backup e mirror", "size_bytes": 8192, "size_label": "8.0 KiB", "percent": 100}],
        "dominant_category": {"code": "backup", "label": "Backup e mirror", "size_label": "8.0 KiB", "percent": 100},
        "top_paths": [{"display_path": "backup/mirror", "size_label": "8.0 KiB"}],
        "largest_files": [{"display_path": "backup/mirror/atto.pdf", "size_label": "8.0 KiB"}],
        "recommendations": ["Backup e mirror sopra 256 MiB: analizzare retention e compattazione prima di creare nuove copie."],
        "links": {"detail": "/admin/studi/studio-a", "database": "/admin/studi/studio-a/database"},
    }
    monkeypatch.setattr(superficie, "build_server_maintenance_surface", lambda: {"tenants": [studio], "summary": {"tenant_count": 1}})
    chiamate = []
    monkeypatch.setattr(
        superficie,
        "run_storage_compaction",
        lambda **kw: chiamate.append(kw) or {"applied": kw["apply"], "tenant_slug": kw["tenant_slug"], "hardlinked_files": 2, "physical_duplicate_files": 2, "bytes_reclaimable_label": "4 KiB", "bytes_reclaimed_label": "4 KiB"},
    )
    with app.test_client() as client:
        _login_superadmin(client)
        corpo = client.get(BASE).get_json()
        tabella = next(s for s in corpo["sections"] if s["kind"] == "table" and s["title"] == "Consumi per studio")
        riga = tabella["rows"][0]
        assert riga["href"] == "/admin/studi/studio-a"
        assert "copie speculari" in riga["cells"]["dominant"] and "retention" not in riga["cells"]["advice"]
        azioni = {a["key"]: a for a in riga["actions"]}
        # Lo studio viaggia come `slug`: `tenant_slug` e' respinto dal presidio delle API /api/v1/ui/*.
        assert azioni["analizza-compattazione"]["params"] == {"slug": "studio-a"}
        assert azioni["compatta"]["params"] == {"slug": "studio-a"} and azioni["compatta"]["confirm"]

        archivio = _azione(client, "apri-archivio-studio", params=azioni["apri-archivio-studio"]["params"]).get_json()
        assert archivio["ok"] is True and archivio["navigate"] == "/admin/studi/studio-a/database"

        analisi = _azione(client, "analizza-compattazione", params=azioni["analizza-compattazione"]["params"]).get_json()
        applicata = _azione(client, "compatta", params=azioni["compatta"]["params"]).get_json()
        globale = _azione(client, "compatta").get_json()
    assert chiamate == [{"apply": False, "tenant_slug": "studio-a"}, {"apply": True, "tenant_slug": "studio-a"}, {"apply": True, "tenant_slug": ""}]
    assert analisi["ok"] is True and analisi["tone"] == "info" and "2 file da compattare" in analisi["message"]
    assert applicata["ok"] is True and applicata["tone"] == "success" and "2 file compattati ora" in applicata["message"]
    assert any(s["title"] == "Compattazione applicata per studio-a" for s in applicata["sections"])
    assert globale["ok"] is True


def test_analisi_eseguite_senza_modifiche(app, monkeypatch):
    """Le analisi leggono e basta: girano con i servizi veri e rispondono con il loro esito."""
    import web.services.censimento_spazio as censimento

    db = Path(app.config["PCT_DATA_ROOT"]) / "tenants" / "studio-prova" / "studio.db"
    prima = db.read_bytes()
    with app.test_client() as client:
        _login_superadmin(client)
        for chiave in sorted(ANALISI):
            esito = _azione(client, chiave).get_json()
            assert esito["ok"] is True, (chiave, esito["message"])
            assert esito["tone"] in {"info", "warning"}, chiave
            assert esito["message"], chiave

        # Senza censimento notturno si dice come ottenerlo; con il censimento se ne mostra il risultato.
        assert "Nessun censimento dello spazio disponibile" in _azione(client, "analizza-manutenzione-professionale").get_json()["message"]
        letti = []
        risultato = {"applied": False, "bytes_reclaimable_label": "3 GiB", "backup_retention": {"archives_to_delete": 2}, "errors": []}
        monkeypatch.setattr(censimento, "ultimo_censimento", lambda cfg: letti.append(cfg) or {"eseguito_il": datetime.now(UTC).isoformat(), "risultato": risultato})
        letto = _azione(client, "analizza-manutenzione-professionale").get_json()
    assert db.read_bytes() == prima
    assert letti and isinstance(letti[0], dict)
    assert letto["tone"] == "info" and "3 GiB" in letto["message"] and "scansione di 0 ore fa" in letto["message"]
    assert letto["sections"][0]["title"] == "Analisi della manutenzione professionale"


def _finto(registro: list, nome: str, risultato: dict):
    def chiamata(*args, **kwargs):
        registro.append((nome, args, kwargs))
        return risultato

    return chiamata


def test_azioni_che_modificano_chiamano_i_servizi_storici(app, monkeypatch):
    import web.services.server_maintenance_surface as superficie
    from pct import manutenzione_database, manutenzione_dati_json
    from web.services import chunk_rag_runtime, collegamenti_pec_runtime

    radice = Path(app.config["PCT_DATA_ROOT"])
    registro: list = []
    esito_studi = {"ok": True, "messaggio": "Fatto.", "studi": [{"studio": "studio-prova"}], "errori": []}
    finti = {
        (manutenzione_dati_json, "esamina_tutti"): {**esito_studi, "riscrittura_eseguita": True, "righe_riscritte": 3, "mb_in_eccesso": 1.5},
        (manutenzione_database, "esamina_tutti"): {**esito_studi, "compattazione_eseguita": True},
        (collegamenti_pec_runtime, "esamina_tutti"): {**esito_studi, "ricollegamento_eseguito": True},
        (chunk_rag_runtime, "esamina_tutti"): {**esito_studi, "rispezzatura_eseguita": True},
        (superficie, "run_max_storage_optimization"): {"applied": True, "bytes_reclaimed_label": "1 GiB"},
        (superficie, "run_all_backup_retention"): {"applied": True, "archives_deleted": 4, "bytes_reclaimed_label": "2 GiB", "errors": []},
        (superficie, "trigger_backup"): {"ok": True, "pid": 4242, "log": "/tmp/backup.log"},
        (superficie, "run_docker_prune"): {"applied": True, "error": None, "bytes_reclaimed_label": "5 GiB", "stdout": ""},
        (superficie, "run_inactive_tenant_cleanup"): {"applied": True, "directories_deleted": 1, "bytes_reclaimed_label": "1 MiB", "errors": []},
        (superficie, "run_professional_server_maintenance"): {"applied": True, "bytes_reclaimed_label": "9 GiB", "errors": ["backup-1.zip: archivio non rimosso"]},
        (superficie, "run_system_log_cleanup"): {"applied": True, "before": "1.0G", "after": "256.0M", "errors": []},
        (superficie, "run_normativa_global_cleanup"): {"applied": True, "bytes_reclaimed_label": "700 MiB", "errors": []},
    }
    for (modulo, nome), risultato in finti.items():
        monkeypatch.setattr(modulo, nome, _finto(registro, f"{modulo.__name__}.{nome}", risultato))

    attese = {
        "applica-copia-doppia-fascicoli": ("pct.manutenzione_dati_json.esamina_tutti", (radice,), {"riscrivi": True}, "success"),
        "applica-compattazione-database": ("pct.manutenzione_database.esamina_tutti", (radice,), {"compattare": True}, "success"),
        "applica-collegamenti-pec": ("web.services.collegamenti_pec_runtime.esamina_tutti", None, {"ricollegare": True}, "success"),
        "applica-chunk-rag": ("web.services.chunk_rag_runtime.esamina_tutti", None, {"rispezzare": True}, "success"),
        "applica-ottimizzazione-massima": ("web.services.server_maintenance_surface.run_max_storage_optimization", (), {"apply": True, "tenant_slug": ""}, "success"),
        "applica-retention-backup": ("web.services.server_maintenance_surface.run_all_backup_retention", (), {"apply": True}, "success"),
        "backup-ora": ("web.services.server_maintenance_surface.trigger_backup", (), {}, "success"),
        "docker-prune": ("web.services.server_maintenance_surface.run_docker_prune", (), {"dry_run": False}, "success"),
        "elimina-cartelle-escluse": ("web.services.server_maintenance_surface.run_inactive_tenant_cleanup", (), {"apply": True}, "success"),
        "applica-manutenzione-professionale": ("web.services.server_maintenance_surface.run_professional_server_maintenance", (), {"apply": True}, "warning"),
        "pulisci-log-sistema": ("web.services.server_maintenance_surface.run_system_log_cleanup", (), {"apply": True}, "success"),
        "pulisci-normativa-globale": ("web.services.server_maintenance_surface.run_normativa_global_cleanup", (), {"apply": True}, "success"),
    }
    with app.test_client() as client:
        _login_superadmin(client)
        for chiave, (nome, argomenti, parametri, tono) in attese.items():
            registro.clear()
            esito = _azione(client, chiave).get_json()
            assert esito["ok"] is True and esito["tone"] == tono, (chiave, esito)
            assert esito["sections"], chiave
            assert len(registro) == 1 and registro[0][0] == nome, (chiave, registro)
            _nome, args, kwargs = registro[0]
            assert kwargs == parametri, chiave
            if argomenti is not None:
                assert args == argomenti, chiave
            else:
                # Le analisi per studio ricevono l'applicazione Flask, come nella vista storica.
                assert len(args) == 1 and args[0].name == app.name, chiave

    assert "Riscritte 3 righe" in _messaggio(app, "applica-copia-doppia-fascicoli")
    assert "processo 4242" in _messaggio(app, "backup-ora")


def _messaggio(app, chiave: str) -> str:
    with app.test_client() as client:
        _login_superadmin(client)
        return _azione(client, chiave).get_json()["message"]


def test_esiti_negativi_e_errori_imprevisti(app, monkeypatch):
    import web.services.server_maintenance_surface as superficie

    monkeypatch.setattr(superficie, "trigger_backup", lambda: {"ok": False, "error": "Script backup.sh non trovato.", "pid": None})
    monkeypatch.setattr(superficie, "run_docker_prune", lambda **kw: {"applied": False, "error": "Pulizia Docker non completata.", "bytes_reclaimed_label": "0 B"})

    def _guasto(**_kw):
        raise RuntimeError("percorso segreto /opt/iusentra esploso")

    monkeypatch.setattr(superficie, "run_normativa_global_cleanup", _guasto)
    with app.test_client() as client:
        _login_superadmin(client)
        backup = _azione(client, "backup-ora").get_json()
        servizi = _azione(client, "docker-prune").get_json()
        guasto = _azione(client, "pulisci-normativa-globale").get_json()
        sconosciuta = _azione(client, "sconosciuta").get_json()
    assert backup["ok"] is False and backup["tone"] == "danger" and "Script backup.sh non trovato." in backup["message"]
    assert servizi["ok"] is True and servizi["tone"] == "warning"
    assert servizi["sections"][0]["title"] == "Errore nella pulizia della memoria temporanea dei servizi"
    assert (guasto["ok"], guasto["tone"], guasto["sections"]) == (False, "danger", [])
    assert guasto["message"] == "Errore durante la pulizia della normativa globale." and "segreto" not in str(guasto)
    assert sconosciuta["ok"] is False


def test_lessico_italiano_e_percorsi_del_server():
    from web.services.react_piattaforma_pagina_server_manutenzione_lessico import it, percorso

    assert it("Backup mirror interni sopra 512 MiB: verificare retention; la compattazione e' utile solo se l'analisi segnala file da compattare.").startswith("Copie speculari interne")
    assert it("12 chunk su 40 in attesa verrebbero scartati") == "12 frammenti su 40 in attesa verrebbero scartati"
    assert it("1.2 GiB recuperabili con un VACUUM. Nessuna modifica eseguita.") == "1.2 GiB recuperabili con una compattazione. Nessuna modifica eseguita."
    assert it("Area principale: Backup e mirror (3 GiB).") == "Area principale: Backup e copie speculari (3 GiB)."
    # Il superamministratore vede i percorsi del server, come nella vista storica.
    assert percorso("/opt/iusentra/backups") == "/opt/iusentra/backups"
    assert percorso("/data/tenants/studio-a") == "/data/tenants/studio-a"
