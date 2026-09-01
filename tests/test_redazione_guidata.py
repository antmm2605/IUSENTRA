"""Test della Redazione Atti guidata: contesto reale, suggerimenti, normativa, generazione.

Copre i criteri di accettazione del modulo: dati reali dal fascicolo (mai
inventati), ufficio giudiziario preso dal fascicolo, suggerimento tipo atto da
materia/pratica, riferimenti normativi per template modificabili dallo studio,
campi mancanti evidenziati e mai compilati con valori finti, isolamento
cliente/fascicolo.
"""
from __future__ import annotations

from time import perf_counter
from types import SimpleNamespace

import pytest

from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.storage import StudioDB
from pct.redazione_contesto import (
    anteprima_campi_modello,
    applica_marcatori_dati_mancanti,
    condizioni_dal_fascicolo,
    contributo_unificato_da_fascicolo,
    estrai_contesto_fascicolo,
    marcatore_dato_mancante,
)
from pct.redazione_normativa import (
    disattiva_riferimento,
    riferimenti_per_modello,
    salva_riferimento,
    tutti_riferimenti,
)
from pct.redazione_normativa import testo_diritto_da_riferimenti as costruisci_testo_diritto
from pct.redazione_suggerimenti import catalogo_per_scelta_manuale, suggerisci_modelli
from web.services.react_redazione_guidata_bridge import (
    build_redazione_anteprima_payload,
    build_redazione_clienti_payload,
    build_redazione_contesto_payload,
    build_redazione_fascicoli_payload,
    evidenzia_dati_mancanti_html,
    prepara_payload_generazione,
    verifica_fascicolo_del_cliente,
)


@pytest.fixture()
def repos(tmp_path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "clienti.json"))
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    return clienti, fascicoli


@pytest.fixture()
def cliente_mario(repos):
    clienti, _ = repos
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA70B10G288K",
    )
    return clienti.aggiorna(
        cliente.id,
        data_nascita="1970-02-10",
        luogo_nascita="Palmi",
        provincia_nascita="RC",
        recapiti=Recapiti(email="mario.rossi@example.test", pec="mario.rossi@pec.example.test", telefono="0966123456"),
        indirizzo_residenza=Indirizzo(via="Via Roma", civico="10", cap="89015", comune="Palmi", provincia="RC"),
    )


@pytest.fixture()
def fascicolo_preliminare(repos, cliente_mario):
    _, fascicoli = repos
    fascicolo = fascicoli.nuovo(
        titolo="Risoluzione contratto preliminare immobile",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente_mario.id,
        nome_cliente=cliente_mario.nome_completo,
    )
    return fascicoli.aggiorna(
        fascicolo.id,
        oggetto="Inadempimento del preliminare di compravendita: caparra confirmatoria e diffida ad adempiere",
        note="Mediazione esperita con esito negativo. Mancato pagamento del saldo prezzo entro il termine per il rogito.",
        tribunale="Tribunale di Palmi",
        controparte="Bianchi Costruzioni Srl",
        cf_controparte="01234567890",
        valore_causa=80000.0,
        area_pratica="contratti",
    )


CONFIG_STUDIO = {
    "STUDIO_NOME": "Studio Legale Verdi",
    "STUDIO_AVVOCATO": "Avv. Giulia Verdi",
    "STUDIO_CF": "VRDGLI80A41H501X",
    "STUDIO_PIVA": "09876543210",
    "STUDIO_INDIRIZZO": "Corso Garibaldi 5, Palmi (RC)",
    "PCT_STUDIO_PEC": "studio.verdi@pec.example.test",
}


def _utente():
    return SimpleNamespace(id="USR1", username="g.verdi", nome_completo="Avv. Giulia Verdi")


# ---------------------------------------------------------------------------
# Selezione cliente e fascicolo (passi 1-2)
# ---------------------------------------------------------------------------


def test_clienti_reali_con_conteggio_fascicoli(repos, cliente_mario, fascicolo_preliminare):
    clienti, fascicoli = repos
    payload = build_redazione_clienti_payload(get_clienti=lambda: clienti, get_fascicoli=lambda: fascicoli)
    assert payload["ok"] is True
    voci = {voce["id"]: voce for voce in payload["clienti"]}
    assert cliente_mario.id in voci
    assert voci[cliente_mario.id]["label"] == "Rossi Mario"
    assert voci[cliente_mario.id]["fascicoli"] == 1


def test_fascicoli_filtrati_per_cliente(repos, cliente_mario, fascicolo_preliminare):
    clienti, fascicoli = repos
    altro = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Luca", cognome="Neri", codice_fiscale="NRELCU85C15H501Z")
    fascicoli.nuovo(titolo="Pratica di Neri", tipo=TipoFascicolo.CIVILE, id_cliente=altro.id, nome_cliente="Luca Neri")

    payload = build_redazione_fascicoli_payload(get_fascicoli=lambda: fascicoli, cliente_id=cliente_mario.id)
    assert payload["ok"] is True
    assert [voce["id"] for voce in payload["fascicoli"]] == [fascicolo_preliminare.id]
    assert payload["fascicoli"][0]["ufficio"] == "Tribunale di Palmi"


def test_isolamento_fascicolo_di_altro_cliente(repos, cliente_mario, fascicolo_preliminare):
    assert verifica_fascicolo_del_cliente(fascicolo_preliminare, cliente_mario.id) is True
    assert verifica_fascicolo_del_cliente(fascicolo_preliminare, "ALTRO_CLIENTE") is False


# ---------------------------------------------------------------------------
# Contesto reale del fascicolo (passo 3)
# ---------------------------------------------------------------------------


def test_contesto_legge_dati_reali_e_traccia_fonti(cliente_mario, fascicolo_preliminare):
    contesto = estrai_contesto_fascicolo(fascicolo=fascicolo_preliminare, cliente=cliente_mario, config=CONFIG_STUDIO)
    ufficio = contesto["fascicolo"]["ufficioGiudiziario"]
    assert ufficio["valore"] == "Tribunale di Palmi"
    assert ufficio["mancante"] is False
    assert ufficio["fonte"] == {"tabella": "fascicoli", "id": fascicolo_preliminare.id, "campo": "tribunale"}
    assert contesto["cliente"]["denominazione"]["valore"] == "Rossi Mario"
    assert contesto["cliente"]["codiceFiscale"]["valore"] == "RSSMRA70B10G288K"
    assert contesto["cliente"]["residenza"]["valore"].startswith("Via Roma 10")
    assert contesto["controparti"][0]["denominazione"]["valore"] == "Bianchi Costruzioni Srl"
    assert contesto["studio"]["avvocato"]["valore"] == "Avv. Giulia Verdi"
    # R.G. assente nel fascicolo: deve risultare mancante, non inventato.
    assert contesto["fascicolo"]["rg"]["mancante"] is True


def test_condizioni_rilevate_dai_dati_reali(fascicolo_preliminare):
    condizioni = condizioni_dal_fascicolo(fascicolo_preliminare)
    assert condizioni["preliminare"] is True
    assert condizioni["caparra"] is True
    assert condizioni["mediazione"] is True
    assert condizioni["diffida"] is True
    assert condizioni["locazione"] is False


def test_contributo_unificato_da_valore_causa(fascicolo_preliminare, repos):
    esito = contributo_unificato_da_fascicolo(fascicolo_preliminare)
    assert esito["disponibile"] is True
    assert esito["totale"] == pytest.approx(759.0)
    assert "115/2002" in esito["fonte"]

    _, fascicoli = repos
    senza_valore = fascicoli.aggiorna(fascicolo_preliminare.id, valore_causa=0.0)
    esito_mancante = contributo_unificato_da_fascicolo(senza_valore)
    assert esito_mancante["disponibile"] is False
    assert esito_mancante["totale"] is None


# ---------------------------------------------------------------------------
# Suggerimento tipo atto (passo 3)
# ---------------------------------------------------------------------------


def test_suggerimento_citazione_per_preliminare(fascicolo_preliminare):
    suggerimenti = suggerisci_modelli(fascicolo_preliminare)
    assert suggerimenti, "Il fascicolo reale deve produrre suggerimenti"
    primo = suggerimenti[0]
    assert primo["code"] == "CIV_CIT_001"
    assert primo["name"] == "Atto di Citazione"
    assert any("preliminare" in motivo.lower() for motivo in primo["motivi"])


def test_suggerimenti_per_materia_e_pratica(repos, cliente_mario):
    _, fascicoli = repos
    sfratto = fascicoli.nuovo(titolo="Sfratto per morosita' conduttore", tipo=TipoFascicolo.CIVILE, id_cliente=cliente_mario.id)
    sfratto = fascicoli.aggiorna(sfratto.id, oggetto="Canoni di locazione non pagati, sfratto per morosita'")
    codici_sfratto = [voce["code"] for voce in suggerisci_modelli(sfratto)]
    assert codici_sfratto[0] in {"CIV_SFRINT_001", "CIV_CONVSFR_001"}

    lavoro = fascicoli.nuovo(titolo="Impugnazione licenziamento", tipo=TipoFascicolo.LAVORO, id_cliente=cliente_mario.id)
    lavoro = fascicoli.aggiorna(lavoro.id, id_pratica="licenziamento", oggetto="Licenziamento disciplinare illegittimo")
    suggeriti_lavoro = suggerisci_modelli(lavoro)
    assert suggeriti_lavoro[0]["code"] == "LAV_IMPLIC_001"
    assert any("pratica collegata" in motivo.lower() for motivo in suggeriti_lavoro[0]["motivi"])

    famiglia = fascicoli.nuovo(titolo="Separazione consensuale coniugi", tipo=TipoFascicolo.FAMIGLIA, id_cliente=cliente_mario.id)
    famiglia = fascicoli.aggiorna(famiglia.id, oggetto="Separazione consensuale")
    assert suggerisci_modelli(famiglia)[0]["code"] == "FAM_SEPC_001"


def test_catalogo_completo_per_scelta_manuale():
    catalogo = catalogo_per_scelta_manuale()
    aree = {gruppo["area"] for gruppo in catalogo}
    assert {"CIVILE", "PENALE", "AMMINISTRATIVO", "TRIBUTARIO", "FAMIGLIA", "LAVORO", "STRAGIUDIZIALE"} <= aree
    totale_modelli = sum(len(gruppo["modelli"]) for gruppo in catalogo)
    assert totale_modelli >= 90, "Il catalogo strutturato deve restare completo"


# ---------------------------------------------------------------------------
# Riferimenti normativi per template (registro modificabile)
# ---------------------------------------------------------------------------


def test_normativa_citazione_processuale(tmp_path, fascicolo_preliminare):
    condizioni = condizioni_dal_fascicolo(fascicolo_preliminare)
    normativa = riferimenti_per_modello(
        "CIV_CIT_001", materia="CIVILE", condizioni=condizioni, db_path=str(tmp_path / "norme.json")
    )
    processuali = {voce["riferimento"] for voce in normativa["processuali"]}
    assert "art. 163 c.p.c." in processuali
    assert "art. 163-bis c.p.c." in processuali
    assert "art. 166 c.p.c." in processuali
    assert "art. 167 c.p.c." in processuali
    assert "art. 168-bis c.p.c." in processuali
    # Mediazione presente nel fascicolo -> art. 12-bis d.lgs. 28/2010 suggerito.
    assert "art. 12-bis d.lgs. 28/2010" in processuali


def test_normativa_risoluzione_preliminare_sostanziale(tmp_path, fascicolo_preliminare):
    condizioni = condizioni_dal_fascicolo(fascicolo_preliminare)
    normativa = riferimenti_per_modello(
        "CIV_CIT_001", materia="CIVILE", condizioni=condizioni, db_path=str(tmp_path / "norme.json")
    )
    sostanziali = {voce["riferimento"] for voce in normativa["sostanziali"]}
    for atteso in ("art. 1453 c.c.", "art. 1454 c.c.", "art. 1455 c.c.", "art. 1458 c.c.", "art. 1385 c.c.", "art. 2932 c.c.", "art. 1223 c.c.", "art. 1227 c.c."):
        assert atteso in sostanziali, f"manca {atteso}"
    # Ogni riferimento deve spiegare perche' e' stato suggerito.
    assert all(voce["motivo_contestuale"] for voce in normativa["sostanziali"])


def test_normativa_condizionale_esclusa_senza_presupposti(tmp_path, repos, cliente_mario):
    _, fascicoli = repos
    neutro = fascicoli.nuovo(titolo="Causa generica", tipo=TipoFascicolo.CIVILE, id_cliente=cliente_mario.id)
    normativa = riferimenti_per_modello(
        "CIV_CIT_001", materia="CIVILE",
        condizioni=condizioni_dal_fascicolo(neutro),
        db_path=str(tmp_path / "norme.json"),
    )
    tutti = {voce["riferimento"] for voce in normativa["processuali"] + normativa["sostanziali"]}
    assert "art. 1385 c.c." not in tutti, "La caparra non va citata se non risulta dal fascicolo"
    assert "art. 12-bis d.lgs. 28/2010" not in tutti, "La mediazione non va citata se non risulta dal fascicolo"


def test_registro_normativo_modificabile_dallo_studio(tmp_path):
    db = str(tmp_path / "norme.json")
    salvato = salva_riferimento(
        {
            "fonte": "c.c.",
            "articolo": "1490",
            "rubrica": "Garanzia per i vizi della cosa venduta",
            "ambito": "sostanziale",
            "motivo": "Vizi della cosa venduta ricorrenti nelle compravendite dello studio.",
            "modelli": ["CIV_CIT_001"],
        },
        db_path=db,
    )
    assert salvato.origine == "studio"
    riferimenti = riferimenti_per_modello("CIV_CIT_001", db_path=db)
    assert any(voce["id"] == salvato.id for voce in riferimenti["sostanziali"])

    assert disattiva_riferimento("cpc_86", db_path=db) is True
    dopo = riferimenti_per_modello("CIV_CIT_001", db_path=db)
    assert all(voce["id"] != "cpc_86" for voce in dopo["processuali"])
    # I seed restano intatti: la disattivazione vive solo nell'override.
    assert any(rif.id == "cpc_86" for rif in tutti_riferimenti(db_path=str(tmp_path / "altro.json")))


def test_testo_in_diritto_da_riferimenti(tmp_path, fascicolo_preliminare):
    normativa = riferimenti_per_modello(
        "CIV_CIT_001", materia="CIVILE",
        condizioni=condizioni_dal_fascicolo(fascicolo_preliminare),
        db_path=str(tmp_path / "norme.json"),
    )
    testo = costruisci_testo_diritto(normativa)
    assert "Quanto al merito:" in testo
    assert "art. 1453 c.c." in testo
    assert "Quanto al rito:" in testo
    assert "art. 163 c.p.c." in testo


# ---------------------------------------------------------------------------
# Anteprima campi e generazione (passi 4-6)
# ---------------------------------------------------------------------------


def test_anteprima_campi_compilati_da_dati_reali(cliente_mario, fascicolo_preliminare, tmp_path):
    payload = build_redazione_anteprima_payload(
        model_code="CIV_CIT_001",
        fascicolo=fascicolo_preliminare,
        cliente=cliente_mario,
        utente=_utente(),
        config=CONFIG_STUDIO,
        normativa_db_path=str(tmp_path / "norme.json"),
    )
    assert payload["ok"] is True
    trovati = {voce["name"]: voce for voce in payload["campiTrovati"]}
    assert trovati["court_name"]["value"] == "Tribunale di Palmi"
    assert trovati["plaintiff"]["value"] == "Rossi Mario"
    assert trovati["defendant"]["value"] == "Bianchi Costruzioni Srl"
    mancanti = {voce["name"] for voce in payload["campiMancanti"]}
    assert "hearing_date" in mancanti, "La data udienza assente deve risultare mancante, non inventata"
    assert payload["normativa"]["totale"] > 0


def test_generazione_compila_atto_con_dati_reali(repos, cliente_mario, fascicolo_preliminare):
    from pct.compilatore_atti import render_compiled_act

    from pct.fascicoli import TipoDocumento

    _, fascicoli = repos
    fascicoli.aggiungi_documento(
        fascicolo_preliminare.id,
        "contratto_preliminare.pdf",
        TipoDocumento.CONTRATTO,
        b"%PDF-1.4 contenuto del preliminare",
        caricato_da="g.verdi",
    )
    fascicolo = fascicoli.get(fascicolo_preliminare.id)

    preparazione = prepara_payload_generazione(
        model_code="CIV_CIT_001",
        fascicolo=fascicolo,
        cliente=cliente_mario,
        utente=_utente(),
        config=CONFIG_STUDIO,
        valori_utente={
            "hearing_date": "2026-10-15",
            "facts": "In data 05/01/2025 le parti sottoscrivevano contratto preliminare di compravendita.",
            "requests_or_conclusions": "Dichiarare la risoluzione del contratto preliminare per inadempimento della convenuta.",
            "evidence_means": "Interrogatorio formale del legale rappresentante della convenuta.",
        },
        riferimenti_selezionati=[
            {"ambito": "sostanziale", "riferimento": "art. 1453 c.c.", "rubrica": "Risolubilita' del contratto per inadempimento", "motivo": "Risoluzione per inadempimento."},
        ],
        conferma_bozza=False,
    )
    assert preparazione["ok"] is True, preparazione["errors"]
    testo = render_compiled_act("CIV_CIT_001", preparazione["payload"], include_timbro=False)
    assert "Rossi Mario" in testo
    assert "TRIBUNALE DI PALMI" in testo.upper()
    assert "Bianchi Costruzioni Srl" in testo
    assert "contratto_preliminare.pdf" in testo, "Gli allegati reali del fascicolo entrano nell'atto"
    assert "{{" not in testo and "}}" not in testo, "Nessun placeholder tecnico nell'atto finale"
    assert "DATO MANCANTE" not in testo, "Atto completo: nessun marcatore di dato mancante"


def test_campo_obbligatorio_mancante_bloccato_senza_conferma(cliente_mario, fascicolo_preliminare):
    preparazione = prepara_payload_generazione(
        model_code="CIV_CIT_001",
        fascicolo=fascicolo_preliminare,
        cliente=cliente_mario,
        utente=_utente(),
        config=CONFIG_STUDIO,
        valori_utente={},
        conferma_bozza=False,
    )
    assert preparazione["ok"] is False
    assert preparazione["errors"], "I campi obbligatori mancanti devono essere segnalati"
    assert any(voce["name"] == "hearing_date" for voce in preparazione["mancanti"])


def test_bozza_confermata_evidenzia_dati_mancanti_senza_inventarli(cliente_mario, fascicolo_preliminare):
    from pct.compilatore_atti import render_compiled_act

    preparazione = prepara_payload_generazione(
        model_code="CIV_CIT_001",
        fascicolo=fascicolo_preliminare,
        cliente=cliente_mario,
        utente=_utente(),
        config=CONFIG_STUDIO,
        valori_utente={},
        conferma_bozza=True,
    )
    assert preparazione["ok"] is True
    assert preparazione["marcati"], "Le etichette dei campi marcati devono essere riportate"
    testo = render_compiled_act("CIV_CIT_001", preparazione["payload"], include_timbro=False)
    assert "[DATO MANCANTE:" in testo
    html = evidenzia_dati_mancanti_html("<p>[DATO MANCANTE: Data Udienza]</p>")
    assert '<mark class="iu-dato-mancante"' in html
    assert "Data Udienza" in html


def test_evidenzia_dati_mancanti_resiste_a_input_patologico():
    html_sorgente = "<p>[DATO MANCANTE:" + ("\t" * 5_000) + "<script>alert(1)</script>]</p>"
    inizio = perf_counter()
    html = evidenzia_dati_mancanti_html(html_sorgente)
    durata = perf_counter() - inizio
    assert durata < 1.0
    assert '<mark class="iu-dato-mancante"' in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_marcatori_su_payload(cliente_mario, fascicolo_preliminare):
    payload, marcati = applica_marcatori_dati_mancanti("CIV_CIT_001", {"model_code": "CIV_CIT_001"})
    assert marcati
    assert payload["hearing_date"] == marcatore_dato_mancante("Data Udienza")


def test_riferimenti_selezionati_entrano_nella_sezione_diritto(cliente_mario, fascicolo_preliminare):
    preparazione = prepara_payload_generazione(
        model_code="CIV_CIT_001",
        fascicolo=fascicolo_preliminare,
        cliente=cliente_mario,
        utente=_utente(),
        config=CONFIG_STUDIO,
        valori_utente={"hearing_date": "2026-10-15"},
        riferimenti_selezionati=[
            {"ambito": "sostanziale", "riferimento": "art. 1453 c.c.", "rubrica": "Risolubilita' del contratto per inadempimento", "motivo": "Risoluzione per inadempimento."},
            {"ambito": "processuale", "riferimento": "art. 163 c.p.c.", "rubrica": "Contenuto della citazione", "motivo": "Requisiti dell'atto."},
        ],
        conferma_bozza=True,
    )
    assert "art. 1453 c.c." in str(preparazione["payload"].get("legal_arguments"))
    assert "art. 163 c.p.c." in str(preparazione["payload"].get("legal_arguments"))


def test_contesto_payload_completo(repos, cliente_mario, fascicolo_preliminare):
    payload = build_redazione_contesto_payload(
        fascicolo=fascicolo_preliminare,
        cliente=cliente_mario,
        config=CONFIG_STUDIO,
    )
    assert payload["ok"] is True
    assert payload["contesto"]["fascicolo"]["ufficioGiudiziario"]["valore"] == "Tribunale di Palmi"
    assert payload["suggerimenti"][0]["code"] == "CIV_CIT_001"
    assert payload["catalogo"], "Il catalogo manuale deve restare disponibile"


# ---------------------------------------------------------------------------
# End-to-end HTTP: wizard completo dal cliente reale all'editor
# ---------------------------------------------------------------------------


def _app_redazione(tmp_path):
    from tests.test_applicazioni import _cfg_web
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_AVVOCATO"] = "Avv. Giulia Verdi"
    cfg["STUDIO_CF"] = "VRDGLI80A41H501X"
    cfg["STUDIO_INDIRIZZO"] = "Corso Garibaldi 5, Palmi (RC)"
    cfg["PCT_STUDIO_PEC"] = "studio.verdi@pec.example.test"
    cfg["REDAZIONE_NORMATIVA_DB"] = str(tmp_path / "template_atti" / "riferimenti_normativi.json")
    app = create_app(cfg)

    from pct.fascicoli import TipoDocumento

    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"], studio_db=studio_db)
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi", codice_fiscale="RSSMRA70B10G288K")
    clienti.aggiorna(
        cliente.id,
        data_nascita="1970-02-10",
        luogo_nascita="Palmi",
        indirizzo_residenza=Indirizzo(via="Via Roma", civico="10", cap="89015", comune="Palmi", provincia="RC"),
    )
    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
        studio_db=studio_db,
    )
    fascicolo = fascicoli.nuovo(
        titolo="Risoluzione contratto preliminare immobile",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
    )
    fascicoli.aggiorna(
        fascicolo.id,
        oggetto="Inadempimento del preliminare di compravendita: caparra confirmatoria e diffida ad adempiere",
        note="Mediazione esperita con esito negativo.",
        tribunale="Tribunale di Palmi",
        controparte="Bianchi Costruzioni Srl",
        valore_causa=80000.0,
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "contratto_preliminare.pdf",
        TipoDocumento.CONTRATTO,
        b"%PDF-1.4 contenuto del preliminare",
        caricato_da="admin",
    )
    return app, cliente, fascicolo


def test_flusso_completo_http_dal_cliente_all_editor(tmp_path):
    app, cliente, fascicolo = _app_redazione(tmp_path)
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)

        # Passo 1: clienti reali
        clienti_resp = client.get("/api/v1/ui/redazione-atti/clienti").get_json()
        assert clienti_resp["ok"] is True
        assert any(voce["id"] == cliente.id for voce in clienti_resp["clienti"])

        # Passo 2: fascicoli del cliente selezionato
        fasc_resp = client.get(f"/api/v1/ui/redazione-atti/clienti/{cliente.id}/fascicoli").get_json()
        assert fasc_resp["ok"] is True
        assert [voce["id"] for voce in fasc_resp["fascicoli"]] == [fascicolo.id]

        # Passo 3: contesto + suggerimenti dal fascicolo
        contesto_resp = client.get(
            f"/api/v1/ui/redazione-atti/fascicoli/{fascicolo.id}/contesto?id_cliente={cliente.id}"
        ).get_json()
        assert contesto_resp["ok"] is True
        assert contesto_resp["contesto"]["fascicolo"]["ufficioGiudiziario"]["valore"] == "Tribunale di Palmi"
        assert contesto_resp["suggerimenti"][0]["code"] == "CIV_CIT_001"

        # Isolamento: fascicolo richiesto con cliente sbagliato -> rifiutato
        negato = client.get(
            f"/api/v1/ui/redazione-atti/fascicoli/{fascicolo.id}/contesto?id_cliente=CLIENTE_X"
        ).get_json()
        assert negato["ok"] is False

        # Passo 4: anteprima campi trovati/mancanti + normativa
        anteprima = client.get(
            f"/api/v1/ui/redazione-atti/anteprima/CIV_CIT_001?id_fascicolo={fascicolo.id}&id_cliente={cliente.id}"
        ).get_json()
        assert anteprima["ok"] is True
        trovati = {voce["name"]: voce["value"] for voce in anteprima["campiTrovati"]}
        assert trovati["court_name"] == "Tribunale di Palmi"
        assert trovati["plaintiff"] == "Rossi Mario"
        assert any(voce["name"] == "hearing_date" for voce in anteprima["campiMancanti"])
        riferimenti_resi = {voce["riferimento"] for voce in anteprima["normativa"]["processuali"]}
        assert "art. 163 c.p.c." in riferimenti_resi

        # Passi 5-6: generazione senza data udienza -> blocco con richiesta conferma
        bloccata = client.post(
            "/api/v1/ui/redazione-atti/genera",
            json={"modelCode": "CIV_CIT_001", "idFascicolo": fascicolo.id, "idCliente": cliente.id, "valori": {}},
        ).get_json()
        assert bloccata["ok"] is False
        assert bloccata.get("richiedeConfermaBozza") is True

        # Generazione completa con i campi forniti dall'avvocato
        valori = {
            "hearing_date": "2026-10-15",
            "facts": "In data 05/01/2025 le parti sottoscrivevano contratto preliminare di compravendita.",
            "requests_or_conclusions": "Dichiarare la risoluzione del contratto preliminare per inadempimento.",
            "evidence_means": "Interrogatorio formale del legale rappresentante della convenuta.",
        }
        esito = client.post(
            "/api/v1/ui/redazione-atti/genera",
            json={
                "modelCode": "CIV_CIT_001",
                "idFascicolo": fascicolo.id,
                "idCliente": cliente.id,
                "valori": valori,
                "riferimenti": [
                    {"ambito": "sostanziale", "riferimento": "art. 1453 c.c.", "rubrica": "Risolubilita' del contratto per inadempimento", "motivo": "Risoluzione per inadempimento."}
                ],
            },
        ).get_json()
        if not esito.get("ok") and (esito.get("richiedeConfermaAvvisi") or esito.get("richiedeConfermaBozza")):
            esito = client.post(
                "/api/v1/ui/redazione-atti/genera",
                json={
                    "modelCode": "CIV_CIT_001",
                    "idFascicolo": fascicolo.id,
                    "idCliente": cliente.id,
                    "valori": valori,
                    "confermaAvvisi": True,
                    "confermaBozza": True,
                },
            ).get_json()
        assert esito["ok"] is True, esito
        assert esito["documentId"]
        assert esito["editorUrl"].startswith(f"/fascicoli/{fascicolo.id}/documenti/")

        # Il documento e' realmente collegato al fascicolo
        doc_id = esito["documentId"]
        editor_payload = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti/{doc_id}/editor"
        ).get_json()
        assert editor_payload.get("notFound") is not True

        # L'editor carica il documento con i dati reali, senza placeholder tecnici
        html_resp = client.get(f"/api/editor/{fascicolo.id}/{doc_id}/html")
        assert html_resp.status_code == 200
        html = html_resp.get_data(as_text=True)
        assert "Rossi Mario" in html
        assert "Bianchi Costruzioni Srl" in html
        assert "TRIBUNALE DI PALMI" in html.upper()
        assert "{{" not in html


def test_nome_file_contiene_cliente_fascicolo_tipo_e_data(tmp_path):
    app, cliente, fascicolo = _app_redazione(tmp_path)
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        esito = client.post(
            "/api/v1/ui/redazione-atti/genera",
            json={
                "modelCode": "CIV_CIT_001",
                "idFascicolo": fascicolo.id,
                "idCliente": cliente.id,
                "valori": {"hearing_date": "2026-10-15", "facts": "Fatti.", "requests_or_conclusions": "Conclusioni.", "evidence_means": "Prove."},
                "confermaAvvisi": True,
                "confermaBozza": True,
            },
        ).get_json()
        assert esito["ok"] is True, esito
        editor_payload = client.get(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti/{esito['documentId']}/editor"
        ).get_json()
        nome = str(editor_payload.get("document", {}).get("name", ""))
        assert "rossi_mario" in nome
        assert "atto_di_citazione" in nome
        assert nome.endswith(".html")


def test_editor_salva_esporta_e_sezioni_atto(tmp_path):
    """Criteri obbligatori 8-12: salvataggio editor, export DOCX/PDF, sezioni formali, accessi."""
    app, cliente, fascicolo = _app_redazione(tmp_path)
    with app.test_client() as anonimo:
        risposta = anonimo.get("/api/v1/ui/redazione-atti/clienti")
        assert risposta.status_code in {401, 403}, "Senza sessione l'accesso deve essere negato"

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        esito = client.post(
            "/api/v1/ui/redazione-atti/genera",
            json={
                "modelCode": "CIV_CIT_001",
                "idFascicolo": fascicolo.id,
                "idCliente": cliente.id,
                "valori": {
                    "hearing_date": "2026-10-15",
                    "facts": "In data 05/01/2025 le parti sottoscrivevano contratto preliminare.",
                    "requests_or_conclusions": "Dichiarare la risoluzione del contratto preliminare; condannare la convenuta al risarcimento.",
                    "evidence_means": "Interrogatorio formale; prova testimoniale.",
                },
                "riferimenti": [
                    {"ambito": "sostanziale", "riferimento": "art. 1453 c.c.", "rubrica": "Risolubilita' del contratto per inadempimento", "motivo": "Risoluzione per inadempimento."},
                    {"ambito": "sostanziale", "riferimento": "art. 1385 c.c.", "rubrica": "Caparra confirmatoria", "motivo": "Caparra versata."},
                ],
                "confermaAvvisi": True,
                "confermaBozza": True,
            },
        ).get_json()
        assert esito["ok"] is True, esito
        doc_id = esito["documentId"]

        # Sezioni formali dell'atto di citazione (intestazione, parti, fatto, diritto, conclusioni, valore, firma)
        html = client.get(f"/api/editor/{fascicolo.id}/{doc_id}/html").get_data(as_text=True)
        testo = html.upper()
        for sezione in ("TRIBUNALE DI PALMI", "FATTO", "DIRITTO", "CONCLUSIONI", "VALORE", "AVV."):
            assert sezione in testo, f"Sezione mancante nell'atto: {sezione}"
        assert "ART. 1453 C.C." in testo
        assert "ART. 1385 C.C." in testo

        # Salvataggio modifiche dall'editor
        salvato = client.post(
            f"/api/editor/{fascicolo.id}/{doc_id}/salva",
            json={"html": html.replace("FATTO", "FATTO", 1) + "<p>Integrazione manuale dell'avvocato.</p>", "auto": False},
        )
        assert salvato.status_code == 200
        assert salvato.get_json().get("ok") is True
        riletto = client.get(f"/api/editor/{fascicolo.id}/{doc_id}/html").get_data(as_text=True)
        assert "Integrazione manuale dell'avvocato." in riletto

        # Export PDF e DOCX reali (gli endpoint editor ricevono l'HTML corrente)
        pdf = client.post(f"/api/editor/{fascicolo.id}/{doc_id}/pdf", json={"html": riletto})
        assert pdf.status_code == 200
        assert pdf.data[:4] == b"%PDF"
        docx = client.post(f"/api/editor/{fascicolo.id}/{doc_id}/docx", json={"html": riletto})
        assert docx.status_code == 200
        assert docx.data[:2] == b"PK", "Il DOCX deve essere un pacchetto OOXML valido"
