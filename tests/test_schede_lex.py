from pct.schede_lex import blocco_scadenze, controlla_risposta, ripara_risposta

RISOLTA = {"campi": [
    {"campo": "costituzione", "etichetta": "Ultimo giorno per costituirsi", "stato": "calcolato", "valore": "29/01/2027",
     "spiegazione": "70 giorni prima dell'udienza del 09/04/2027", "scaduto": False},
    {"campo": "difensore", "etichetta": "Difensore", "stato": "compilato", "valore": "Avv. Rossi"}]}
MESSAGGIO = "Udienza del 09/04/2027 indicata in citazione; atto del 19/10/2026"


def test_blocco_contiene_la_data_calcolata():
    blocco = blocco_scadenze(RISOLTA)
    assert "29/01/2027" in blocco and "non ricalcolarle" in blocco
    assert blocco_scadenze({"campi": []}) == ""


def test_data_ricalcolata_dal_modello_viene_segnalata_e_corretta():
    # errore tipico del pilota: un giorno di scarto
    risposta = "Il convenuto deve costituirsi entro il 28/01/2027, 70 giorni prima dell'udienza del 09/04/2027."
    esito = controlla_risposta(risposta, RISOLTA, MESSAGGIO)
    assert esito == {"mancanti": ["29/01/2027"], "estranee": ["28/01/2027"], "ok": False}
    riparata = ripara_risposta(risposta, RISOLTA, MESSAGGIO)
    assert "29/01/2027" in riparata and "28/01/2027" in riparata.split("prevalgono")[1]


def test_risposta_corretta_resta_invariata():
    risposta = "Costituzione entro il 29/01/2027 (udienza del 9/4/2027)."
    assert controlla_risposta(risposta, RISOLTA, MESSAGGIO)["ok"]
    assert ripara_risposta(risposta, RISOLTA, MESSAGGIO) == risposta


def test_data_calcolata_da_fonte_non_confermata_non_diventa_certa_per_lex():
    from datetime import date

    from pct.registro_letture.fatti_repository import Fatto
    from pct.schede_compilazione import risolvi_scheda, scheda_per_template

    scheda = scheda_per_template("CIV_ORD_009")
    fatti = [Fatto(categoria="data", campo="udienza", valore="2027-04-18", etichetta="Udienza")]
    risolta = risolvi_scheda(scheda, {}, fatti=fatti, oggi=date(2026, 10, 21))
    blocco = blocco_scadenze(risolta)
    assert "05/02/2027" in blocco
    assert "non presentarlo come confermato" in blocco


def test_primo_giorno_utile_trascorso_non_viene_presentato_come_decadenza():
    risolta = {"campi": [{"campo": "decorrenza", "etichetta": "Primo giorno utile per procedere",
                           "stato": "calcolato", "valore": "01/10/2026", "scaduto": True}]}
    assert "01/10/2026" in blocco_scadenze(risolta)
    assert "scaduto" not in blocco_scadenze(risolta)


def test_runtime_date_discordanti_non_produce_scadenza_certa(monkeypatch):
    from types import SimpleNamespace

    from pct.registro_letture.fatti_repository import Fatto
    from pct.template_atti_lex_deadlines import completa_scadenze
    from web.services import archivio_letture_runtime

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", lambda f: [
        Fatto(categoria="data", campo="udienza", valore=d, verifica="verificata")
        for d in ("2027-04-09", "2027-04-18")
    ])
    answer, result = completa_scadenze("Risposta", "CIV_COM_001", {}, SimpleNamespace(id="caso"))
    assert result["stato"] == "dati_insufficienti" and result["scadenze"] == []
    assert "manca una data di partenza univoca" in answer


def test_data_nel_titolo_sql_non_viene_segnalata_come_inventata(monkeypatch):
    from types import SimpleNamespace

    from pct.registro_letture.fatti_repository import Fatto
    from pct.template_atti_lex_deadlines import completa_scadenze
    from web.services import archivio_letture_runtime

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", lambda f: [
        Fatto(categoria="data", campo="udienza", valore="2027-04-09", verifica="verificata")])
    answer, _ = completa_scadenze("Fascicolo: COLLAUDO 13/07/2026", "CIV_COM_001", {},
                                 SimpleNamespace(id="caso", titolo="COLLAUDO 13/07/2026"))
    assert "29/01/2027" in answer
    assert "Date da verificare perché" not in answer


def test_runtime_errore_archivio_resta_esplicito(monkeypatch):
    from types import SimpleNamespace

    from pct.template_atti_lex_deadlines import completa_scadenze
    from web.services import archivio_letture_runtime

    def unavailable(fascicolo):
        raise RuntimeError("archivio non disponibile")

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", unavailable)
    answer, result = completa_scadenze("Risposta", "CIV_COM_001", {}, SimpleNamespace(id="caso"))
    assert result["stato"] == "non_disponibile"
    assert "Non è stato possibile verificare" in answer


def test_comparsa_richiesta_come_modello_usa_il_percorso_deterministico():
    from lex.http_bounded_bridge import _is_template_act_request, _resolve_workflow_hint

    context = {"effective_question": "Usa il modello CIV_COM_001 per la comparsa di costituzione",
               "focus_topic": "fascicoli"}
    assert _resolve_workflow_hint(context, {"intent": "bozza_atto"}) == "atto_da_template"
    context["effective_question"] = "Qual è il termine per la comparsa di costituzione?"
    assert not _is_template_act_request(context["effective_question"], context, {"intent": "normativa"})


def test_ingresso_template_non_costruisce_contesti_estranei(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kw: calls.append(kw) or {"answer": "ok"})
    common = {"user": object(), "studio": object(), "data": {}, "attachments": []}
    assert template_http_payload(**common, question="Usa template CIV_COM_001: comparsa di costituzione") == {"answer": "ok"}
    assert calls[0]["studio_context"]["focus_topic"] == "template_act"
    assert template_http_payload(**common, question="Qual è il termine della comparsa di costituzione?") is None
    assert template_http_payload(**common, question="Mostra le udienze di oggi") is None
    assert len(calls) == 1


def test_contesto_template_non_legge_agenda_documenti_o_contabilita(monkeypatch):
    from lex.context import builder
    from lex.contracts import LexRequest
    from lex.retrieval.source_router import SourceRouter

    def forbidden(*args, **kwargs):
        raise AssertionError("Contesto estraneo alla compilazione")

    for name in ("load_agenda_context", "load_scadenze_context", "load_document_context",
                 "load_economic_context", "load_fascicolo_lettura_context", "build_studio_context"):
        monkeypatch.setattr(builder, name, forbidden)
    request = LexRequest(tenant_id="studio", user_id="avvocato", session_id="sessione",
                         query="Usa template CIV_COM_001", fascicolo_id="caso", workflow_hint="atto_da_template")
    context = builder.LexContextBuilder().build_request_context(request, "atto_da_template")
    assert context["permessi"]["can_use_lex"]
    assert {type(s).__name__ for s in SourceRouter().resolve(request, context, "atto_da_template")} == {
        "TemplateAttiSource", "ComplianceSource"}
