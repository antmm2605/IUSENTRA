from web.services.assistente_competencies import (
    build_competence_catalog_prompt,
    build_competence_prompt_blocks,
    match_competence_profiles,
    resolve_competence_section_titles,
)


def test_competence_registry_copre_l_area_economica_dello_studio():
    profiles = match_competence_profiles("mi controlli preventivi, fatturazione e pagamenti", limit=3)

    assert profiles
    assert profiles[0].topic == "economico"
    assert "Fatturazione" in profiles[0].section_titles
    assert "Preventivi" in profiles[0].section_titles
    assert "Tariffario" in profiles[0].section_titles


def test_competence_registry_copre_il_centro_servizi_telematici():
    profiles = match_competence_profiles("stato connessioni pst pdp pat e import fascicoli", limit=3)

    assert profiles
    assert profiles[0].topic == "telematico"
    assert profiles[0].label == "Centro Servizi Telematici"
    assert "PEC e canali email" in profiles[0].section_titles


def test_competence_prompt_blocks_guidano_su_moduli_e_template():
    blocks = build_competence_prompt_blocks("mi serve un template atto e il catalogo atti", limit=3)

    assert blocks
    assert any("Atti, template e catalogo atti" in block for block in blocks)


def test_competence_section_titles_uniscono_sync_e_configurazione():
    titles = resolve_competence_section_titles("sincronizza calendario, pec e impostazioni studio", limit=3)

    assert "Impostazioni studio" in titles
    assert "PEC e canali email" in titles
    assert "Agenda" in titles


def test_competence_registry_spiega_notifiche_legali_e_documento_ufficio():
    profiles = match_competence_profiles(
        "come funziona la relata notifica quando il documento d'ufficio va scaricato dal Portale Servizi?",
        limit=3,
    )
    blocks = build_competence_prompt_blocks("notifiche legali L. 53 con RAC RdAC e Portale Servizi", limit=3)

    assert profiles
    assert profiles[0].topic == "pec_firma_comunicazioni"
    assert "Centro Servizi Telematici" in profiles[0].section_titles
    assert any("rileva il documento rilasciato dall'ufficio" in block for block in blocks)
    assert any("RAC/RdAC" in block for block in blocks)


def test_competence_catalog_prompt_elenca_le_aree_principali_di_hacs():
    prompt = build_competence_catalog_prompt()

    assert "Centro Servizi Telematici" in prompt
    assert "Tariffario, preventivi, fatturazione e pagamenti" in prompt
    assert "Applicazioni e moduli del gestionale" in prompt
