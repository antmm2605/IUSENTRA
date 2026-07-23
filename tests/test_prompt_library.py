"""Test funzionali della libreria prompt "LegalSkills Italia".

Verificano il contratto del catalogo (1.303 prompt in 26 aree), la
composizione nelle varie forme, la ricerca su tutto il contenuto e le
API governate (auth, feature flag, parametri riservati).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lex.legal_skills.exceptions import LegalSkillsError
from lex.legal_skills.prompt_library import (
    FORME,
    PROMPT_PACK_ID,
    ContestoFascicolo,
    LegalPromptLibrary,
    aree_preferite_da_profilo,
    get_prompt_library,
    prepara_esecuzione_prompt,
)
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app

TOTALE_PROMPT = 1303
TOTALE_AREE = 26


@pytest.fixture(scope="module")
def library() -> LegalPromptLibrary:
    return get_prompt_library()


def test_catalogo_completo_26_aree_1303_prompt(library: LegalPromptLibrary):
    aree = library.aree()
    assert len(aree) == TOTALE_AREE
    assert library.totale_prompt() == TOTALE_PROMPT
    for area in aree:
        assert area.nome and area.descrizione
        assert area.voci, f"Area senza voci: {area.area_id}"


def test_ogni_voce_dichiara_riferimenti_normativi(library: LegalPromptLibrary):
    for area in library.aree():
        for voce in area.voci:
            assert voce.riferimenti, f"Voce senza base normativa: {area.area_id}/{voce.voce_id}"
            assert voce.forme, f"Voce senza forme: {area.area_id}/{voce.voce_id}"
            assert set(voce.forme) <= set(FORME), f"Forme sconosciute: {area.area_id}/{voce.voce_id}"


def test_ricerca_vuota_trova_tutto_con_id_univoci(library: LegalPromptLibrary):
    tutti = library.search()
    assert len(tutti) == TOTALE_PROMPT
    ids = [prompt["prompt_id"] for prompt in tutti]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("forma", sorted(FORME))
def test_composizione_funziona_per_ogni_forma(library: LegalPromptLibrary, forma: str):
    risultati = library.search(forma=forma)
    assert risultati, f"Nessun prompt per la forma {forma}"
    for entry in (risultati[0], risultati[-1]):
        dettaglio = library.get_prompt(entry["prompt_id"])
        assert dettaglio["forma"] == forma
        assert dettaglio["forma_label"] == FORME[forma]["label"]
        assert "revisione obbligatoria" in dettaglio["testo"]
        assert "ordinamento italiano" in dettaglio["testo"]
        for riferimento in dettaglio["riferimenti"]:
            assert riferimento in dettaglio["testo"]


def test_ricerca_per_area_forma_testo_e_riferimento(library: LegalPromptLibrary):
    per_area = library.search(area="penale")
    assert per_area and all(prompt["area_id"] == "penale" for prompt in per_area)

    per_forma = library.search(forma="parere")
    assert per_forma and all(prompt["forma"] == "parere" for prompt in per_forma)

    per_testo = library.search(query="licenziamento")
    assert per_testo and all("lavoro" == prompt["area_id"] for prompt in per_testo)

    per_norma = library.search(query="1454")
    assert per_norma, "La ricerca deve trovare anche per riferimento normativo"

    combinata = library.search(query="licenziamento", forma="checklist")
    assert combinata and all(prompt["forma"] == "checklist" for prompt in combinata)

    assert library.search(query="zzz-introvabile-zzz") == []
    assert len(library.search(limit=5)) == 5


def test_composizione_precompilata_dal_contesto_fascicolo(library: LegalPromptLibrary):
    entry = library.search(area="civile", forma="redazione_atto")[0]
    contesto = ContestoFascicolo(
        fascicolo_id="F1",
        numero="2026/001",
        titolo="Rossi contro Bianchi",
        cliente="Mario Rossi",
        controparte="Bianchi Srl",
        ufficio="Tribunale di Milano",
        numero_rg="1428",
        anno_rg="2026",
        oggetto="Inadempimento del contratto di fornitura",
        documenti=["Contratto di fornitura.pdf", "Diffida 12-05-2026.pdf"],
        scadenze=["10/09/2026 — Udienza di prima comparizione"],
    )

    dettaglio = library.get_prompt(entry["prompt_id"], contesto=contesto)
    testo = dettaglio["testo"]

    assert "assistito Mario Rossi contro Bianchi Srl" in testo
    assert "Tribunale di Milano" in testo
    assert "RG 1428/2026" in testo
    assert "Contesto del fascicolo" in testo
    assert "Contratto di fornitura.pdf" in testo
    assert "10/09/2026 — Udienza di prima comparizione" in testo
    assert "senza inventarlo" in testo
    assert "[PARTI]" not in testo
    assert "[AUTORITÀ O UFFICIO COMPETENTE]" not in testo
    assert dettaglio["contesto_fascicolo"]["rg"] == "RG 1428/2026"


def test_contesto_parziale_conserva_i_segnaposto_mancanti(library: LegalPromptLibrary):
    entry = library.search(area="civile", forma="lettera")[0]
    contesto = ContestoFascicolo(fascicolo_id="F2", cliente="Mario Rossi")

    testo = library.get_prompt(entry["prompt_id"], contesto=contesto)["testo"]

    # Nessuna controparte nota: il destinatario resta da chiedere all'avvocato.
    assert "[DESTINATARIO]" in testo
    assert "[FATTI]" in testo
    assert "assistito Mario Rossi" in testo


def test_aree_preferite_da_profilo_studio(library: LegalPromptLibrary):
    disponibili = {area.area_id for area in library.aree()}

    preferite = aree_preferite_da_profilo(
        ["Diritto del Lavoro", "Privacy e GDPR", "recupero crediti", "astrofisica"], disponibili
    )

    assert preferite == ["lavoro", "privacy", "recupero_crediti"]
    assert aree_preferite_da_profilo([], disponibili) == []


def test_prompt_inesistente_solleva_errore_404(library: LegalPromptLibrary):
    with pytest.raises(LegalSkillsError) as errore:
        library.get_prompt("civile.voce_inesistente.parere")
    assert errore.value.status_code == 404
    with pytest.raises(LegalSkillsError):
        library.get_prompt("id-malformato")


def test_catalogo_mancante_fail_closed(tmp_path: Path):
    with pytest.raises(LegalSkillsError) as errore:
        LegalPromptLibrary(catalog_dir=tmp_path / "vuoto").aree()
    assert errore.value.code == "prompt_catalog_missing"


def _app(tmp_path: Path, flags: dict | None = None):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    if flags is not None:
        cfg["FEATURE_FLAGS"] = flags
    app = create_app(cfg)
    app.config["API_KEY"] = "prompt-library-test-key"
    return app


def test_api_prompt_library_auth_guardie_e_ricerca(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "prompt-library-test-key"}

    with app.test_client() as client:
        anonimo = client.get("/api/v1/legal-skills/prompt-library/aree")
        assert anonimo.status_code == 401

        bloccato = client.get("/api/v1/legal-skills/prompt-library/prompts?tenant_id=leak", headers=headers)
        assert bloccato.status_code == 400
        assert bloccato.get_json()["code"] == "backend_security_control_param"

        aree = client.get("/api/v1/legal-skills/prompt-library/aree", headers=headers)
        assert aree.status_code == 200
        payload = aree.get_json()
        assert payload["totale_prompt"] == TOTALE_PROMPT
        assert len(payload["aree"]) == TOTALE_AREE
        assert {forma["forma_id"] for forma in payload["forme"]} == set(FORME)

        tutti = client.get("/api/v1/legal-skills/prompt-library/prompts", headers=headers)
        assert tutti.status_code == 200
        assert tutti.get_json()["totale"] == TOTALE_PROMPT

        filtrati = client.get(
            "/api/v1/legal-skills/prompt-library/prompts?q=licenziamento&forma=lettera", headers=headers
        )
        assert filtrati.status_code == 200
        corpo = filtrati.get_json()
        assert corpo["totale"] >= 1
        assert all(prompt["forma"] == "lettera" for prompt in corpo["prompts"])

        prompt_id = corpo["prompts"][0]["prompt_id"]
        dettaglio = client.get(f"/api/v1/legal-skills/prompt-library/prompts/{prompt_id}", headers=headers)
        assert dettaglio.status_code == 200
        assert "revisione obbligatoria" in dettaglio.get_json()["prompt"]["testo"]

        mancante = client.get("/api/v1/legal-skills/prompt-library/prompts/area.voce.parere", headers=headers)
        assert mancante.status_code == 404


def test_api_aree_ordina_per_profilo_studio(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "prompt-library-test-key"}

    with app.test_client() as client:
        senza_profilo = client.get("/api/v1/legal-skills/prompt-library/aree", headers=headers)
        assert senza_profilo.status_code == 200
        assert senza_profilo.get_json()["aree_preferite"] == []

        profilo = client.post(
            "/api/v1/legal-skills/profile/cold-start",
            json={
                "firm_name": "Studio Test",
                "jurisdictions": ["IT"],
                "practice_areas": ["diritto del lavoro", "privacy"],
            },
            headers=headers,
        )
        assert profilo.status_code == 200

        con_profilo = client.get("/api/v1/legal-skills/prompt-library/aree", headers=headers)
        assert con_profilo.status_code == 200
        payload = con_profilo.get_json()
        assert payload["aree_preferite"] == ["lavoro", "privacy"]
        preferite = [area["area_id"] for area in payload["aree"] if area["preferita"]]
        assert set(preferite) == {"lavoro", "privacy"}
        # Le aree preferite vengono proposte per prime.
        assert {area["area_id"] for area in payload["aree"][:2]} == {"lavoro", "privacy"}


def test_api_prompt_precompilato_dal_fascicolo(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "prompt-library-test-key"}

    gestione = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gestione.nuovo(
        titolo="Rossi contro Bianchi",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Mario Rossi",
        controparte="Bianchi Srl",
        tribunale="Tribunale di Milano",
        numero_rg="1428",
        anno_rg=2026,
        oggetto="Inadempimento del contratto di fornitura",
    )

    with app.test_client() as client:
        entry = client.get(
            "/api/v1/legal-skills/prompt-library/prompts?area=civile&forma=redazione_atto&limit=1", headers=headers
        ).get_json()["prompts"][0]

        precompilato = client.get(
            f"/api/v1/legal-skills/prompt-library/prompts/{entry['prompt_id']}?fascicolo={fascicolo.id}",
            headers=headers,
        )
        assert precompilato.status_code == 200
        prompt = precompilato.get_json()["prompt"]
        assert "Mario Rossi" in prompt["testo"]
        assert "Tribunale di Milano" in prompt["testo"]
        assert prompt["contesto_fascicolo"]["fascicolo_id"] == fascicolo.id
        assert prompt["contesto_fascicolo"]["rg"] == "RG 1428/2026"

        mancante = client.get(
            f"/api/v1/legal-skills/prompt-library/prompts/{entry['prompt_id']}?fascicolo=INESISTENTE",
            headers=headers,
        )
        assert mancante.status_code == 404
        assert mancante.get_json()["code"] == "fascicolo_not_found"


def test_runner_costruisce_skill_sintetica_e_richiesta(library: LegalPromptLibrary):
    dettaglio = library.get_prompt(library.search(area="lavoro", forma="parere")[0]["prompt_id"])

    skill, richiesta = prepara_esecuzione_prompt(dettaglio, nota="Priorità alta per udienza imminente.")

    assert skill.pack_id == PROMPT_PACK_ID
    assert skill.skill_id == dettaglio["prompt_id"]
    assert skill.read_only is True
    assert skill.references == dettaglio["riferimenti"]
    assert richiesta.question.startswith(dettaglio["testo"])
    assert "Nota dell'avvocato: Priorità alta per udienza imminente." in richiesta.question
    assert richiesta.context["prompt_id"] == dettaglio["prompt_id"]


def test_api_esegui_prompt_con_lex_pipeline_governata(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "prompt-library-test-key"}

    gestione = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gestione.nuovo(
        titolo="Rossi contro Bianchi",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Mario Rossi",
        controparte="Bianchi Srl",
        tribunale="Tribunale di Milano",
        oggetto="Inadempimento del contratto di fornitura",
    )

    with app.test_client() as client:
        entry = client.get(
            "/api/v1/legal-skills/prompt-library/prompts?area=civile&forma=parere&limit=1", headers=headers
        ).get_json()["prompts"][0]

        # Senza profilo studio la pipeline resta chiusa.
        bloccato = client.post(
            "/api/v1/legal-skills/prompt-library/run", json={"prompt_id": entry["prompt_id"]}, headers=headers
        )
        assert bloccato.status_code == 409
        assert bloccato.get_json()["code"] == "profile_incomplete"

        profilo = client.post(
            "/api/v1/legal-skills/profile/cold-start",
            json={"firm_name": "Studio Test", "jurisdictions": ["IT"], "practice_areas": ["civile"]},
            headers=headers,
        )
        assert profilo.status_code == 200

        eseguito = client.post(
            "/api/v1/legal-skills/prompt-library/run",
            json={"prompt_id": entry["prompt_id"], "fascicolo": fascicolo.id, "nota": "Preparare entro venerdì."},
            headers=headers,
        )
        assert eseguito.status_code == 200
        result = eseguito.get_json()["result"]
        assert result["pack_id"] == PROMPT_PACK_ID
        assert result["prompt_id"] == entry["prompt_id"]
        assert result["fascicolo_id"] == fascicolo.id
        assert result["needs_review"] is True
        assert result["citations"]
        assert "Mario Rossi" in result["question"]
        assert "Nota dell'avvocato: Preparare entro venerdì." in result["question"]

        # Il risultato entra nella coda di revisione esistente ed è approvabile.
        salvato = client.get(f"/api/v1/legal-skills/runs/{result['run_id']}", headers=headers)
        assert salvato.status_code == 200
        approvato = client.post(f"/api/v1/legal-skills/runs/{result['run_id']}/approve", headers=headers)
        assert approvato.status_code == 200
        assert approvato.get_json()["result"]["needs_review"] is False

        inesistente = client.post(
            "/api/v1/legal-skills/prompt-library/run", json={"prompt_id": "area.voce.parere"}, headers=headers
        )
        assert inesistente.status_code == 404


def test_api_prompt_library_feature_flag_off(tmp_path: Path):
    app = _app(tmp_path, flags={"lex.legalSkills.enabled": False})
    headers = {"X-API-Key": "prompt-library-test-key"}

    with app.test_client() as client:
        risposta = client.get("/api/v1/legal-skills/prompt-library/aree", headers=headers)
    assert risposta.status_code == 403
    assert risposta.get_json()["code"] == "feature_disabled"
