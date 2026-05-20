"""Consultazione multi-fonte governata per procedure XSD.

Il modulo non effettua scraping né download automatici: costruisce un piano di
fonti tracciate e registra evidenze sintetiche riformulate, pronte per review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from pct.procedure_knowledge_pipeline import add_source_evidence, save_knowledge_card
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository
from pct.procedure_xsd_mapper import infer_mapping_for_xsd


PST_DOWNLOAD_URL = "https://pst.giustizia.it/PST/it/download.page"
PST_SPECIFICHE_URL = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC382"
CPC_BASE = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443"
DL_179_ART_16_BIS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2012-10-18;179~art16bis"
L_53_ART_3_BIS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1994-01-21;53~art3bis"


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    source_type: str
    source_url: str
    source_title: str
    evidence_kind: str
    extracted_principle: str
    copyright_policy: str
    reliability_score: int = 90
    review_status: str = "needs_review"

    def to_evidence(self, procedure_code: str, xsd_code: str | None) -> dict[str, Any]:
        return {
            **asdict(self),
            "procedure_code": procedure_code,
            "xsd_code": xsd_code,
            "last_checked_at": date.today().isoformat(),
        }


@dataclass(frozen=True)
class SourceResearchPlan:
    xsd_code: str
    xsd_label: str
    xsd_family_label: str
    xsd_area_label: str
    procedure_code: str
    family: str
    references: list[SourceReference]
    review_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "xsd_code": self.xsd_code,
            "xsd_label": self.xsd_label,
            "xsd_family_label": self.xsd_family_label,
            "xsd_area_label": self.xsd_area_label,
            "procedure_code": self.procedure_code,
            "family": self.family,
            "references": [asdict(item) for item in self.references],
            "review_required": self.review_required,
        }


@dataclass(frozen=True)
class SourceResearchReport:
    dry_run: bool
    xsd_total: int
    source_evidence_created: int
    cards_created: int
    review_required: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _prefix(xsd_code: str | None) -> str:
    return str(xsd_code or "")[:3]


def _cpc_reference(
    *,
    source_id: str,
    article: str,
    title: str,
    evidence_kind: str,
    principle: str,
    reliability_score: int = 85,
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_type="official",
        source_url=f"{CPC_BASE}~art{article}",
        source_title=f"Codice di procedura civile - {title}",
        evidence_kind=evidence_kind,
        extracted_principle=principle,
        copyright_policy="official_public",
        reliability_score=reliability_score,
    )


def _general_cpc_references() -> list[SourceReference]:
    return [
        _cpc_reference(
            source_id="cpc_art_125",
            article="125",
            title="art. 125",
            evidence_kind="requisiti_formali_atto",
            principle="Ogni atto processuale generato deve essere verificato rispetto ai requisiti formali e alla sottoscrizione richiesti dal rito applicabile.",
            reliability_score=85,
        )
    ]


def _ordinary_civil_introductory_references() -> list[SourceReference]:
    return [
        _cpc_reference(
            source_id="cpc_art_163",
            article="163",
            title="art. 163",
            evidence_kind="atto_introduttivo_civile",
            principle="Quando il workflow genera un atto introduttivo ordinario, il contenuto va confrontato con i requisiti dell'atto di citazione o con la forma speciale del rito scelto.",
            reliability_score=80,
        ),
    ]


def _base_references() -> list[SourceReference]:
    return [
        SourceReference(
            source_id="pst_xsd_download",
            source_type="technical",
            source_url=PST_DOWNLOAD_URL,
            source_title="Portale Servizi Telematici - File ufficiali del Processo Civile Telematico",
            evidence_kind="catalogo_xsd",
            extracted_principle="Il codice oggetto deve provenire dal catalogo PST/XSD attivo e non può essere inventato dall'applicazione.",
            copyright_policy="official_public",
            reliability_score=95,
        ),
        SourceReference(
            source_id="pst_specifiche_art_34",
            source_type="technical",
            source_url=PST_SPECIFICHE_URL,
            source_title="Specifiche tecniche PCT pubblicate sul Portale Servizi Telematici",
            evidence_kind="specifica_tecnica",
            extracted_principle="La busta e i dati strutturati del deposito vanno verificati rispetto alle specifiche tecniche applicabili.",
            copyright_policy="official_public",
            reliability_score=90,
        ),
        SourceReference(
            source_id="dl_179_2012_art_16_bis",
            source_type="official",
            source_url=DL_179_ART_16_BIS,
            source_title="D.L. 179/2012 - art. 16-bis",
            evidence_kind="deposito_telematico",
            extracted_principle="Il deposito telematico richiede canale e ricevute coerenti con la disciplina del processo telematico.",
            copyright_policy="official_public",
            reliability_score=90,
        ),
        SourceReference(
            source_id="l_53_1994_art_3_bis",
            source_type="official",
            source_url=L_53_ART_3_BIS,
            source_title="L. 53/1994 - notificazioni in proprio via PEC",
            evidence_kind="notifica_telematica",
            extracted_principle="La notifica in proprio via PEC richiede indirizzo da fonte idonea, relata e prove di accettazione/consegna.",
            copyright_policy="official_public",
            reliability_score=90,
        ),
    ]


def _family_references(xsd_object: dict[str, Any]) -> tuple[str, list[SourceReference]]:
    prefix = _prefix(xsd_object.get("xsd_code"))
    label = " ".join(
        str(xsd_object.get(key) or "").lower()
        for key in ("xsd_label", "xsd_family_label", "xsd_area_label")
    )
    if prefix in {"010", "050"}:
        return (
            "ingiunzione",
            [
                _cpc_reference(
                    source_id="cpc_art_633",
                    article="633",
                    title="art. 633",
                    evidence_kind="presupposti_ingiunzione",
                    principle="La procedura monitoria richiede verifica dei presupposti e della prova scritta prima della richiesta.",
                    reliability_score=90,
                ),
                _cpc_reference(
                    source_id="cpc_art_644",
                    article="644",
                    title="art. 644",
                    evidence_kind="notifica_decreto_ingiuntivo",
                    principle="Dopo il provvedimento va valutata la notifica del decreto e la conservazione della prova.",
                    reliability_score=90,
                ),
            ],
        )
    if prefix == "030":
        return (
            "sfratto",
            [
                _cpc_reference(
                    source_id="cpc_art_657",
                    article="657",
                    title="art. 657",
                    evidence_kind="licenza_sfratto_finita_locazione",
                    principle="La convalida di sfratto richiede impostazione dell'intimazione e citazione con attenzione alla notifica.",
                    reliability_score=90,
                ),
                _cpc_reference(
                    source_id="cpc_art_658",
                    article="658",
                    title="art. 658",
                    evidence_kind="sfratto_morosita",
                    principle="La morosità va documentata e coordinata con intimazione, citazione e successive prove di notifica.",
                    reliability_score=90,
                ),
            ],
        )
    if prefix in {"011", "012", "014", "015", "017", "019", "051", "052", "053", "055", "059"}:
        return (
            "cautelare",
            [
                _cpc_reference(
                    source_id="cpc_art_669_bis",
                    article="669bis",
                    title="art. 669-bis",
                    evidence_kind="procedimento_cautelare",
                    principle="Il cautelare richiede verifica di rito, competenza, presupposti e gestione degli adempimenti successivi.",
                    reliability_score=90,
                ),
                _cpc_reference(
                    source_id="cpc_art_700",
                    article="700",
                    title="art. 700",
                    evidence_kind="urgenza_residuale",
                    principle="Le misure d'urgenza residuali richiedono cautela nella qualificazione e review professionale.",
                    reliability_score=85,
                ),
            ],
        )
    if prefix == "020":
        return (
            "possessoria",
            [
                _cpc_reference(
                    source_id="cpc_art_703",
                    article="703",
                    title="art. 703",
                    evidence_kind="procedimento_possessorio",
                    principle="Le azioni possessorie richiedono qualificazione della tutela, documenti del possesso e review su udienza/notifica.",
                    reliability_score=90,
                )
            ],
        )
    if prefix == "016":
        return (
            "famiglia_mantenimento",
            [
                _cpc_reference(
                    source_id="cpc_art_473bis",
                    article="473bis",
                    title="art. 473-bis",
                    evidence_kind="rito_famiglia",
                    principle="I procedimenti in materia di famiglia richiedono verifica del rito unitario, dei documenti reddituali e degli adempimenti di tutela delle parti.",
                    reliability_score=85,
                ),
                SourceReference(
                    source_id="cc_art_446",
                    source_type="official",
                    source_url="https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art446",
                    source_title="Codice civile - art. 446",
                    evidence_kind="alimenti_mantenimento",
                    extracted_principle="Le richieste provvisorie di alimenti o mantenimento richiedono coordinamento tra presupposti sostanziali, rito e documenti reddituali.",
                    copyright_policy="official_public",
                    reliability_score=80,
                ),
            ],
        )
    if prefix in {"100", "101", "102", "109"}:
        return (
            "contenzioso_civile_generale",
            _ordinary_civil_introductory_references()
            + [
                _cpc_reference(
                    source_id="cpc_art_99",
                    article="99",
                    title="art. 99",
                    evidence_kind="domanda_giudiziale",
                    principle="La pratica va ricondotta a una domanda giudiziale concreta e a un interesse processuale verificato sul caso.",
                    reliability_score=80,
                ),
                _cpc_reference(
                    source_id="cpc_art_183",
                    article="183",
                    title="art. 183",
                    evidence_kind="trattazione_civile",
                    principle="Il workflow deve prevedere controllo su trattazione, memorie, richieste istruttorie e termini del rito applicabile.",
                    reliability_score=80,
                ),
            ],
        )
    if prefix == "103":
        return (
            "navigazione_review",
            _ordinary_civil_introductory_references()
            + [
                _cpc_reference(
                    source_id="cpc_art_99_navigazione_review",
                    article="99",
                    title="art. 99",
                    evidence_kind="domanda_navigazione",
                    principle="Le controversie di navigazione richiedono inquadramento specialistico della domanda e del rito concretamente applicabile.",
                    reliability_score=75,
                )
            ],
        )
    if prefix in {"104", "105", "106"}:
        return (
            "corte_appello_trap_review",
            [
                _cpc_reference(
                    source_id="cpc_art_341",
                    article="341",
                    title="art. 341",
                    evidence_kind="impugnazione_appello",
                    principle="Le pratiche davanti alla Corte di appello richiedono verifica di ufficio competente, mezzo di impugnazione e forma dell'atto.",
                    reliability_score=80,
                ),
                _cpc_reference(
                    source_id="cpc_art_342",
                    article="342",
                    title="art. 342",
                    evidence_kind="contenuto_appello",
                    principle="Quando l'atto è un appello, il contenuto deve essere verificato rispetto ai requisiti specifici del mezzo.",
                    reliability_score=80,
                ),
            ],
        )
    if prefix == "108":
        return (
            "giudice_pace",
            [
                _cpc_reference(
                    source_id="cpc_art_316",
                    article="316",
                    title="art. 316",
                    evidence_kind="procedimento_giudice_pace",
                    principle="Le pratiche del Giudice di pace richiedono verifica del rito, dell'ufficio competente e della modalità di introduzione.",
                    reliability_score=85,
                ),
                _cpc_reference(
                    source_id="cpc_art_318",
                    article="318",
                    title="art. 318",
                    evidence_kind="domanda_giudice_pace",
                    principle="La domanda davanti al Giudice di pace va controllata su contenuto, citazione e dati necessari all'iscrizione.",
                    reliability_score=80,
                ),
            ],
        )
    if prefix in {"110", "111", "112"}:
        return (
            "persone_famiglia_minori",
            [
                _cpc_reference(
                    source_id="cpc_art_70",
                    article="70",
                    title="art. 70",
                    evidence_kind="intervento_pubblico_ministero",
                    principle="Nelle materie di stato, persone, famiglia e minori va valutata la partecipazione del pubblico ministero e il rito applicabile.",
                    reliability_score=80,
                ),
                _cpc_reference(
                    source_id="cpc_art_473bis_famiglia",
                    article="473bis",
                    title="art. 473-bis",
                    evidence_kind="rito_persone_famiglia_minori",
                    principle="Il rito persone, minorenni e famiglie richiede documenti, allegazioni e verifiche specifiche prima della redazione dell'atto.",
                    reliability_score=85,
                ),
            ],
        )
    if prefix in {"120", "129"}:
        return (
            "successioni_volontaria_giurisdizione",
            [
                _cpc_reference(
                    source_id="cpc_art_747",
                    article="747",
                    title="art. 747",
                    evidence_kind="volontaria_giurisdizione_successioni",
                    principle="Le pratiche successorie di volontaria giurisdizione richiedono controllo su autorizzazioni, documenti ereditari e competenza.",
                    reliability_score=75,
                ),
                _cpc_reference(
                    source_id="cpc_art_749",
                    article="749",
                    title="art. 749",
                    evidence_kind="provvedimenti_successori",
                    principle="Gli adempimenti successori vanno mantenuti in review quando incidono su autorizzazioni o gestione di beni ereditari.",
                    reliability_score=75,
                ),
            ],
        )
    if prefix == "130":
        if "possess" in label:
            family_name = "diritti_reali_possesso_trascrizioni"
        else:
            family_name = "diritti_reali_trascrizioni"
        return (
            family_name,
            [
                _cpc_reference(
                    source_id="cpc_art_703_diritti_reali",
                    article="703",
                    title="art. 703",
                    evidence_kind="possesso_diritti_reali",
                    principle="Le pratiche su diritti reali e possesso devono distinguere tutela possessoria, tutela petitoria e adempimenti di pubblicità.",
                    reliability_score=80,
                ),
            ]
            + _ordinary_civil_introductory_references(),
        )
    if prefix == "201":
        return (
            "revocazione",
            [
                _cpc_reference(
                    source_id="cpc_art_395",
                    article="395",
                    title="art. 395",
                    evidence_kind="revocazione_sentenza",
                    principle="La revocazione richiede qualificazione tassativa del motivo, controllo del provvedimento e verifica dei termini.",
                    reliability_score=90,
                )
            ],
        )
    if prefix == "210":
        return (
            "lavoro_ingiunzione",
            [
                _cpc_reference(
                    source_id="cpc_art_633_lavoro",
                    article="633",
                    title="art. 633",
                    evidence_kind="ingiunzione_lavoro",
                    principle="Il procedimento monitorio in area lavoro va verificato su presupposti, prova scritta e rito competente.",
                    reliability_score=85,
                ),
                _cpc_reference(
                    source_id="cpc_art_409_lavoro_monitorio",
                    article="409",
                    title="art. 409",
                    evidence_kind="materie_lavoro",
                    principle="La materia va qualificata rispetto al perimetro delle controversie di lavoro prima di generare atto o mapping.",
                    reliability_score=85,
                ),
            ],
        )
    if prefix == "211":
        return (
            "lavoro_cautelare",
            [
                _cpc_reference(
                    source_id="cpc_art_669bis_lavoro",
                    article="669bis",
                    title="art. 669-bis",
                    evidence_kind="cautelare_lavoro",
                    principle="Il cautelare in area lavoro richiede controllo dei presupposti cautelari e del collegamento con la controversia di lavoro.",
                    reliability_score=85,
                ),
                _cpc_reference(
                    source_id="cpc_art_409_lavoro_cautelare",
                    article="409",
                    title="art. 409",
                    evidence_kind="materie_lavoro",
                    principle="La qualificazione della materia lavoro deve precedere la scelta del rito e degli adempimenti cautelari.",
                    reliability_score=85,
                ),
            ],
        )
    if prefix in {"220", "221", "222", "223"}:
        return (
            "lavoro_previdenza",
            [
                _cpc_reference(
                    source_id="cpc_art_409",
                    article="409",
                    title="art. 409",
                    evidence_kind="controversie_lavoro",
                    principle="La pratica va qualificata rispetto alle controversie di lavoro e ai rapporti rientranti nel rito speciale.",
                    reliability_score=90,
                ),
                _cpc_reference(
                    source_id="cpc_art_414",
                    article="414",
                    title="art. 414",
                    evidence_kind="ricorso_lavoro",
                    principle="Il ricorso in materia di lavoro richiede controllo puntuale di fatti, domande, mezzi di prova e documenti allegati.",
                    reliability_score=90,
                ),
            ],
        )
    return (
        "pct_generico",
        _ordinary_civil_introductory_references()
        + [
            _cpc_reference(
                source_id="cpc_codice_procedura_civile",
                article="125",
                title="art. 125",
                evidence_kind="inquadramento_generale",
                principle="La procedura non è ancora mappata in modo specialistico: serve review su rito, atto e adempimenti.",
                reliability_score=75,
            )
        ],
    )


def _dedupe_references(references: list[SourceReference]) -> list[SourceReference]:
    seen: set[str] = set()
    deduped: list[SourceReference] = []
    for reference in references:
        key = f"{reference.source_id}|{reference.source_url}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reference)
    return deduped


def build_source_plan_for_xsd(
    xsd_object: dict[str, Any],
    procedure_code: str | None = None,
) -> SourceResearchPlan:
    candidate = infer_mapping_for_xsd(xsd_object)
    effective_procedure = procedure_code or candidate.procedure_code
    family, family_refs = _family_references(xsd_object)
    references = _dedupe_references(_base_references() + _general_cpc_references() + family_refs)
    return SourceResearchPlan(
        xsd_code=str(xsd_object.get("xsd_code") or ""),
        xsd_label=str(xsd_object.get("xsd_label") or ""),
        xsd_family_label=str(xsd_object.get("xsd_family_label") or ""),
        xsd_area_label=str(xsd_object.get("xsd_area_label") or ""),
        procedure_code=effective_procedure,
        family=family,
        references=references,
        review_required=True,
    )


def consult_sources_for_xsd(
    repo: ProcedureLifecycleRepository,
    xsd_code: str,
    *,
    procedure_code: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    repo.ensure_extended_schema()
    xsd_object = repo.get_xsd_object(xsd_code)
    if not xsd_object:
        raise ValueError("Codice XSD non presente nel catalogo importato.")
    plan = build_source_plan_for_xsd(xsd_object, procedure_code)
    if dry_run:
        return {"plan": plan.to_dict(), "source_evidence_created": 0, "card_id": None}

    created = 0
    for reference in plan.references:
        add_source_evidence(repo, **reference.to_evidence(plan.procedure_code, plan.xsd_code))
        created += 1
    sources = repo.list_source_evidence(plan.procedure_code, plan.xsd_code)
    card_id = save_knowledge_card(
        repo,
        procedure_code=plan.procedure_code,
        xsd_code=plan.xsd_code,
        title=f"Scheda conoscitiva {xsd_object.get('xsd_label') or plan.xsd_code}",
        sources=sources,
        risk_level="HIGH" if _prefix(plan.xsd_code) == "050" else "MEDIUM",
    )
    return {"plan": plan.to_dict(), "source_evidence_created": created, "card_id": card_id}


def seed_multi_source_evidence_for_inventory(
    repo: ProcedureLifecycleRepository,
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> SourceResearchReport:
    repo.ensure_extended_schema()
    xsd_objects = repo.list_xsd_objects(active_only=True)
    if limit is not None:
        xsd_objects = xsd_objects[: max(0, int(limit))]
    evidence_created = 0
    cards_created = 0
    for xsd_object in xsd_objects:
        result = consult_sources_for_xsd(repo, str(xsd_object["xsd_code"]), dry_run=dry_run)
        evidence_created += int(result.get("source_evidence_created") or 0)
        cards_created += 1 if result.get("card_id") else 0
    return SourceResearchReport(
        dry_run=dry_run,
        xsd_total=len(xsd_objects),
        source_evidence_created=evidence_created,
        cards_created=cards_created,
        review_required=len(xsd_objects),
    )
