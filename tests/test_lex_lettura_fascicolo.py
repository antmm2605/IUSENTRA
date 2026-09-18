"""Lex risponde sul fascicolo con la lettura costruita dai dati.

Il provider deterministico usa la lettura quando il contesto la contiene; la
scelta delle sezioni segue la domanda; il costruttore del contesto registra la
sezione «lettura_fascicolo»; l'endpoint React la espone in JSON.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from lex.context.builder import LexContextBuilder
from lex.contracts import LexRequest
from lex.formatting import lettura_fascicolo as formato
from lex.providers.deterministic_provider import DeterministicProvider
from pct.fascicoli import EsitoAttivita, TipoAttivita, TipoFascicolo
from pct.fascicolo_lettura import DatiLettura, costruisci_lettura
from pct.fascicolo_lettura.narrativa import ORDINE_SEZIONI
from tests.test_react_shell import _app

HEADERS = {"X-API-Key": "react-test-key"}


def _lettura_di_prova() -> dict:
    dati = DatiLettura(
        fascicolo={"id": "F1", "numero": "2026/7", "titolo": "Verdi / Gamma S.p.A.", "cliente": "Luca Verdi", "controparte": "Gamma S.p.A.", "tribunale": "Tribunale di Roma", "numero_rg": "555", "anno_rg": "2026", "stato": "IN_CORSO", "oggetto": "Risarcimento danni da sinistro stradale"},
        depositi=[{"id": "D1", "timestamp": "2026-03-01T09:00:00", "stato": "ACCETTATO_CANCELLERIA", "tipo_atto": "CITAZIONE", "nome_atto_principale": "Atto di citazione", "ricevuta_accettazione": "x", "ricevuta_consegna": "y", "ricevuta_cancelleria": "z"}],
        notifiche=[{"id": "N1", "status": "SENT_WAITING_RAC", "status_label": "Inviata, in attesa della ricevuta di accettazione", "recipients": [{"name": "Gamma S.p.A."}], "document": {"name": "Atto di citazione"}, "source_effective_at": "2026-02-20"}],
        oggi=date(2026, 9, 14),
    )
    return costruisci_lettura(dati)


def test_sezioni_per_domanda_segue_il_fuoco_della_domanda():
    assert formato.sezioni_per_domanda("riassumi il fascicolo") == ORDINE_SEZIONI
    assert formato.sezioni_per_domanda("") == ORDINE_SEZIONI
    assert formato.sezioni_per_domanda("a che punto siamo con le notifiche?") == ("quadro", "depositi_notifiche", "prossimi_passi", "verifiche", "lacune", "fase", "cronologia")
    assert formato.sezioni_per_domanda("quali verifiche automatiche risultano?") == ("quadro", "verifiche", "prossimi_passi", "lacune")
    assert formato.sezioni_per_domanda("cosa devo fare adesso") == ("quadro", "fase", "prossimi_passi", "lacune")
    assert formato.sezioni_per_domanda("di cosa tratta la causa") == ("quadro", "oggetto", "documenti", "fase")
    assert formato.sezioni_per_domanda("ciao") == ORDINE_SEZIONI


def test_provider_deterministico_risponde_con_la_lettura_del_fascicolo():
    lettura = _lettura_di_prova()
    contesto = {"structured_context": {"lettura_fascicolo": lettura, "fascicolo": {"id": "F1"}}}
    provider = DeterministicProvider()

    completa = provider.generate(SimpleNamespace(query="riassumi il fascicolo"), contesto, [], "fascicolo")
    testo = str(getattr(completa, "text", None) or getattr(completa, "content", None) or completa)
    assert "Quadro della pratica" in testo
    assert "RG 555/2026" in testo
    assert "accettato dalla cancelleria" in testo
    assert "Prossimi passaggi" in testo
    assert "Nessuna evidenza" not in testo

    mirata = provider.generate(SimpleNamespace(query="a che punto siamo con le notifiche"), contesto, [], "fascicolo")
    testo_mirato = str(getattr(mirata, "text", None) or getattr(mirata, "content", None) or mirata)
    assert "Depositi e notifiche" in testo_mirato
    assert "Gamma S.p.A." in testo_mirato
    assert "Di che cosa tratta" not in testo_mirato


def test_testo_lettura_vuoto_senza_intestazione():
    assert formato.testo_lettura_per_domanda("riassumi", {}) == ""
    assert formato.testo_lettura_per_domanda("riassumi", {"narrativa": "x"}) == ""


def test_provider_senza_lettura_non_si_rompe():
    provider = DeterministicProvider()
    risposta = provider.generate(SimpleNamespace(query="riassumi il fascicolo"), {"structured_context": {"fascicolo": {}}}, [], "fascicolo")
    assert str(getattr(risposta, "text", None) or getattr(risposta, "content", None) or risposta)


def _seed(app):
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo(
            "Bianchi / Delta S.r.l.",
            TipoFascicolo.CIVILE,
            nome_cliente="Anna Bianchi",
            tribunale="Tribunale di Torino",
            numero_rg="777",
            anno_rg=2026,
            oggetto="Opposizione a decreto ingiuntivo",
        )
        fascicoli.aggiungi_attivita(fascicolo.id, TipoAttivita.UDIENZA, "2026-05-10", "Prima udienza", esito=EsitoAttivita.RINVIATO)
        return fascicolo.id


def test_builder_registra_la_lettura_del_fascicolo(tmp_path):
    app = _app(tmp_path)
    fascicolo_id = _seed(app)
    builder = LexContextBuilder()
    request = LexRequest(tenant_id="tenant-test", user_id="admin", session_id="s", query="riassumi il fascicolo", fascicolo_id=fascicolo_id)
    with app.app_context():
        context = builder.build_request_context(request, "fascicolo")
    lettura = context["lettura_fascicolo"]
    assert lettura["intestazione"]["rg"] == "777/2026"
    assert lettura["intestazione"]["ufficio"] == "Tribunale di Torino"
    assert lettura["fase"]["codice"] == "trattazione"
    assert "Opposizione a decreto ingiuntivo" in lettura["narrativa"]
    assert any(evento["categoria"] == "udienza" for evento in lettura["cronologia"])


def test_endpoint_lettura_restituisce_la_lettura_del_fascicolo(tmp_path):
    app = _app(tmp_path)
    fascicolo_id = _seed(app)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/lettura", headers=HEADERS)
        assert risposta.status_code == 200
        payload = risposta.get_json()
        assert payload["ok"] is True
        assert payload["lettura"]["intestazione"]["rg"] == "777/2026"
        assert payload["lettura"]["generata_il"].count("/") == 2
        assert "Quadro della pratica" in payload["lettura"]["narrativa"]

        assente = client.get("/api/v1/ui/fascicoli/NONESISTE/lettura", headers=HEADERS)
        assert assente.status_code == 404
        assert assente.get_json()["notFound"] is True


def test_endpoint_lettura_non_propaga_errori(tmp_path, monkeypatch):
    import lex.context.fascicolo_lettura_context as modulo

    def esplode(**_kwargs):
        raise RuntimeError("guasto")

    monkeypatch.setattr(modulo, "load_fascicolo_lettura_context", esplode)
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/fascicoli/F1/lettura", headers=HEADERS)
        assert risposta.status_code == 200
        assert risposta.get_json() == {"ok": False, "errore": "Lettura del fascicolo non completata."}


def test_endpoint_lettura_usa_la_cache_breve_e_la_salta_con_aggiorna(tmp_path, monkeypatch):
    import lex.context.fascicolo_lettura_context as modulo
    from web.blueprints import api_v1_react

    chiamate = {"n": 0}

    def finta_lettura(**_kwargs):
        chiamate["n"] += 1
        return {"intestazione": {"rg": "1/2026"}, "narrativa": "Quadro della pratica", "generata_il": "14/09/2026", "prossimi_passi": [], "stato_passi": {"attivi": True, "motivo": ""}}

    monkeypatch.setattr(modulo, "load_fascicolo_lettura_context", finta_lettura)
    api_v1_react._LETTURA_CACHE.clear()
    app = _app(tmp_path)
    with app.test_client() as client:
        prima = client.get("/api/v1/ui/fascicoli/FX/lettura", headers=HEADERS)
        seconda = client.get("/api/v1/ui/fascicoli/FX/lettura", headers=HEADERS)
        terza = client.get("/api/v1/ui/fascicoli/FX/lettura?aggiorna=1", headers=HEADERS)
        altra = client.get("/api/v1/ui/fascicoli/FY/lettura", headers=HEADERS)
    assert prima.status_code == seconda.status_code == terza.status_code == altra.status_code == 200
    assert prima.get_json()["lettura"]["intestazione"]["rg"] == "1/2026"
    assert seconda.get_data() == prima.get_data()
    assert chiamate["n"] == 3  # prima, aggiorna=1, altro fascicolo
    api_v1_react._LETTURA_CACHE.clear()


def test_endpoint_lettura_cache_key_isola_versione_applicativa(tmp_path):
    from web.blueprints import api_v1_react

    app = _app(tmp_path)
    with app.test_request_context("/"):
        chiave = api_v1_react._lettura_cache_key("FX")

    assert chiave[0] == "lettura"
    # La versione applicativa e' un segmento della chiave: una release nuova non
    # serve mai all'avvocato il payload costruito da quella precedente. Accanto
    # sta la revisione SQL della lettura, cosi' il completamento del worker OCR
    # invalida la cache anche fra container diversi. Si verifica la proprieta',
    # non la posizione: la chiave puo' crescere di segmenti senza perderla.
    segmenti = chiave[1].split("@")
    assert segmenti[0] == "default"
    assert segmenti[1] == api_v1_react.APP_VERSION
    assert chiave[2] == "FX"


def test_context_archivio_completo_non_ricostruisce_catalogo_pesante(monkeypatch):
    """Con l'archivio gia' letto, la lettura del fascicolo non riapre il catalogo pesante.

    Il documento risulta letto perche' lo dice l'archivio — «letto» nelle
    letture dei motori — non perche' lo dica un indice ricostruito nella
    richiesta. Il catalogo si deriva da li'.
    """
    import lex.context.fascicolo_lettura_context as modulo

    fascicolo = SimpleNamespace(
        id="F1",
        numero="2026/1",
        titolo="Rossi / Bianchi",
        documenti=[SimpleNamespace(id="D1", nome="Atto introduttivo.pdf", tipo="ATTO", data_caricamento="2026-09-10")],
        attivita=[],
        depositi_pct=[],
    )

    def vietato(*_args, **_kwargs):
        raise AssertionError("il percorso con archivio completo non deve richiamare il catalogo documentale pesante")

    monkeypatch.setattr(modulo, "get_fascicoli", lambda: SimpleNamespace(get=lambda _id: fascicolo))
    monkeypatch.setattr(modulo, "_archivio", lambda _fascicolo: {
        "stato": {"completa": True, "da_leggere": 0},
        "riassunto": {"totale": 1, "per_motore": {"documenti": 1}},
        "letture_documenti": {"D1": {"stato": "letto", "presente": True}},
        "domande": [],
    })
    monkeypatch.setattr(modulo, "_catalogo", vietato)
    monkeypatch.setattr(modulo, "_documenti_non_scaricati", vietato)
    monkeypatch.setattr(modulo, "_verifiche", lambda _fascicolo: {})
    monkeypatch.setattr(modulo, "_regia", lambda _id: {})
    monkeypatch.setattr(modulo, "_economico", lambda _id: {})
    monkeypatch.setattr(modulo, "_parti", lambda _id: [])
    monkeypatch.setattr(modulo, "_presidi_notifiche", lambda _id: [])
    monkeypatch.setattr(modulo, "messaggi_pec_per_fascicolo", lambda _fascicolo: [])
    monkeypatch.setattr("web.services.react_fascicoli_bridge._sql_document_catalog_by_id", lambda _fascicolo: {})
    monkeypatch.setattr("web.services.correlazioni_ricevute_archivio.depositi_da_archivio", lambda _fascicolo: [])

    dati = modulo.raccogli_dati_lettura("F1")

    assert dati is not None
    assert dati.documenti[0]["id"] == "D1"
    assert dati.documenti[0]["lex_read"] is True
    assert dati.catalogo[0]["document_id"] == "D1"
    assert dati.catalogo[0]["indexed"] is True
