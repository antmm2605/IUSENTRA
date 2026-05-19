from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _normalize_source_token(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class SourceCapability:
    source_code: str
    item_strategy: str
    detail_strategy: str
    attachment_strategy: str
    pdf_required: bool
    ocr_allowed: bool
    reference_extraction_enabled: bool
    context_question_enabled: bool
    publication_destination: str
    rag_destination: str
    jurisprudence_destination: str
    relevance_policy: str
    exclusion_policy: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "famiglia": _source_family(self.source_code),
                "parser_strategy": self.item_strategy,
                "pdf_allowed": bool(
                    self.pdf_required
                    or self.attachment_strategy not in {"none", "manual_free_web_only"}
                ),
                "references_enabled": self.reference_extraction_enabled,
                "context_questions_enabled": self.context_question_enabled,
                "destination": _canonical_destination(self.publication_destination),
                "filtro_interesse_studio_legale": self.relevance_policy,
                "regole_esclusione": self.exclusion_policy,
                "note_diagnostiche": _diagnostic_notes(self),
            }
        )
        return payload


_DEFAULT = SourceCapability(
    source_code="",
    item_strategy="html_listing",
    detail_strategy="detail_if_useful",
    attachment_strategy="official_links",
    pdf_required=False,
    ocr_allowed=True,
    reference_extraction_enabled=True,
    context_question_enabled=True,
    publication_destination="news",
    rag_destination="legal_updates",
    jurisprudence_destination="none",
    relevance_policy="studio_legale_operativo",
    exclusion_policy="navigation_cookie_privacy_contatti_cataloghi_non_documentali",
)


def _source_family(source_code: Any) -> str:
    code = _normalize_source_token(source_code)
    if code.startswith("cassazione_"):
        return "cassazione"
    if code.startswith("openga_"):
        return "open_data_giustizia_amministrativa"
    if code.startswith("codice_"):
        return "codici_normattiva"
    if code.startswith(("inps_", "inail_", "ministero_lavoro")):
        return "lavoro_previdenza"
    if code in {"agcom_provvedimenti", "agcm_bollettino", "anac_documenti", "garante_privacy", "banca_italia_normativa"}:
        return "autorita_indipendenti"
    if code in {"curia_cgue_rss", "eur_lex"}:
        return "unione_europea"
    if code in {"normattiva", "dati_normattiva", "gazzetta_ufficiale"}:
        return "normativa"
    if code in {"pst_giustizia_download"}:
        return "telematico"
    if code.startswith(("studiocataldi_", "avvocatoandreani_")):
        return "fonti_secondarie"
    return "istituzionale"


def _canonical_destination(value: Any) -> str:
    raw = _normalize_source_token(value)
    if raw == "out_of_scope":
        return "out_of_scope"
    if raw in {"rag_only", "technical_metadata"} or "rag_only" in raw:
        return "RAG-only"
    if "osservazione" in raw:
        return "osservazione"
    if "giurisprudenza" in raw:
        return "giurisprudenza"
    if "normativa" in raw:
        return "normativa"
    if "prassi" in raw:
        return "prassi"
    if "news" in raw:
        return "news"
    return raw or "osservazione"


def _diagnostic_notes(capability: SourceCapability) -> str:
    notes = [
        f"parser={capability.item_strategy}",
        f"dettaglio={capability.detail_strategy}",
        f"allegati={capability.attachment_strategy}",
        "PDF obbligatorio" if capability.pdf_required else "PDF se presente",
        "OCR consentito" if capability.ocr_allowed else "OCR non previsto",
    ]
    return "; ".join(notes)


def _cap(source_code: str, **overrides: Any) -> SourceCapability:
    data = asdict(_DEFAULT)
    data.update(overrides)
    data["source_code"] = source_code
    return SourceCapability(**data)


_SECONDARY_POLICY = {
    "item_strategy": "disabled_secondary",
    "detail_strategy": "manual_free_web_only",
    "attachment_strategy": "none",
    "pdf_required": False,
    "ocr_allowed": False,
    "reference_extraction_enabled": False,
    "context_question_enabled": False,
    "publication_destination": "out_of_scope",
    "rag_destination": "none",
    "jurisprudence_destination": "none",
    "relevance_policy": "fonte_secondaria_non_ufficiale",
    "exclusion_policy": "non pubblicare come fonte ufficiale; usare solo Web libero esplicito",
}


SOURCE_CAPABILITIES: dict[str, SourceCapability] = {
    "gazzetta_ufficiale": _cap(
        "gazzetta_ufficiale",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="normativa_or_news",
        rag_destination="official_rag",
        relevance_policy="norme_decreti_regolamenti_avvisi_normativi",
    ),
    "normattiva": _cap(
        "normattiva",
        item_strategy="normattiva_index",
        detail_strategy="article_or_act_detail",
        attachment_strategy="none_unless_official_document",
        publication_destination="normativa",
        rag_destination="official_normative_rag",
        relevance_policy="testi_vigenti_articoli_commi_codici",
    ),
    "dati_normattiva": _cap(
        "dati_normattiva",
        item_strategy="technical_catalog",
        detail_strategy="metadata_only",
        attachment_strategy="document_resources_only",
        publication_destination="rag_only",
        rag_destination="technical_metadata",
        relevance_policy="dataset_normativi_solo_come_evidenza",
        exclusion_policy="catalogo tecnico non pubblicabile come aggiornamento",
    ),
    "corte_costituzionale": _cap(
        "corte_costituzionale",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="pronunce_ordinanze_parametri_normativi",
    ),
    "corte_conti": _cap(
        "corte_conti",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza_or_rag_only",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="sentenze_responsabilita_erariale_contabilita_appalti",
    ),
    "cassazione_massimario": _cap(
        "cassazione_massimario",
        item_strategy="cassazione_detail_cards",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza_or_rag",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="solo_schede_decisioni_massime_questioni",
        exclusion_policy="escludere pagine servizio privacy cookie URP supporto",
    ),
    "cassazione_ultime_sent_ord_questioni": _cap(
        "cassazione_ultime_sent_ord_questioni",
        item_strategy="cassazione_index_civile_penale",
        detail_strategy="detail_html_only_content_id",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza_or_rag",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="solo_url_dettaglio_content_id",
        exclusion_policy="escludere privacy URP cookie navigazione supporto",
    ),
    "giustizia_amministrativa": _cap(
        "giustizia_amministrativa",
        item_strategy="html_listing_disabled_by_default",
        detail_strategy="detail_html_backfill_only",
        attachment_strategy="official_pdf_links",
        publication_destination="giurisprudenza_or_rag",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_tar_cds_number_year",
        relevance_policy="decisioni_pareri_non_home_o_ricerca_generica",
    ),
    "giustizia_amministrativa_decisioni_pareri": _cap(
        "giustizia_amministrativa_decisioni_pareri",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_tar_cds_number_year",
        relevance_policy="decisioni_pareri_con_estremi",
    ),
    "eur_lex": _cap(
        "eur_lex",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_or_celex",
        publication_destination="normativa_or_prassi",
        rag_destination="official_eu_rag",
        relevance_policy="atti_ue_regolamenti_direttive_celex",
    ),
    "agenzia_entrate": _cap(
        "agenzia_entrate",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="circolari_risoluzioni_interpelli_provvedimenti_tributari",
    ),
    "ministero_lavoro": _cap(
        "ministero_lavoro",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="lavoro_previdenza_decreti_circolari",
    ),
    "ministero_lavoro_interpelli": _cap(
        "ministero_lavoro_interpelli",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="prassi",
        rag_destination="official_prassi_rag",
        relevance_policy="interpelli_lavoro_con_numero_e_soluzione",
    ),
    "garante_privacy": _cap(
        "garante_privacy",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="provvedimenti_gdpr_sanzioni_data_breach_lavoro",
    ),
    "anac_documenti": _cap(
        "anac_documenti",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="delibere_pareri_linee_guida_appalti_accesso_atti",
    ),
    "inps_circolari": _cap(
        "inps_circolari",
        item_strategy="feed_items",
        detail_strategy="feed_detail_if_poor",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi",
        rag_destination="official_prassi_rag",
        relevance_policy="circolari_previdenza_termini_contributi_contenzioso",
    ),
    "inps_messaggi": _cap(
        "inps_messaggi",
        item_strategy="inps_search_api",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="messaggi_previdenza_termini_contributi_contenzioso",
    ),
    "inps_sentenze": _cap(
        "inps_sentenze",
        item_strategy="feed_items",
        detail_strategy="feed_detail_if_poor",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza_or_rag",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="sentenze_previdenziali_con_estremi",
    ),
    "curia_cgue_rss": _cap(
        "curia_cgue_rss",
        item_strategy="feed_items",
        detail_strategy="feed_detail_if_poor",
        attachment_strategy="official_pdf_links",
        publication_destination="giurisprudenza_ue",
        rag_destination="official_eu_case_law_rag",
        jurisprudence_destination="structured_if_case_number_year",
        relevance_policy="sentenze_conclusioni_cgue_cause_direttive_regolamenti",
    ),
    "istat_prezzi": _cap(
        "istat_prezzi",
        item_strategy="feed_items",
        detail_strategy="feed_detail_if_poor",
        attachment_strategy="technical_document_links",
        publication_destination="prassi_or_rag_only",
        rag_destination="official_data_rag",
        relevance_policy="indici_rivalutazioni_decorrenze_calcoli_legali",
        exclusion_policy="news_generica_prezzi_non_operativa",
    ),
    "mimit_incentivi": _cap(
        "mimit_incentivi",
        item_strategy="feed_items",
        detail_strategy="feed_detail_if_poor",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="decreti_bandi_incentivi_termini_imprese",
    ),
    "agcm_bollettino": _cap(
        "agcm_bollettino",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news",
        rag_destination="official_prassi_rag",
        relevance_policy="bollettini_provvedimenti_sanzioni_concorrenza_consumatori",
    ),
    "agcom_provvedimenti": _cap(
        "agcom_provvedimenti",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_news_or_rag",
        rag_destination="official_prassi_rag",
        relevance_policy="delibere_sanzioni_controversie_corecom_tutela_utenti_diritto_autore",
        exclusion_policy="consultazioni_contributi_assoradio_frequenze_non_operative",
    ),
    "banca_italia_normativa": _cap(
        "banca_italia_normativa",
        item_strategy="html_listing",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_normativa",
        rag_destination="official_prassi_rag",
        relevance_policy="normativa_vigilanza_disposizioni_circolari_regolamenti",
    ),
    "inail_istruzioni_operative": _cap(
        "inail_istruzioni_operative",
        item_strategy="html_listing_disabled_by_default",
        detail_strategy="detail_html_backfill_only",
        attachment_strategy="official_pdf_links",
        publication_destination="prassi_or_rag",
        rag_destination="official_prassi_rag",
        relevance_policy="istruzioni_lavoro_infortuni_termini_operativi",
    ),
    "pst_giustizia_download": _cap(
        "pst_giustizia_download",
        item_strategy="html_listing",
        detail_strategy="download_metadata",
        attachment_strategy="technical_download_links",
        publication_destination="rag_only",
        rag_destination="telematico_rag",
        relevance_policy="specifiche_deposito_telematico_schemi_software_manuali",
        exclusion_policy="software_generico_non_collegato_a_deposito_o_specifiche",
    ),
    "cassazione_citazioni_verificate": _cap(
        "cassazione_citazioni_verificate",
        item_strategy="verified_citation_detail",
        detail_strategy="detail_html",
        attachment_strategy="official_pdf_links",
        pdf_required=True,
        publication_destination="giurisprudenza_or_rag",
        rag_destination="official_case_law_rag",
        jurisprudence_destination="structured_if_court_number_year",
        relevance_policy="solo_citazioni_con_url_verificato",
    ),
}

for _code in (
    "openga_giustizia_amministrativa",
    "openga_calendario_udienze",
    "openga_decreti",
    "openga_ordinanze",
    "openga_pareri",
    "openga_provvedimenti_pubblicati",
    "openga_ricorsi_definiti",
    "openga_ricorsi_pendenti",
    "openga_ricorsi_pervenuti",
    "openga_sentenze",
):
    SOURCE_CAPABILITIES[_code] = _cap(
        _code,
        item_strategy="ckan_package_resources",
        detail_strategy="resource_detail_if_document",
        attachment_strategy="resource_document_links",
        pdf_required=_code in {"openga_sentenze", "openga_ordinanze", "openga_decreti", "openga_pareri"},
        publication_destination="giurisprudenza_if_document_else_rag_only",
        rag_destination="official_open_data_rag",
        jurisprudence_destination="structured_if_tar_cds_number_year",
        relevance_policy="documento_giuridico_concreto_non_catalogo",
        exclusion_policy="cataloghi_dataset_record_statistici_non_pubblicabili",
    )

for _code, _label in (
    ("codice_civile", "articoli_commi_codice_civile"),
    ("codice_procedura_civile", "articoli_commi_codice_procedura_civile"),
    ("codice_penale", "articoli_commi_codice_penale"),
    ("codice_procedura_penale", "articoli_commi_codice_procedura_penale"),
    ("codice_processo_amministrativo", "articoli_commi_codice_processo_amministrativo"),
    ("codice_strada", "articoli_commi_codice_strada"),
):
    SOURCE_CAPABILITIES[_code] = _cap(
        _code,
        item_strategy="normattiva_code_index",
        detail_strategy="article_detail",
        attachment_strategy="none_unless_official_document",
        publication_destination="normativa",
        rag_destination="official_normative_rag",
        relevance_policy=_label,
    )

for _code in (
    "studiocataldi_codice_civile",
    "avvocatoandreani_codice_procedura_civile",
    "studiocataldi_codice_penale",
    "avvocatoandreani_codice_strada",
):
    SOURCE_CAPABILITIES[_code] = _cap(_code, **_SECONDARY_POLICY)


NAVIGATION_MARKERS = (
    "cookie",
    "privacy policy",
    "informativa privacy",
    "urp",
    "contatti",
    "newsletter",
    "mappa del sito",
    "supporto",
    "login",
)
ACCOUNTING_LOW_VALUE_MARKERS = (
    "liquidazione fattura",
    "liquidazione della fattura",
    "liquidazione fatture",
    "pagamento fattura",
    "impegno di spesa",
    "mandato di pagamento",
    "durc",
)
LEGAL_CONTEXT_MARKERS = (
    "ricorso",
    "contenzioso",
    "tar",
    "consiglio di stato",
    "gara",
    "appalto",
    "affidamento",
    "accesso agli atti",
    "sanzione",
    "sentenza",
    "ordinanza",
)
DOCUMENT_MARKERS = (
    "sentenza",
    "ordinanza",
    "decreto",
    "parere",
    "provvedimento",
    "delibera",
    "ricorso",
    "r.g.",
    "rg ",
    "tar",
    "consiglio di stato",
)
AGCOM_LOW_MARKERS = (
    "consultazione pubblica",
    "contributo alla consultazione",
    "assoradio",
    "pianificazione frequenze",
    "frequenza dab",
)
AGCOM_KEEP_MARKERS = (
    "delibera",
    "provvedimento",
    "sanzion",
    "controvers",
    "corecom",
    "tutela utenti",
    "diritto d'autore",
    "inottemperanza",
)

OPEN_DATA_CATALOG_MARKERS = (
    "dataset statistico",
    "conteggi",
    "per tipo di decisione",
    "catalogo dataset",
    "catalogo open data",
    "metadati dataset",
)


def normalize_source_code(value: Any) -> str:
    return _normalize_source_token(value)


def get_source_capability(source_code: Any, *, category: Any = "") -> SourceCapability:
    code = normalize_source_code(source_code)
    if code in SOURCE_CAPABILITIES:
        return SOURCE_CAPABILITIES[code]
    category_text = normalize_source_code(category)
    if category_text == "giurisprudenza":
        return _cap(
            code,
            publication_destination="giurisprudenza_or_rag",
            rag_destination="official_case_law_rag",
            jurisprudence_destination="structured_if_court_number_year",
        )
    if category_text == "normativa":
        return _cap(code, publication_destination="normativa", rag_destination="official_normative_rag")
    if category_text == "telematico":
        return _cap(
            code,
            attachment_strategy="technical_download_links",
            publication_destination="rag_only",
            rag_destination="telematico_rag",
        )
    return _cap(code)


def source_capability_payload(source: dict[str, Any]) -> dict[str, Any]:
    return get_source_capability(source.get("code"), category=source.get("category")).to_dict()


def _haystack(*values: Any) -> str:
    return " ".join(" ".join(str(value or "").lower().split()) for value in values if str(value or "").strip())


def looks_like_open_data_document(text: Any) -> bool:
    haystack = _haystack(text)
    return any(marker in haystack for marker in DOCUMENT_MARKERS)


def _has_positive_legal_context(text: str) -> bool:
    for marker in LEGAL_CONTEXT_MARKERS:
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0:
                break
            prefix = text[max(0, index - 40) : index]
            if not any(value in prefix for value in ("senza ", "non ", "nessun ", "nessuna ")):
                return True
            start = index + len(marker)
    return False


def source_exclusion_reason(
    source: dict[str, Any],
    *,
    title: Any = "",
    body_text: Any = "",
    url: Any = "",
    has_structured_reference: bool = False,
) -> str:
    code = normalize_source_code(source.get("code"))
    capability = get_source_capability(code, category=source.get("category"))
    text = _haystack(title, body_text, url, source.get("category"))
    if capability.publication_destination == "out_of_scope":
        return "Fonte secondaria non ufficiale: resta fuori dal corpus ufficiale e si usa solo con Web libero manuale."
    navigation_markers = NAVIGATION_MARKERS
    if code == "garante_privacy":
        navigation_markers = tuple(marker for marker in NAVIGATION_MARKERS if marker != "newsletter")
    if any(marker in text for marker in navigation_markers) and not has_structured_reference:
        return "Pagina di navigazione, privacy, cookie, contatti o supporto: non pubblicabile come aggiornamento."
    if any(marker in text for marker in ACCOUNTING_LOW_VALUE_MARKERS) and not _has_positive_legal_context(text):
        return "Atto contabile interno senza ricorso, appalto, contenzioso o sanzione: fuori perimetro studio legale."
    if code == "agcom_provvedimenti" and any(marker in text for marker in AGCOM_LOW_MARKERS) and not any(
        marker in text for marker in AGCOM_KEEP_MARKERS
    ):
        return "Consultazione, contributo o pianificazione frequenze AGCOM senza valore operativo per lo studio."
    source_type = normalize_source_code(source.get("source_type"))
    parser_type = normalize_source_code(source.get("parser_type"))
    if source_type == "open_data" or parser_type == "ckan_json" or code.startswith("openga_"):
        if any(marker in text for marker in OPEN_DATA_CATALOG_MARKERS) and not has_structured_reference:
            return "Catalogo o dataset open data senza documento giuridico concreto: conservato solo come evidenza RAG."
    if (source_type == "open_data" or parser_type == "ckan_json" or code.startswith("openga_")) and not (
        has_structured_reference or looks_like_open_data_document(text)
    ):
        return "Catalogo o dataset open data senza documento giuridico concreto: conservato solo come evidenza RAG."
    if code == "pst_giustizia_download" and not any(
        marker in text
        for marker in ("deposito", "telematico", "pct", "specifiche", "schema", "manuale", "redattore")
    ):
        return "Download tecnico PST non collegato a deposito, specifiche o manuali operativi."
    return ""


def publication_destination_label(value: Any) -> str:
    labels = {
        "normativa": "Normativa",
        "normativa_or_news": "Normativa o notizia",
        "normativa_or_prassi": "Normativa o prassi",
        "giurisprudenza": "Giurisprudenza",
        "giurisprudenza_or_rag": "Giurisprudenza o RAG",
        "giurisprudenza_or_rag_only": "Giurisprudenza o solo RAG",
        "giurisprudenza_if_document_else_rag_only": "Giurisprudenza se documentale, altrimenti solo RAG",
        "giurisprudenza_ue": "Giurisprudenza UE",
        "prassi": "Prassi",
        "prassi_or_news": "Prassi o notizia",
        "prassi_or_news_or_rag": "Prassi, notizia o RAG",
        "prassi_or_normativa": "Prassi o normativa",
        "prassi_or_rag": "Prassi o RAG",
        "prassi_or_rag_only": "Prassi o solo RAG",
        "rag_only": "Solo RAG",
        "news": "Notizia",
        "out_of_scope": "Fuori perimetro",
    }
    return labels.get(str(value or "").strip(), str(value or "").replace("_", " ").strip() or "Da verificare")


def capability_required_source_codes() -> set[str]:
    return set(SOURCE_CAPABILITIES)
