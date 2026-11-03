"""Regressioni della verifica visiva dell'area Documenti e redazione (02/11/2026).

Base normativa delle correzioni ai contratti: artt. 21 e 447-bis c.p.c. (foro delle locazioni, del
comodato di immobili e dell'affitto d'azienda); art. 2 e art. 36 L. 392/1978 (sublocazione e cessione);
artt. 27-29 e 32 L. 392/1978 (locazioni non abitative); artt. 1804, 1809 c.c. (comodato).
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.contratti.bozza import componi
from web.services.react_document_archive_bridge import build_react_document_archive_payload
from web.services.react_template_atti_bridge import _channel_label, _state_label, _tassonomia, _variable_names


def _archivio(documenti):
    fascicolo = SimpleNamespace(
        id="F1", numero="2026/001", numero_rg="", anno_rg="", titolo="Prova", nome_cliente="Cliente",
        stato="APERTO", documenti=documenti, documenti_cestino=[],
    )
    gestore = SimpleNamespace(tutti=lambda archiviati=True: [fascicolo])
    return build_react_document_archive_payload(get_fascicoli=lambda: gestore, query={})


def _doc(doc_id, nome, note="", fonte="CARICAMENTO_STUDIO", tipo="ALTRO"):
    return SimpleNamespace(
        id=doc_id, nome=nome, nome_originale=nome, percorso="", tipo=tipo, dimensione_bytes=10,
        data_caricamento="2026-11-02T10:00:00", data_documento="2026-11-02", note=note, tags=[],
        fonte_documento=fonte, eliminato_il="", eliminato_da="",
    )


def test_note_senza_marcatore_tecnico_e_con_date_italiane():
    nota = ("IUSENTRA_PROVVEDIMENTO_CANCELLERIA:pec_abc123\n"
            "Copia informativa del provvedimento ricevuta il 2026-11-02 (SENTENZA).")
    payload = _archivio([_doc("D1", "25637478s.pdf", nota, fonte="PEC_CANCELLERIA", tipo="PARCELLA")])
    riga = payload["items"][0]
    assert "IUSENTRA_" not in riga["notes"] and "pec_abc123" not in riga["notes"]
    assert "02/11/2026" in riga["notes"] and "2026-11-02" not in riga["notes"]
    assert riga["source"] == "PEC di cancelleria"
    assert riga["typeLabel"] == "Parcella"


def test_formato_solo_da_estensioni_reali():
    payload = _archivio([
        _doc("D1", "Ricorso 23.11.2025"), _doc("D2", "atto ric. Compagnone"), _doc("D3", "Memoria.docx"),
    ])
    formati = {riga["name"]: riga["format"] for riga in payload["items"]}
    assert formati == {"Ricorso 23.11.2025": "ALTRO", "atto ric. Compagnone": "ALTRO", "Memoria.docx": "DOCX"}
    etichette = {voce["value"]: voce["label"] for voce in payload["facets"]["formats"]}
    assert etichette["ALTRO"] == "Altro formato"


def test_catalogo_modelli_senza_codici_tecnici():
    assert _channel_label("NESSUNO") == "Nessun deposito telematico"
    assert _channel_label("PST_GDP") == "PST · Giudice di pace"
    assert _state_label("draft_professionale") == "Bozza professionale"
    assert _tassonomia("Core processuale e civile") == "Processuale e civile essenziale"
    assert _variable_names(["timbro_studio", "valore_causa"])[0]["label"] == "Timbro studio"


def test_categorie_e_materie_con_la_stessa_grafia():
    from web.services.react_template_atti_bridge import _counter_section, _forme_canoniche

    forme = _forme_canoniche(["Lavoro e Previdenza", "Lavoro e previdenza", "Famiglia e Persone"])
    assert forme["lavoro e previdenza"] == "Lavoro e previdenza"
    sezione = _counter_section("materie", "Materie", "Modelli per materia", ["Lavoro e Previdenza", "Lavoro e previdenza"], "")
    assert [(voce["label"], voce["value"]) for voce in sezione["items"]] == [("Lavoro e previdenza", 2)]


def _articoli(contratto_id):
    return {a["chiave"]: a for a in componi(contratto_id, {}, {})["articoli"]}


def test_locazioni_foro_del_luogo_dell_immobile_senza_deroga():
    for contratto_id in ("locazione_abitativa", "locazione_uso_diverso", "comodato_immobiliare", "affitto_azienda"):
        articoli = _articoli(contratto_id)
        assert "legge_foro" not in articoli, contratto_id
        assert "447-bis" in articoli["foro_immobile"]["norma"]
        testo_approvazione = articoli.get("approvazione_specifica", {}).get("testo", "")
        assert "deroga alla competenza" not in testo_approvazione


def test_sublocazione_e_locazione_non_abitativa_citano_le_norme_giuste():
    abitativa = _articoli("locazione_abitativa")
    assert abitativa["sublocazione_divieto"]["norma"].startswith("art. 2 L. 392/1978")
    assert "27 L. 392/1978" not in abitativa["recesso_conduttore"]["norma"]
    diverso = _articoli("locazione_uso_diverso")
    assert "durata_locazione" not in diverso and "canone_locazione" not in diverso
    assert "art. 36 L. 392/1978" in diverso["sublocazione_diverso"]["norma"]
    assert "cedolare" not in diverso["canone_locazione_diverso"]["testo"]


def test_comodato_parla_di_comodatario_e_senza_approvazione_vuota():
    articoli = _articoli("comodato_immobiliare")
    assert "comodatario" in articoli["riconsegna_comodato"]["testo"]
    assert "conduttore" not in articoli["riconsegna_comodato"]["testo"]
    assert "approvazione_specifica" not in articoli


def test_etichette_campi_compilatore_in_italiano_e_uffici_pertinenti():
    from web.blueprints.api_v1_react import _react_template_field_label, _react_template_office_options

    assert _react_template_field_label("practice_reference", "Practice Reference") == "Riferimento pratica"
    assert _react_template_field_label("_lawyer_pec", "") == "PEC difensore"
    assert _react_template_field_label("court_name", "Ufficio giudiziario") == "Ufficio giudiziario"
    assert _react_template_office_options({"name": "competent_tax_court", "label": "Corte di Giustizia Tributaria Competente"}) == []
    assert _react_template_office_options({"name": "tax_authority_or_resistant_party", "label": "Ente Impositore / Resistente"}) == []
    autorita = [voce["label"] for voce in _react_template_office_options({"name": "proceeding_authority", "label": "Autorità procedente"})]
    assert any(etichetta.startswith("Procura") for etichetta in autorita)
    assert any(etichetta.startswith("Tribunale") for etichetta in autorita)
    uffici = [voce["label"] for voce in _react_template_office_options({"name": "court_name", "label": "Ufficio giudiziario"})]
    assert any(etichetta.startswith("Tribunale") for etichetta in uffici)
    assert not any(etichetta.startswith("Procura") for etichetta in uffici)
