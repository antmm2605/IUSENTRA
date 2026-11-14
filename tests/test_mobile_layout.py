from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


def _login_admin(cfg: dict) -> None:
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="admin-mobile",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )
