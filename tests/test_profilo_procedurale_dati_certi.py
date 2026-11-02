"""Profilo procedurale dai dati certi del fascicolo, per tutte le materie.

Difetto in produzione (v2.476.0): fascicoli ben identificati (lavoro con sezione
Lavoro e ricorso ex art. 414 c.p.c.; civile al Tribunale di Firenze) restavano
«Profilo procedurale da confermare — profilo non determinabile automaticamente»
con sempre le stesse cinque alternative estranee (ambientale, accesso agli atti,
gara d'appalto, sinistro assicurativo, contestazione bancaria): il resolver non
leggeva ufficio, sezione, registro e atto introduttivo, e il ripiego erano i
primi cinque profili del catalogo in ordine alfabetico.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.practice_engine import PracticeEngineRepository, get_profile
from pct.practice_engine.evaluator import AUTORE_DATI_CERTI, build_regia_payload, ensure_profile_for_fascicolo
from pct.practice_engine.profiles import list_profiles
from pct.practice_engine.resolver import resolve_practice_profile
from pct.practice_engine.riconvalida_profili import riconvalida_profili

ESTRANEE = {"PROC_AMB_SANZ_001", "PROC_ACC_ATTI_001", "PROC_APP_GARA_001", "PROC_ASS_001", "PROC_BANK_001"}
LAVORO_414 = "Ricorso in materia di lavoro (art. 414 c.p.c.)"


def _risolvi(etichette: list[str] | None = None, **campi):
    return resolve_practice_profile(fascicolo=SimpleNamespace(**campi), payload={"etichette_documenti": etichette or []})


@pytest.mark.parametrize(
    ("campi", "etichette", "atteso"),
    [
        # lavoro: tipo, sezione Lavoro e Previdenza, ricorso ex art. 414 c.p.c. (artt. 409, 414 c.p.c.)
        ({"tipo": "LAVORO", "tribunale": "Tribunale di Torino", "sezione": "Lavoro e Previdenza", "numero_rg": "3950", "anno_rg": 2026},
         [LAVORO_414], "PROC_RITO_LAVORO_001"),
        # stesso fascicolo registrato come «Civile»: la sezione lavoro precisa la materia
        ({"tipo": "CIVILE", "tribunale": "Tribunale di Torino", "sezione": "Lavoro e Previdenza"}, [LAVORO_414], "PROC_RITO_LAVORO_001"),
        # civile ordinario: atto di citazione davanti al Tribunale (art. 163 c.p.c.)
        ({"tipo": "CIVILE", "tribunale": "Tribunale di Firenze", "tipo_registro": "SICID"}, ["Atto di citazione"], "PROC_RITO_ORDINARIO_001"),
        # giudice di pace civile (SIGP)
        ({"tipo": "CIVILE", "tribunale": "Ufficio del Giudice di Pace di Firenze"}, [], "PROC_SIGP_GDP_001"),
        ({"tipo": "CIVILE", "tribunale": "Ufficio del Giudice di Pace di Firenze"}, ["Atto di citazione"], "PROC_SIGP_GDP_001"),
        # TAR: processo amministrativo (artt. 40-41 c.p.a.)
        ({"tipo": "AMMINISTRATIVO", "tribunale": "TAR Toscana"}, ["Ricorso al TAR"], "PROC_RITO_TAR_001"),
        # famiglia: rito delle persone, dei minorenni e delle famiglie (art. 473-bis c.p.c.)
        ({"tipo": "FAMIGLIA", "tribunale": "Tribunale di Milano"}, ["Ricorso per separazione o divorzio"], "PROC_RITO_FAMIGLIA_001"),
    ],
)
def test_dati_certi_concordi_impostano_il_rito_senza_conferma(campi, etichette, atteso):
    esito = _risolvi(etichette, **campi)

    assert esito.profile is not None and esito.profile.code == atteso
    assert esito.automatic is True
    assert esito.needs_manual_confirmation is False
    assert esito.reason.startswith("Profilo impostato dai dati certi del fascicolo:")
    assert esito.profile.source  # la norma del rito o il catalogo da cui viene


def test_codice_oggetto_pst_ufficiale_imposta_il_profilo_senza_conferma():
    esito = _risolvi(tipo="LAVORO", tribunale="TRIBUNALE DI TORINO", oggetto="222050 - Retribuzione", codice_oggetto_pst="222050 - Retribuzione")

    assert esito.profile.code == "PROC_LAV_RETRIB_001"
    assert esito.automatic is True and esito.needs_manual_confirmation is False
    assert "codice oggetto PST ufficiale 222050" in esito.reason


def test_codice_oggetto_pst_licenziamento_non_diventa_retribuzione():
    esito = _risolvi(tipo="LAVORO", tribunale="Tribunale di Roma", codice_oggetto_pst="222102")

    assert esito.profile.code == "PROC_LIC_IMP_001"
    assert esito.automatic is True


def test_codice_pst_lavoro_discordante_col_fascicolo_chiede_conferma():
    esito = _risolvi(tipo="AMMINISTRATIVO", tribunale="TAR Lazio", codice_oggetto_pst="222050")

    assert esito.automatic is False and esito.needs_manual_confirmation is True
    assert "contrasta" in esito.reason


def test_civile_senza_atto_introduttivo_propone_solo_riti_civili_del_tribunale():
    esito = _risolvi(tipo="CIVILE", tribunale="Tribunale di Firenze", numero_rg="1234", anno_rg=2025, oggetto="garanzia vizi")

    codici = {alternativa["code"] for alternativa in esito.alternatives}
    assert esito.automatic is False and esito.needs_manual_confirmation is True
    assert {"PROC_RITO_ORDINARIO_001", "PROC_RITO_SEMPLIFICATO_001"} <= codici
    assert not codici & ESTRANEE
    assert all(get_profile(codice).channel == "PCT_CIVILE" for codice in codici)
    assert "Materia civile" in esito.reason


def test_lavoro_senza_sezione_ne_atto_propone_il_rito_del_lavoro_con_alternative_di_lavoro():
    esito = _risolvi(tipo="LAVORO", tribunale="Tribunale di Palmi")

    assert esito.profile.code == "PROC_RITO_LAVORO_001"
    assert esito.needs_manual_confirmation is True
    codici = {alternativa["code"] for alternativa in esito.alternatives}
    assert codici and codici <= {"PROC_LIC_IMP_001", "PROC_LAV_RETRIB_001"}


def test_caso_indeterminabile_nessuna_alternativa():
    esito = _risolvi(tipo="ALTRO")

    assert esito.profile is None
    assert esito.alternatives == []
    assert esito.needs_manual_confirmation is True
    assert "non determinabile" in esito.reason


def test_dati_discordanti_nessun_profilo_automatico():
    esito = _risolvi(tipo="LAVORO", tribunale="TAR Lazio")

    assert esito.profile is None and esito.automatic is False
    assert "discordanti" in esito.reason


def test_nessuna_combinazione_propone_le_alternative_fisse_di_prima():
    for campi in (
        {"tipo": "LAVORO", "tribunale": "Tribunale di Torino"},
        {"tipo": "CIVILE", "tribunale": "Tribunale di Firenze"},
        {"tipo": "FAMIGLIA", "tribunale": "Tribunale di Milano"},
        {"tipo": "PENALE", "tribunale": "Tribunale di Roma"},
    ):
        codici = {alternativa["code"] for alternativa in _risolvi(**campi).alternatives}
        assert not codici & ESTRANEE, campi


def test_profili_di_rito_hanno_canale_e_fonte_normativa():
    riti = [profilo for profilo in list_profiles() if profilo.code.startswith("PROC_RITO_")]
    assert {p.code for p in riti} == {
        "PROC_RITO_LAVORO_001", "PROC_RITO_ORDINARIO_001", "PROC_RITO_SEMPLIFICATO_001", "PROC_RITO_FAMIGLIA_001", "PROC_RITO_TAR_001",
    }
    for profilo in riti:
        assert profilo.depositable and profilo.required_slots
        assert "c.p.c." in profilo.source or "c.p.a." in profilo.source


def _fascicolo_lavoro(tmp_path, **extra):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo(
        titolo="Rossi c. Alfa S.p.A.", tipo=TipoFascicolo.LAVORO, id_cliente="cliente-1", nome_cliente="Mario Rossi",
        oggetto="Differenze di inquadramento", tribunale="Tribunale di Torino", avvocato="Avv. Regia",
        codice_fiscale_cliente="RSSMRA80A01H501U", **extra,
    )
    gf.aggiorna(fascicolo.id, sezione="Lavoro e Previdenza", numero_rg="3950", anno_rg=2026)
    repo = PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))
    return gf, repo, gf.get(fascicolo.id)


def test_regia_imposta_il_profilo_certo_con_audit_e_fonte(tmp_path):
    gf, repo, fascicolo = _fascicolo_lavoro(tmp_path)

    payload = build_regia_payload(repo, fascicolo=fascicolo, fascicoli_manager=gf, etichette_documenti=[LAVORO_414])

    assert payload["page_state"] == "operativa"
    assert payload["header"]["channel"] == "PCT lavoro / SICID"
    assert payload["profile"]["code"] == "PROC_RITO_LAVORO_001"
    assert payload["profile"]["automatic"] is True
    assert "sezione Lavoro e Previdenza" in payload["profile"]["reason"]
    snapshot = repo.get_profile_snapshot(fascicolo.id)
    assert snapshot["applied_by"] == AUTORE_DATI_CERTI
    assert any(evento.event_type == "PROFILE_APPLIED" for evento in repo.list_audit(fascicolo.id))

    # Seconda apertura: nessuna nuova applicazione, stesso profilo con la stessa fonte.
    eventi = len(repo.list_audit(fascicolo.id))
    di_nuovo = build_regia_payload(repo, fascicolo=fascicolo, fascicoli_manager=gf)
    assert di_nuovo["profile"]["reason"] == payload["profile"]["reason"]
    assert len([e for e in repo.list_audit(fascicolo.id) if e.event_type == "PROFILE_APPLIED"]) == 1
    assert len(repo.list_audit(fascicolo.id)) >= eventi


def test_profilo_confermato_dall_avvocato_non_viene_sostituito(tmp_path):
    gf, repo, fascicolo = _fascicolo_lavoro(tmp_path)
    repo.apply_profile(fascicolo.id, get_profile("PROC_LIC_IMP_001"), actor="Avv. Regia", reason="Conferma esplicita.")

    profilo, esito = ensure_profile_for_fascicolo(repo, fascicolo=fascicolo, etichette_documenti=[LAVORO_414])

    assert profilo.code == "PROC_LIC_IMP_001"
    assert esito["automatic"] is False
    assert repo.get_profile_snapshot(fascicolo.id)["applied_by"] == "Avv. Regia"


def test_deduzione_non_certa_resta_proposta_senza_salvare(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo(titolo="Bianchi c. Verdi", tipo=TipoFascicolo.CIVILE, tribunale="Tribunale di Firenze")
    repo = PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))

    payload = build_regia_payload(repo, fascicolo=fascicolo, fascicoli_manager=gf)

    assert payload["page_state"] == "profilo_da_confermare"
    assert repo.get_profile_snapshot(fascicolo.id) is None
    assert not {a["code"] for a in payload["profile"]["alternatives"]} & ESTRANEE


def test_atto_di_citazione_classificato_nel_fascicolo_fissa_il_rito_ordinario(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo(titolo="Bianchi c. Verdi", tipo=TipoFascicolo.CIVILE, tribunale="Tribunale di Firenze")
    gf.aggiungi_documento(fascicolo.id, "citazione.pdf", TipoDocumento.CITAZIONE, b"%PDF-1.4\n%%EOF")
    repo = PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))

    profilo, esito = ensure_profile_for_fascicolo(repo, fascicolo=gf.get(fascicolo.id))

    assert profilo.code == "PROC_RITO_ORDINARIO_001"
    assert esito["automatic"] is True


def test_riconvalida_imposta_i_profili_certi_ed_e_idempotente(tmp_path):
    gf, repo, fascicolo = _fascicolo_lavoro(tmp_path)
    incerto = gf.nuovo(titolo="Neri c. Gialli", tipo=TipoFascicolo.CIVILE, tribunale="Tribunale di Firenze")
    confermato = gf.nuovo(titolo="Blu c. Rosa", tipo=TipoFascicolo.LAVORO, tribunale="Tribunale di Torino")
    repo.apply_profile(confermato.id, get_profile("PROC_LIC_IMP_001"), actor="Avv. Regia", reason="Conferma esplicita.")
    fascicoli = [gf.get(fascicolo.id), gf.get(incerto.id), gf.get(confermato.id)]
    etichette = {fascicolo.id: [LAVORO_414]}

    primo = riconvalida_profili(repo, fascicoli, etichette_di=lambda fid: etichette.get(fid, []))
    secondo = riconvalida_profili(repo, fascicoli, etichette_di=lambda fid: etichette.get(fid, []))

    assert primo["impostati"] == 1 and primo["fascicoli_impostati"] == [fascicolo.id]
    assert primo["da_confermare"] == 1 and primo["gia_salvati"] == 1
    assert secondo["impostati"] == 0 and secondo["gia_salvati"] == 2 and secondo["da_confermare"] == 1
    assert repo.get_profile_snapshot(confermato.id)["code"] == "PROC_LIC_IMP_001"
    assert repo.get_profile_snapshot(incerto.id) is None


def test_riconvalida_a_lotti_lascia_il_resto_al_giro_successivo(tmp_path):
    gf, repo, _ = _fascicolo_lavoro(tmp_path)
    altri = [gf.nuovo(titolo=f"Causa {n}", tipo=TipoFascicolo.CIVILE, tribunale="Tribunale di Firenze") for n in range(3)]
    fascicoli = gf.tutti()

    esito = riconvalida_profili(repo, fascicoli, limite=2)

    assert esito["esaminati"] == 2 and esito["restano"] == len(altri) + 1 - 2


def test_job_notturno_registrato_in_corsia_lunga_con_template():
    from pct.scheduler_corsie import CORSIA_LUNGA, corsia_del_lavoro
    from pct.scheduler_registry import default_scheduler_templates

    assert corsia_del_lavoro("profili_procedurali_riconvalida") == CORSIA_LUNGA
    assert corsia_del_lavoro("manual_profili_procedurali_riconvalida_42") == CORSIA_LUNGA
    template = next(t for t in default_scheduler_templates({}) if t.key == "profili_procedurali_riconvalida")
    assert template.trigger_kind == "cron" and template.hour == "2"


def test_runtime_notturno_studio_singolo_imposta_profilo(tmp_path, monkeypatch):
    from flask import Flask

    from web.services import profilo_procedurale_runtime as runtime

    gf, repo, fascicolo = _fascicolo_lavoro(tmp_path)
    gf.aggiorna(fascicolo.id, codice_oggetto_pst="222050")
    app = Flask(__name__)
    app.extensions["core_runtime"] = {"get_fascicoli": lambda: gf, "get_practice_engine": lambda: repo}
    monkeypatch.setattr("web.services.react_practice_engine_bridge._etichette_catalogo", lambda _fid: [])
    monkeypatch.setattr("web.services.lettura_cache.invalida_lettura", lambda _fid: None)

    primo = runtime.riconvalida_profili_notturna(app)
    secondo = runtime.riconvalida_profili_notturna(app)

    assert primo["ok"] is True and primo["totals"]["impostati"] == 1
    assert secondo["totals"]["impostati"] == 0 and secondo["totals"]["gia_salvati"] == 1
    assert repo.get_profile_snapshot(fascicolo.id)["code"] == "PROC_LAV_RETRIB_001"


def test_vista_operativa_espone_fonte_e_alternative_per_cambiare(tmp_path):
    gf, repo, fascicolo = _fascicolo_lavoro(tmp_path)

    payload = build_regia_payload(repo, fascicolo=fascicolo, fascicoli_manager=gf, etichette_documenti=[LAVORO_414])

    assert payload["profile"]["sourceLabel"].startswith("Impostato dai dati certi del fascicolo:")
    assert "art. 414 c.p.c." in payload["profile"]["sourceLabel"]
    codici = {riga["code"] for riga in payload["profile"]["changeOptions"]}
    assert codici and "PROC_RITO_LAVORO_001" not in codici
    assert codici <= {"PROC_LIC_IMP_001", "PROC_LAV_RETRIB_001"}
    assert payload["actions"]["applyProfile"].endswith("/regia/applica-profilo")

    repo.apply_profile(fascicolo.id, get_profile("PROC_LIC_IMP_001"), actor="Avv. Regia", reason="Cambio esplicito.")
    cambiato = build_regia_payload(repo, fascicolo=fascicolo, fascicoli_manager=gf)
    assert cambiato["profile"]["code"] == "PROC_LIC_IMP_001"
    assert cambiato["profile"]["sourceLabel"].startswith("Confermato da Avv. Regia il ")
