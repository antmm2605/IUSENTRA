"""Clienti: eliminazione con fascicoli archiviati, permessi di scrittura, CF/P.IVA e conflitto di interessi."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.auth import RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.identificativi_fiscali import controllo_codice_fiscale, controllo_partita_iva, formato_codice_fiscale
from pct.soggetti import GestioneSoggetti
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app
from web.services.fascicolo_controparti_aggiuntive import collega_controparti_aggiuntive, leggi_controparti_aggiuntive

JSON = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def _app(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _create_user(app, "admin2", "Admin12345!")
    _create_user(app, "praticante", "Pratica123!", ruolo=RuoloUtente.PRATICANTE)
    _create_user(app, "senzaclienti", "Senza12345!", ruolo=RuoloUtente.COLLABORATORE, permessi_negati=["clienti.leggi"])
    return app


def _fascicoli(app):
    return GestioneFascicoli(app.config["FASCICOLI_DB"], documents_dir=app.config["FASCICOLI_DOCS"], archive_dir=app.config["FASCICOLI_ARCH"])


def _cliente_con_fascicolo_archiviato(app):
    cliente = GestioneClienti(app.config["CLIENTI_DB"]).nuovo(TipoCliente.PERSONA_FISICA, nome="Anna", cognome="Neri")
    gf = _fascicoli(app)
    fascicolo = gf.nuovo("Pratica chiusa", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente=cliente.nome_completo)
    gf.definisci(fascicolo.id, esito_finale="Conclusa")
    gf.archivia(fascicolo.id, crea_zip=False)
    assert gf.tutti() == []  # l'elenco ordinario esclude gli archiviati
    return cliente.id


def test_cliente_con_fascicolo_archiviato_non_si_elimina(tmp_path):
    app = _app(tmp_path)
    id_cliente = _cliente_con_fascicolo_archiviato(app)
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        react = client.post("/api/v1/ui/clienti/delete", json={"ids": [id_cliente]})
        assert react.status_code == 409
        assert "art. 31 D.Lgs. 231/2007" in react.get_json()["message"]
        classica = client.post(f"/clienti/{id_cliente}/elimina", headers=JSON)
        assert classica.status_code == 409
    assert GestioneClienti(app.config["CLIENTI_DB"]).get(id_cliente) is not None


def test_rotte_storiche_richiedono_permessi_clienti(tmp_path):
    app = _app(tmp_path)
    gc = GestioneClienti(app.config["CLIENTI_DB"])
    cliente = gc.nuovo(TipoCliente.PERSONA_FISICA, nome="Luca", cognome="Bianchi")
    with app.test_client() as client:
        _login(client, "praticante", "Pratica123!")
        assert client.post(f"/clienti/{cliente.id}/elimina", headers=JSON).status_code == 403
        modifica = client.post(f"/clienti/{cliente.id}/modifica", data={"nome": "Cambiato"}, headers=JSON)
        assert modifica.status_code == 403
        nuovo = client.post("/clienti/nuovo", data={"tipo": "PERSONA_FISICA", "nome": "X", "cognome": "Y"}, headers=JSON)
        assert nuovo.status_code == 403
    ricaricato = GestioneClienti(app.config["CLIENTI_DB"])
    assert ricaricato.get(cliente.id).nome == "Luca"
    assert len(ricaricato.tutti(stato=None)) == 1


def test_api_react_clienti_rispetta_permesso_e_condivisione(tmp_path):
    app = _app(tmp_path)
    gc = GestioneClienti(app.config["CLIENTI_DB"])
    visibile = gc.nuovo(TipoCliente.PERSONA_FISICA, nome="Condiviso", cognome="Uno")
    riservato = gc.nuovo(TipoCliente.PERSONA_FISICA, nome="Riservato", cognome="Due")
    from pct.auth import GestioneUtenti
    from pct.condivisione import GestioneCondivisioni, RuoloCondivisione

    utenti = GestioneUtenti(db_path=app.config["AUTH_DB"], audit_path=app.config["AUDIT_DB"], secret_key=app.secret_key,
                            bootstrap_admin_password="admin", bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"])
    utente = next(u for u in utenti.tutti() if u.username == "senzaclienti")
    GestioneCondivisioni(app.config["CONDIVISIONI_DB"], app.config["SECRET_KEY"]).condividi(
        visibile.id, utente.id, utente.username, utente.nome_completo, RuoloCondivisione.LETTURA, condiviso_da="admin2",
    )
    with app.test_client() as client:
        _login(client, "senzaclienti", "Senza12345!")
        elenco = client.get("/api/v1/ui/clienti").get_json()
        ids = {item["id"] for item in elenco["items"]}
        assert riservato.id not in ids
        assert visibile.id in ids
        assert client.get(f"/api/v1/ui/clienti/{visibile.id}/cartella").status_code == 200
        assert client.get(f"/api/v1/ui/clienti/{riservato.id}/cartella").status_code == 403
        assert client.get(f"/api/v1/ui/clienti/{riservato.id}/modifica").status_code == 403
        html = {"Accept": "text/html"}
        pagina_riservata = client.get(f"/clienti/{riservato.id}", headers=html)
        assert pagina_riservata.status_code == 302
        assert client.get(f"/clienti/{visibile.id}", headers=html).status_code == 200
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        ids = {item["id"] for item in client.get("/api/v1/ui/clienti").get_json()["items"]}
        assert {visibile.id, riservato.id} <= ids


@pytest.mark.parametrize(
    "valore,atteso",
    [
        ("RSSMRA80A01H501U", True),   # esempio del D.M. 23/12/1976, controllo corretto
        ("RSSMRA80A01H501X", False),  # carattere di controllo errato
        ("80015010723", True),        # Comune di Bari, codice numerico
        ("80015010724", False),
    ],
)
def test_carattere_di_controllo_codice_fiscale(valore, atteso):
    assert formato_codice_fiscale(valore) is True
    assert controllo_codice_fiscale(valore) is atteso


def test_cifra_di_controllo_partita_iva():
    assert controllo_partita_iva("00488410010") is True
    assert controllo_partita_iva("00488410011") is False


def test_ente_con_codice_fiscale_numerico_e_controllo_al_salvataggio(tmp_path):
    gc = GestioneClienti(str(tmp_path / "clienti.json"))
    ente = gc.nuovo(TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Comune di Bari", codice_fiscale="80015010723", verifica_controllo=True)
    assert ente.codice_fiscale == "80015010723"
    # La scheda storica resta salvabile anche senza toccare il CF.
    gc.aggiorna(ente.id, verifica_controllo=True, codice_fiscale="80015010723", note="ok")
    with pytest.raises(ValueError, match="carattere di controllo"):
        gc.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi", codice_fiscale="RSSMRA80A01H501X", verifica_controllo=True)
    with pytest.raises(ValueError, match="cifra di controllo"):
        gc.nuovo(TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Beta Srl", partita_iva="00488410011", verifica_controllo=True)


def test_controparte_gia_cliente_viene_collegata_con_avviso(tmp_path):
    soggetti = GestioneSoggetti(str(tmp_path / "soggetti.json"), str(tmp_path / "parti.json"))
    proprio = SimpleNamespace(id="cli-1", nome="", cognome="", ragione_sociale="Alfa Spa", codice_fiscale="", partita_iva="00488410010")
    altro = SimpleNamespace(id="cli-2", nome="", cognome="", ragione_sociale="Beta Srl", codice_fiscale="", partita_iva="80015010723")
    controparti = leggi_controparti_aggiuntive(
        '[{"nome": "Alfa Spa", "identificativo": "00488410010"}, {"nome": "Beta Srl", "identificativo": "80015010723"}]',
        gestore_soggetti=soggetti,
    )
    esito = collega_controparti_aggiuntive(soggetti, [proprio, altro], "fasc-1", controparti, id_cliente_fascicolo="cli-1")
    assert esito.escluse_cliente == ("Alfa Spa",)
    assert esito.collegate == ("Beta Srl",)
    assert esito.conflitti == ("Beta Srl",)
    assert "conflitto di interessi" in esito.messaggio() and "art. 24" in esito.messaggio()


def test_apertura_fascicolo_con_controparte_cliente_mostra_avviso(tmp_path):
    app = _app(tmp_path)
    gc = GestioneClienti(app.config["CLIENTI_DB"])
    assistito = gc.nuovo(TipoCliente.PERSONA_FISICA, nome="Maria", cognome="Verdi")
    gc.nuovo(TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Gamma Srl", partita_iva="00488410010")
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        risposta = client.post(
            "/fascicoli/nuovo",
            data={"titolo": "Causa contro Gamma", "tipo": "CIVILE", "id_cliente": assistito.id,
                  "controparte": "Gamma Srl", "cf_controparte": "00488410010", "crea_soggetto_controparte": "1"},
            headers=JSON,
        )
        assert risposta.status_code == 200, risposta.get_data(as_text=True)
        assert "conflitto di interessi" in risposta.get_json()["message"]
