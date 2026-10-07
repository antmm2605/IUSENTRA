"""La presa visione sopravvive agli accessi, senza risolvere la discordanza."""
import pytest

from pct.registro_letture import RegistroLetture
from pct.discordanze_letture_repository import RegistroDiscordanze
from pct.controllo_studio.letture import LettureControllo


def _ambiente(tmp_path):
    registro = RegistroLetture(tmp_path / "letture.db")
    discordanze = RegistroDiscordanze(registro)
    discordanze.riconcilia("studio-a", "f1", "cf", [{"chiave": "c1", "titolo": "CF discordante", "valore": "uno"}])
    letture = LettureControllo(registro, "studio-a")
    voce = discordanze.aperte("studio-a")["voci"][0]
    return registro, discordanze, letture, {"fascicoloId": "f1", "codice": "cf", "chiave": "c1", "revisione": voce["revisione"]}


def test_persistenza_idempotenza_e_isolamento(tmp_path):
    registro, discordanze, letture, voce = _ambiente(tmp_path)
    assert letture.non_viste("utente-a") == 1
    assert letture.conferma("utente-a", [voce]) == 1
    assert letture.conferma("utente-a", [voce]) == 1
    nuova_sessione = LettureControllo(RegistroLetture(tmp_path / "letture.db"), "studio-a")
    assert nuova_sessione.non_viste("utente-a") == 0
    assert nuova_sessione.non_viste("utente-b") == 1
    assert LettureControllo(registro, "studio-b").viste("utente-a") == {}
    assert discordanze.aperte("studio-a")["totale"] == 1
    with registro.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM controllo_discordanze_viste").fetchone()[0] == 1
        assert c.execute("SELECT stato FROM letture_discordanze").fetchone()[0] == "aperta"


def test_nuova_revisione_richiede_nuova_presa_visione(tmp_path):
    _, discordanze, letture, voce = _ambiente(tmp_path)
    letture.conferma("utente-a", [voce])
    discordanze.riconcilia("studio-a", "f1", "cf", [{"chiave": "c1", "titolo": "CF discordante", "valore": "due"}])
    assert letture.non_viste("utente-a") == 1
    with pytest.raises(ValueError, match="cambiata"):
        letture.conferma("utente-a", [voce])
    voce["revisione"] = discordanze.aperte("studio-a")["voci"][0]["revisione"]
    letture.conferma("utente-a", [voce])
    assert letture.non_viste("utente-a") == 0


def test_selezione_invalida_non_salva_parzialmente(tmp_path):
    _, _, letture, voce = _ambiente(tmp_path)
    with pytest.raises(ValueError):
        letture.conferma("utente-a", [voce, {**voce, "revisione": "obsoleta"}])
    assert letture.viste("utente-a") == {}


def test_schema_di_presa_visione_identico_nei_due_backend():
    from pathlib import Path
    import pct.controllo_studio.letture as modulo
    root = Path(modulo.__file__).resolve().parent.parent / "sql"
    assert (root / "20261005_controllo_letture.sql").read_bytes() == (root / "20261005_controllo_letture_postgres.sql").read_bytes()
