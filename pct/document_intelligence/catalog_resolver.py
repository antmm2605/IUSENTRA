"""Resolver deterministico per la catalogazione documentale del fascicolo.

Il resolver non naviga in rete e non deduce una materia da prefissi storici:
usa il profilo semantico del fascicolo, metadati del canale e testo già estratto
nel repository SQL. Quando mancano prove sufficienti apre una revisione.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable

from pct.fascicoli import TipoDocumento
from pct.fascicolo_document_catalog import DocumentCatalogClassification, classify_fascicolo_document
from pct.presidio_processuale_ruleset import presidio_rule_hits
from pct.template_atti_legal_sources import REGISTRY_VERSION, TEMPLATE_ATTI_LEGAL_SOURCES

from .models import (
    DocumentCatalogCandidate,
    DocumentCatalogEvidence,
    DocumentCatalogReview,
    new_id,
    utc_now,
)


# Incrementato quando cambia l'evidenza persistita: il refresh deve sostituire
# le prove automatiche precedenti senza toccare le correzioni manuali.
RESOLVER_VERSION = "2026.08.25.catalogo-fascicolo.v14"

# Triadi versionate nell'audit del 24/08/2026. I riferimenti ``snapshot:`` e
# ``browser:`` sono prove archiviate/manuali, mai chiamate HTTP dal runtime.
PROFILE_SOURCES: dict[str, tuple[str, ...]] = {
    "CIV-PCT": ("normattiva_codice_civile", "normattiva_cpc", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "CIV-MON-CAU": ("normattiva_cpc", "cpc_procedimento_monitorio", "cpc_procedimenti_cautelari_uniformi", "pst_specifiche_tecniche_pct"),
    "CIV-ESE": ("normattiva_cpc", "pst_specifiche_tecniche_pct", "pst_portale_vendite_pubbliche_specifiche_concorsuali", "corte_cassazione_sentenzeweb"),
    "CIV-IMP": ("normattiva_cpc", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "CIV-NOT": ("normattiva_legge_53_1994_notifiche", "normattiva_dpr_68_2005_pec", "pst_dgsia_2024_art_27_attestazione_conformita", "normattiva_cad_art_48"),
    "CIV-PROC": ("normattiva_cpc", "normattiva_l_247_2012_ordinamento_forense", "cnf_codice_deontologico_forense", "pst_specifiche_tecniche_pct"),
    "CIV-GDP": ("normattiva_cpc", "normattiva_d_lgs_150_2011_riti", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "LOC": ("normattiva_legge_392_1978_locazioni", "normattiva_legge_431_1998_locazioni_abitative", "agenzia_entrate_rli_locazioni"),
    "RCD": ("normattiva_codice_civile", "normattiva_cpc", "normattiva_codice_strada_285_1992", "normattiva_codice_assicurazioni_209_2005", "normattiva_dl_132_2014_negoziazione"),
    "ADR": ("normattiva_d_lgs_28_2010_mediazione", "normattiva_dm_150_2023_mediazione", "giustizia_registro_mediazione_dm_150_2023", "normattiva_dl_132_2014_negoziazione"),
    "PAT": ("normattiva_cpa", "giustizia_amministrativa_pat", "giustizia_amministrativa_dpcs_2025_pat", "giustizia_amministrativa_ricerche_decisioni"),
    "CONC": ("normattiva_codice_crisi_14_2019", "normattiva_d_lgs_136_2024_correttivo_crisi", "pst_portale_vendite_pubbliche_specifiche_concorsuali", "snapshot:pvp-specifiche-2024-v1.2"),
    "BAN": ("normattiva_tub_385_1993", "abf_normativa", "bancaditalia_abf_disposizioni_2025", "browser:acf-normativa-2026"),
    "SOC": ("normattiva_codice_civile", "normattiva_tuf_58_1998", "snapshot:registro-imprese-bilanci-2026", "snapshot:registro-imprese-specifiche-2026"),
    "LAV": ("normattiva_l_300_1970_statuto_lavoratori", "normattiva_l_604_1966_licenziamenti", "inl_contestazione_licenziamento_gmo", "snapshot:inps-ricorso-previdenziale-2026"),
    "VGS": ("normattiva_codice_civile", "normattiva_cpc", "snapshot:vg-dm-2024", "snapshot:vg-specifiche-2023", "snapshot:successione-certificato-giustizia-2026"),
    "FAM": ("normattiva_codice_civile", "normattiva_cpc", "normattiva_d_lgs_149_2022_cartabia_civile", "corte_cassazione_sentenzeweb"),
    "PEN": ("normattiva_cpp", "normattiva_d_lgs_150_2022_cartabia_penale", "pst_pdp_penale", "pst_specifiche_penale_2024", "corte_cassazione_sentenzeweb"),
    "TRIB": ("normattiva_d_lgs_546_1992_tributario", "normattiva_dm_163_2013_ptt", "snapshot:ptt-specifiche-2015-gu", "snapshot:ptt-modifica-2017-gu", "snapshot:ptt-modifica-2023-gu", "snapshot:ptt-circolare-2019", "giustizia_tributaria_def_giurisprudenza"),
    "STD": ("normattiva_l_247_2012_ordinamento_forense", "cnf_codice_deontologico_forense", "normattiva_dm_55_2014_parametri_forensi", "snapshot:agid-gestione-documentale-2026"),
    "IPD": ("normattiva_cpi_30_2005", "uibm_deposito_telematico_proprieta_industriale", "normattiva_diritto_autore_633_1941", "snapshot:uibm-marchi-disegni-2026"),
    "IMM": ("normattiva_tu_immigrazione_286_1998", "normattiva_d_lgs_25_2008_protezione_internazionale", "interno_protezione_internazionale_commissioni", "snapshot:protezione-internazionale-guida-2024"),
    "PRI": ("normattiva_privacy_196_2003", "garante_gdpr", "snapshot:garante-privacy-regolamento-reclami-2019"),
    "STR": ("normattiva_codice_civile", "normattiva_d_lgs_28_2010_mediazione", "normattiva_dm_150_2023_mediazione", "cnf_codice_deontologico_forense"),
    "CON": ("normattiva_codice_consumo_206_2005", "agcom_conciliaweb", "agcom_delibera_203_18_conciliaweb", "snapshot:arera-tico-209-2016"),
}

# Le 47 righe sono la mappa completa area/branca/sottofamiglia del corpus
# effettivo da 708 modelli. Il confronto è semantico normalizzato ed esatto.
FAMILY_PROFILE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("ADR", "ADR, mediazione, negoziazione, arbitrato", "Mediazione e arbitrato", "ADR"),
    ("Amministrativo", "Amministrativo", "Ricorsi, memorie e cautelare", "PAT"),
    ("Amministrativo", "Giustizia amministrativa", "Ricorsi e appelli", "PAT"),
    ("Civile", "Civile ordinario", "Introduttivi e difensivi", "CIV-PCT"),
    ("Civile", "Civile ordinario", "Introduttivi, difensivi e istanze", "CIV-PCT"),
    ("Civile", "Esecuzioni", "Precetti, pignoramenti e opposizioni", "CIV-ESE"),
    ("Civile", "Esecuzioni civili", "Espropriazione e opposizioni", "CIV-ESE"),
    ("Civile", "Impugnazioni", "Appello, cassazione e rimedi", "CIV-IMP"),
    ("Civile", "Impugnazioni civili", "Appelli, reclami e rimedi impugnatori", "CIV-IMP"),
    ("Civile", "Monitorio e cautelare", "Ricorsi d'urgenza, monitori e sfratti", "CIV-MON-CAU"),
    ("Civile", "Monitorio, cautelare e possessorio", "Ricorsi speciali", "CIV-MON-CAU"),
    ("Civile", "Notifiche e adempimenti", "UNEP, notifica in proprio e allegati", "CIV-NOT"),
    ("Civile", "Procure e deleghe", "Mandati e domiciliazioni", "CIV-PROC"),
    ("Civile", "UNEP e notificazioni", "Notifiche, depositi e fascicolo telematico", "CIV-NOT"),
    ("Crisi d'impresa e insolvenza", "Procedure concorsuali e crisi", "Concorsuale", "CONC"),
    ("Diritto amministrativo", "Amministrativo", "PAT e contenzioso amministrativo", "PAT"),
    ("Diritto bancario", "Bancario e finanziario", "Bancario e finanziario", "BAN"),
    ("Diritto civile", "Core civile", "Contenzioso ordinario", "CIV-PCT"),
    ("Diritto civile", "Giudice di Pace", "Giudice di Pace", "CIV-GDP"),
    ("Diritto civile", "Locazioni, condominio e immobili", "Locazioni, condominio e immobili", "LOC"),
    ("Diritto civile", "Procedimento monitorio", "Procedimento monitorio", "CIV-MON-CAU"),
    ("Diritto civile", "Recupero crediti e stragiudiziale", "Recupero crediti e diffide", "STR"),
    ("Diritto civile", "Responsabilità civile e danni", "Responsabilità civile", "RCD"),
    ("Diritto commerciale", "Commerciale e societario", "Societario", "SOC"),
    ("Diritto del lavoro", "Lavoro e previdenza", "Lavoro e previdenza", "LAV"),
    ("Diritto delle persone e successioni", "Volontaria giurisdizione e successioni", "Volontaria giurisdizione", "VGS"),
    ("Diritto di famiglia", "Famiglia, minori e persone", "Famiglia e minori", "FAM"),
    ("Diritto penale", "Penale", "Difesa penale e persona offesa", "PEN"),
    ("Diritto processuale civile", "Cautelari e urgenza", "Cautelari e urgenza", "CIV-MON-CAU"),
    ("Diritto processuale civile", "Esecuzioni", "Esecuzioni", "CIV-ESE"),
    ("Diritto tributario", "Tributario", "Contenzioso tributario", "TRIB"),
    ("Famiglia e Persone", "Famiglia e persone", "Separazione, divorzio e volontaria giurisdizione", "FAM"),
    ("Famiglia e Persone", "Famiglia, persone e volontaria giurisdizione", "Separazione, divorzio e tutele", "FAM"),
    ("Gestione studio", "Atti interni di studio", "Operatività interna", "STD"),
    ("IP, media e digitale", "Proprietà intellettuale e digitale", "Proprietà intellettuale e web", "IPD"),
    ("Immigrazione", "Immigrazione e cittadinanza", "Ricorsi, permessi e protezione", "IMM"),
    ("Lavoro e Previdenza", "Lavoro e previdenza", "Ricorsi e impugnazioni", "LAV"),
    ("Lavoro e Previdenza", "Lavoro e previdenza", "Ricorsi, memorie e previdenza", "LAV"),
    ("Penale", "Difesa penale", "Atti difensivi e richieste", "PEN"),
    ("Penale", "Penale", "Difesa, istanze e impugnazioni", "PEN"),
    ("Privacy e protezione dati", "Privacy e compliance", "GDPR e compliance", "PRI"),
    ("Societario", "Societario", "Pareri, contratti e contenzioso", "SOC"),
    ("Stragiudiziale", "Diffide e atti stragiudiziali", "Richieste, intimazioni e lettere", "STR"),
    ("Stragiudiziale", "Stragiudiziale", "Comunicazioni, accordi e pareri", "STR"),
    ("Tributario", "Contenzioso tributario", "Ricorso e difese", "TRIB"),
    ("Tributario", "Tributario", "Ricorsi, controdeduzioni e appelli", "TRIB"),
    ("Tutela del consumatore", "Consumatori e utenze", "Consumo e utenze", "CON"),
)


def _normalise(value: Any) -> str:
    raw = unicodedata.normalize("NFD", str(value or "").casefold())
    raw = "".join(char for char in raw if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


FAMILY_PROFILE_BY_CONTEXT = {
    (_normalise(area), _normalise(branch), _normalise(subfamily)): profile
    for area, branch, subfamily, profile in FAMILY_PROFILE_ROWS
}
# I profili inferiti dal corpus non alterano la matrice dei modelli: la
# matrice resta il contratto completo delle 47 famiglie, mentre queste sono
# sottofamiglie documentali più specifiche, usate solo dopo due evidenze
# indipendenti nel fascicolo e mai al posto di dati strutturati dell'avvocato.
INFERRED_PROFILE_CONTEXT_ALIASES = {
    (
        _normalise("Diritto civile"),
        _normalise("Responsabilità civile e danni"),
        _normalise("Risarcimento danni da circolazione stradale"),
    ): "RCD",
}
_SOURCE_INDEX = {str(row.get("id") or ""): dict(row) for row in TEMPLATE_ATTI_LEGAL_SOURCES}


@dataclass(slots=True)
class CatalogResolution:
    profile_id: str | None
    legal_area: str
    legal_branch: str
    legal_subfamily: str
    jurisdiction: str
    rite: str
    proceeding_phase: str
    document_nature: str
    document_label: str
    document_section: str
    deposit_role: str
    deposit_candidate: bool
    confidence: int
    status: str
    source_state: str
    reason: str
    candidates: list[DocumentCatalogCandidate]
    evidence: list[DocumentCatalogEvidence]
    review: DocumentCatalogReview | None


@dataclass(frozen=True, slots=True)
class ContentIdentity:
    """Identità forte ricavata dal documento, distinta dal presidio.

    L'estratto è deliberatamente breve: serve a rendere comprensibile la
    proposta nell'interfaccia, mentre il contenuto completo resta nel lettore
    interno tenant-aware.
    """

    classification: DocumentCatalogClassification
    excerpt: str


def _unindexed_content_classification(current: DocumentCatalogClassification) -> DocumentCatalogClassification:
    """Non attribuisce natura o deposito dal solo nome del file.

    Il tipo storico resta consultabile, ma senza testo SQL il documento deve
    passare dalla revisione: il nome è un metadato, non una prova di contenuto.
    """

    return DocumentCatalogClassification(
        role="da_verificare",
        label="Contenuto da indicizzare",
        section="da-verificare",
        confidence=0,
        evidence="contenuto non disponibile nel repository SQL; il nome del file non è usato per catalogare",
        tipo_documento=current.tipo_documento,
        deposit_role="allegato",
        deposit_candidate=False,
    )


def _insufficient_content_classification(current: DocumentCatalogClassification) -> DocumentCatalogClassification:
    """Conserva il testo indicizzato, ma non trasforma il nome in una prova.

    Un PDF può contenere intestazione dell'ufficio o formule comuni senza
    rivelare la propria natura processuale. In quel caso la classificazione
    originata dal solo nome file non è un esito automatico utilizzabile né
    può renderlo candidato alla busta.
    """

    return DocumentCatalogClassification(
        role="da_verificare",
        label="Contenuto da verificare",
        section="da-verificare",
        confidence=50,
        evidence="testo indicizzato privo di riferimenti sufficienti; il nome del file non è usato per catalogare",
        tipo_documento=current.tipo_documento,
        deposit_role="fuori_busta",
        deposit_candidate=False,
    )


def _procedural_only_content_classification(current: DocumentCatalogClassification) -> DocumentCatalogClassification:
    """Blocca l'equivoco fra un presidio rilevato e il tipo del file.

    Il ruleset processuale può leggere una CTU, un rinvio o un riferimento a
    un rito nel corpo di qualsiasi atto. Senza una formula che identifichi il
    documento, quel segnale diventa una prova separata e il catalogo apre una
    revisione: non è lecito promuoverlo a natura documentale.
    """

    return DocumentCatalogClassification(
        role="da_verificare",
        label="Contenuto da verificare",
        section="da-verificare",
        confidence=50,
        evidence=(
            "segnalazione processuale rilevata nel testo, ma senza una formula "
            "identificativa del documento; è richiesta verifica"
        ),
        tipo_documento=current.tipo_documento,
        deposit_role="fuori_busta",
        deposit_candidate=False,
    )


def _content_excerpt(text: str, pattern: str) -> str:
    """Restituisce una prova breve, leggibile e minimizzata del contenuto."""

    compact = re.sub(r"\s+", " ", str(text or "").replace("\ufffd", "")).strip()
    if not compact:
        return "Contenuto indicizzato disponibile nel repository SQL."
    match = re.search(pattern, compact, flags=re.IGNORECASE)
    if match is None:
        return "Formula identificativa non disponibile nell'estratto indicizzato."
    # La prova visibile deve essere sufficiente a spiegare l'inferenza ma non
    # replicare un brano dell'atto: la fonte completa resta apribile nel nostro
    # lettore, mentre qui esponiamo solo la formula classificante. In questo
    # modo non anticipiamo nominativi, codici fiscali, indirizzi o altri dati
    # personali presenti nelle righe successive dell'OCR.
    formula = re.sub(r"\s+", " ", match.group(0)).strip(" .;:-")
    return f"Formula rilevata nel testo indicizzato: {formula}."


def _content_identity(
    extracted_text: str,
) -> ContentIdentity | None:
    """Riconosce solo identità documentali espresse dal singolo contenuto.

    Le regole di presidio possono indicare una scadenza, un rito o un richiamo
    alla CTU. Non sono, però, una prova dell'identità del file: una memoria che
    cita una CTU resta una memoria e una sentenza che liquida spese resta una
    sentenza. Questo strato precede l'adattatore storico, senza modificarne i
    comportamenti nelle altre superfici applicative.
    """

    raw = str(extracted_text or "").strip()
    if not raw:
        return None
    head = _normalise(raw[:12000])

    def result(
        *,
        role: str,
        label: str,
        section: str,
        confidence: int,
        evidence: str,
        tipo_documento: TipoDocumento,
        deposit_role: str,
        deposit_candidate: bool,
        excerpt_pattern: str,
    ) -> ContentIdentity:
        return ContentIdentity(
            classification=DocumentCatalogClassification(
                role=role,
                label=label,
                section=section,
                confidence=confidence,
                evidence=evidence,
                tipo_documento=tipo_documento,
                deposit_role=deposit_role,
                deposit_candidate=deposit_candidate,
            ),
            excerpt=_content_excerpt(raw, excerpt_pattern),
        )

    # Il dispositivo della sentenza è prova più forte di qualunque riferimento
    # economico o tecnico contenuto nella motivazione.
    if "in nome del popolo italiano" in head and re.search(r"\bsentenza\b", head):
        return result(
            role="provvedimento",
            label="Sentenza",
            section="provvedimenti",
            confidence=99,
            evidence="testo iniziale: dispositivo di sentenza",
            tipo_documento=TipoDocumento.SENTENZA,
            deposit_role="allegato",
            deposit_candidate=True,
            excerpt_pattern=r"\bin\s+nome\s+del\s+popolo\s+italiano\b|\bsentenza\b",
        )

    # L'intestazione identifica il provvedimento dell'ufficio; i richiami a
    # CTU, note scritte o termini nel dispositivo restano segnali separati.
    if re.search(r"\bdecreto\s+di\s+fissazione\s+(?:dell(?:['\u2019]|\s+)?)?udienza\b", head):
        return result(
            role="provvedimento",
            label="Decreto di fissazione udienza",
            section="provvedimenti",
            confidence=98,
            evidence="testo iniziale: decreto di fissazione udienza",
            tipo_documento=TipoDocumento.DECRETO,
            deposit_role="fuori_busta",
            deposit_candidate=False,
            excerpt_pattern=r"\bdecreto\s+di\s+fissazione\s+(?:dell(?:['\u2019]|\s+)?)?udienza\b",
        )

    if re.search(r"\bmemoria\s+(?:conclusion\w*|conclusiv\w*)\b", head):
        return result(
            role="atto_difensivo",
            label="Memoria conclusionale",
            section="atti",
            confidence=98,
            evidence="testo iniziale: memoria conclusionale",
            tipo_documento=TipoDocumento.MEMORIA,
            deposit_role="atto_principale",
            deposit_candidate=True,
            excerpt_pattern=r"\bmemoria\s+(?:conclusion\w*|conclusiv\w*)\b",
        )

    # Nei modelli giudiziari è comune anche la formulazione «note per la
    # trattazione scritta». La particella non può far ricadere l'atto nelle
    # sole segnalazioni CTU eventualmente richiamate nel merito.
    if re.search(r"\bnote\s+(?:di\s+|per\s+(?:la\s+)?)?trattazione\s+scritt\w*\b", head):
        return result(
            role="atto_difensivo",
            label="Note di trattazione scritta",
            section="atti",
            confidence=97,
            evidence="testo iniziale: note di trattazione scritta",
            tipo_documento=TipoDocumento.MEMORIA,
            deposit_role="atto_principale",
            deposit_candidate=True,
            excerpt_pattern=r"\bnote\s+(?:di\s+|per\s+(?:la\s+)?)?trattazione\s+scritt\w*\b",
        )

    # L'OCR restituisce spesso l'intestazione al plurale ("conclusionali")
    # oppure un refuso di scansione ("cocnlusive"). La seconda formula
    # ricorre anche nel corpo delle note: entrambe sono prove del documento,
    # non del presidio CTU che può esservi richiamato.
    if re.search(r"\bnote\s+(?:conclusiv\w*|conclusional\w*|cocnlusiv\w*)\b", head):
        return result(
            role="atto_difensivo",
            label="Note conclusionali",
            section="atti",
            confidence=96,
            evidence="testo iniziale: note conclusionali",
            tipo_documento=TipoDocumento.MEMORIA,
            deposit_role="atto_principale",
            deposit_candidate=True,
            excerpt_pattern=r"\bnote\s+(?:conclusiv\w*|conclusional\w*|cocnlusiv\w*)\b",
        )

    # Le istanze di sostituzione dell'udienza e le note di deposito sono atti
    # autonomi: la menzione di CTU, CTP o di una scadenza nel loro corpo non
    # ne altera l'identità documentale.
    if re.search(
        r"\bistanza\s+per\s+la\s+sostituzione\s+dell(?:['\u2019]|\s+)?udienza\b|"
        r"\brichiesta\s+sostituzione\s+dell(?:['\u2019]|\s+)?udienza\b",
        head,
    ):
        return result(
            role="atto_difensivo",
            label="Istanza di trattazione scritta",
            section="atti",
            confidence=97,
            evidence="testo iniziale: istanza di sostituzione dell'udienza con note scritte",
            tipo_documento=TipoDocumento.ATTO_GIUDIZIARIO,
            deposit_role="atto_principale",
            deposit_candidate=True,
            excerpt_pattern=(
                r"\bistanza\s+per\s+la\s+sostituzione\s+dell(?:['\u2019]|\s+)?udienza\b|"
                r"\brichiesta\s+sostituzione\s+dell(?:['\u2019]|\s+)?udienza\b"
            ),
        )

    if re.search(r"\bnota\s+di\s+deposito\b", head):
        return result(
            role="deposito",
            label="Nota di deposito",
            section="atti",
            confidence=97,
            evidence="testo iniziale: nota di deposito",
            tipo_documento=TipoDocumento.DEPOSITO_PCT,
            deposit_role="fuori_busta",
            deposit_candidate=False,
            excerpt_pattern=r"\bnota\s+di\s+deposito\b",
        )

    if re.search(r"\bistanze\s+e\s+conclusioni\b", head):
        return result(
            role="atto_difensivo",
            label="Istanze e conclusioni",
            section="atti",
            confidence=92,
            evidence="testo iniziale: istanze e conclusioni",
            tipo_documento=TipoDocumento.ATTO_GIUDIZIARIO,
            deposit_role="atto_principale",
            deposit_candidate=True,
            excerpt_pattern=r"\bistanze\s+e\s+conclusioni\b",
        )

    if re.search(r"\bnotificazion[ei]\s+di\s+cancelleria\b|\bcomunicazione\s+di\s+cancelleria\b", head):
        return result(
            role="comunicazione",
            label="Comunicazione di cancelleria",
            section="comunicazioni",
            confidence=97,
            evidence="testo iniziale: notificazione/comunicazione di cancelleria",
            tipo_documento=TipoDocumento.COMUNICAZIONE,
            deposit_role="fuori_busta",
            deposit_candidate=False,
            excerpt_pattern=r"\b(?:notificazion[ei]|comunicazione)\s+di\s+cancelleria\b",
        )

    if (
        re.search(r"\baccett\w*\s+(?:l\s+)?incarico\b", head)
        and re.search(r"\bgiur\w*\b", head)
        and re.search(r"\b(?:ctu|consulente\s+tecnico)\b", head)
    ):
        return result(
            role="atto_ufficio",
            label="Accettazione incarico e giuramento CTU",
            section="allegati",
            confidence=96,
            evidence="testo iniziale: accettazione incarico e giuramento del CTU",
            tipo_documento=TipoDocumento.ALLEGATO,
            deposit_role="fuori_busta",
            deposit_candidate=False,
            excerpt_pattern=r"\baccett\w*\s+(?:l\s+)?incarico\b|\bgiur\w*\b",
        )

    if re.search(r"\b(?:bozza\s+di\s+)?perizia\s+tecnic\w*\b", head) and re.search(r"\b(?:ctu|consulenza\s+tecnica)\b", head):
        return result(
            role="relazione_peritale_ctu",
            label="Bozza di perizia tecnica CTU" if "bozza" in head else "Perizia tecnica CTU",
            section="allegati",
            confidence=95,
            evidence="testo iniziale: perizia tecnica CTU",
            tipo_documento=TipoDocumento.ALLEGATO,
            deposit_role="allegato",
            deposit_candidate=True,
            excerpt_pattern=r"\b(?:bozza\s+di\s+)?perizia\s+tecnic\w*\b",
        )

    if re.search(r"\bverbale\b", head) and re.search(r"\budienza\b", head):
        return result(
            role="verbale_ufficio",
            label="Verbale d'udienza",
            section="provvedimenti",
            confidence=94,
            evidence="testo iniziale: verbale d'udienza",
            tipo_documento=TipoDocumento.VERBALE,
            deposit_role="fuori_busta",
            deposit_candidate=False,
            excerpt_pattern=r"\bverbale\b",
        )

    return None


def _procedural_signal_evidence(extracted_text: str) -> list[DocumentCatalogEvidence]:
    """Traduce il presidio in segnali separati, senza alterare l'identità."""

    evidence: list[DocumentCatalogEvidence] = []
    seen: set[str] = set()
    for hit in presidio_rule_hits(extracted_text):
        code = str(hit.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        legal_basis = [str(item) for item in list(hit.get("legalBasis") or []) if str(item).strip()]
        detail = str(hit.get("label") or "Segnalazione processuale").strip()
        if legal_basis:
            detail = f"{detail}. Riferimento: {', '.join(legal_basis[:3])}"
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id="", fascicolo_id="", assignment_id="",
            evidence_type="procedural_signal", locator=code, excerpt=detail[:240], weight=30,
            content_sha256=None, created_at="",
        ))
        if len(evidence) == 6:
            break
    return evidence


def _classify_indexed_content(extracted_text: str) -> DocumentCatalogClassification:
    """Esegue la classificazione senza nome, tipo o metadati del portale.

    Il catalogo SQL deve dimostrare che la proposta deriva dal testo estratto:
    questo oggetto vuoto impedisce al classificatore storico di usare
    accidentalmente file name, tipo dichiarato o altri metadati come prova.
    """

    identity = _content_identity(extracted_text)
    if identity is not None:
        return identity.classification
    return classify_fascicolo_document(
        SimpleNamespace(
            nome="", nome_originale="", nome_portale="", percorso="", tipo="",
            classificazione_portale="", tipo_atto_portale="", servizio_portale="",
            mittente_portale="", note="", tags=[],
        ),
        filename="",
        extracted_text=extracted_text,
        tipo="",
    )


def profile_source_rows(profile_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id in PROFILE_SOURCES.get(profile_id, ()):
        if source_id.startswith("snapshot:"):
            rows.append({
                "id": source_id,
                "official_url": source_id,
                "verification_status": "snapshot ufficiale acquisito e verificato",
                "last_verified_at": "2026-08-24",
                "snapshot_sha256": "",
                "source_type": "snapshot",
                "label": "Snapshot ufficiale versionato",
            })
        elif source_id.startswith("browser:"):
            rows.append({
                "id": source_id,
                "official_url": "https://www.acf.consob.it/normativa/normativa-acf/-/asset_publisher/3ZtmdCgqd1re/content/aggiornamento-area-riservata?inheritRedirect=false",
                "verification_status": "evidenza browser istituzionale verificata il 24/08/2026",
                "last_verified_at": "2026-08-24",
                "snapshot_sha256": "",
                "source_type": "browser_evidence",
                "label": "Evidenza istituzionale ACF Consob",
            })
        else:
            source = _SOURCE_INDEX.get(source_id, {})
            source_label = " — ".join(
                item for item in (
                    str(source.get("title") or "").strip(),
                    str(source.get("source_title") or "").strip(),
                    str(source.get("article") or "").strip(),
                )
                if item
            )
            rows.append({
                "id": source_id,
                "official_url": str(source.get("official_url") or ""),
                "verification_status": str(source.get("verification_status") or "fonte da verificare"),
                "last_verified_at": str(source.get("last_verified_at") or ""),
                "snapshot_sha256": "",
                "source_type": str(source.get("source_type") or "normativa"),
                "label": source_label or "Fonte normativa ufficiale",
            })
    return rows


def resolve_profile(context: dict[str, Any]) -> tuple[str | None, str]:
    area = str(context.get("area") or context.get("area_pratica") or "")
    branch = str(context.get("branca") or context.get("branch") or "")
    subfamily = str(context.get("sottobranca") or context.get("subfamily") or "")
    exact = FAMILY_PROFILE_BY_CONTEXT.get((_normalise(area), _normalise(branch), _normalise(subfamily)))
    if exact:
        reason = str(context.get("_profile_inference_reason") or "").strip()
        return exact, reason or "profilo del fascicolo corrisponde alla matrice area/branca/sottofamiglia"

    inferred = INFERRED_PROFILE_CONTEXT_ALIASES.get((_normalise(area), _normalise(branch), _normalise(subfamily)))
    if inferred:
        reason = str(context.get("_profile_inference_reason") or "").strip()
        return inferred, reason or "sottofamiglia documentale verificabile del fascicolo"

    channel = _normalise(context.get("canale") or context.get("canale_operativo") or context.get("source"))
    if channel in {"pat", "siga"}:
        return "PAT", "canale amministrativo del fascicolo"
    if channel in {"ptt", "sigit"}:
        return "TRIB", "canale tributario del fascicolo"
    if channel in {"pdp", "ppt", "penale"}:
        return "PEN", "canale penale del fascicolo"
    return None, "mancano area, branca e sottofamiglia verificabili del fascicolo"


def infer_fascicolo_context_from_document_corpus(
    context: dict[str, Any] | None,
    documents: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Integra un profilo assente soltanto quando il corpus è concordante.

    L'inferenza non legge file o nomi locali: riceve esclusivamente il testo
    già estratto nel repository SQL per i documenti esplicitamente associati
    al fascicolo. Non sovrascrive mai area, branca o sottofamiglia compilate.
    """

    inferred = dict(context or {})
    profile_id, _ = resolve_profile(inferred)
    if profile_id:
        return inferred
    structured_values = (
        inferred.get("area") or inferred.get("area_pratica"),
        inferred.get("branca") or inferred.get("branch"),
        inferred.get("sottobranca") or inferred.get("subfamily"),
    )
    if any(str(value or "").strip() for value in structured_values):
        return inferred

    matches: list[tuple[str, str]] = []
    seen_documents: set[str] = set()
    for position, document in enumerate(documents, start=1):
        text = _normalise(document.get("text"))
        if not text:
            continue
        has_damage_claim = bool(re.search(r"\brisarcimento (?:dei )?danni?\b", text))
        has_road_claim = bool(
            re.search(
                r"\b(sinistro stradale|circolazione stradale|rc auto|responsabilita civile auto)\b",
                text,
            )
        )
        if not (has_damage_claim and has_road_claim):
            continue
        document_id = str(document.get("document_id") or document.get("id") or "").strip()
        filename = str(document.get("filename") or document.get("name") or "Documento indicizzato").strip()
        dedupe_key = document_id or f"{filename}:{position}"
        if dedupe_key in seen_documents:
            continue
        seen_documents.add(dedupe_key)
        matches.append((document_id, filename))

    # Un solo documento può essere mal classficato o estratto in modo
    # incompleto: la materia viene proposta solo con conferma indipendente.
    if len(matches) < 2:
        return inferred

    evidence_names = [filename for _, filename in matches[:5]]
    inferred.update({
        "area": "Diritto civile",
        "branca": "Responsabilità civile e danni",
        "sottobranca": "Risarcimento danni da circolazione stradale",
        "_profile_inference_reason": (
            "profilo inferito dal contenuto concordante di "
            f"{len(matches)} documenti indicizzati: risarcimento danni da sinistro stradale"
        ),
        "_profile_evidence_documents": evidence_names,
    })
    return inferred


def resolve_document_catalog(
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    document_sha256: str,
    filename: str,
    extracted_text: str,
    document_metadata: dict[str, Any] | None,
    fascicolo_context: dict[str, Any] | None,
) -> CatalogResolution:
    metadata = dict(document_metadata or {})
    context = dict(fascicolo_context or {})
    profile_id, profile_reason = resolve_profile(context)
    synthetic_document = SimpleNamespace(
        nome=filename,
        nome_originale=metadata.get("nome_originale", ""),
        nome_portale=metadata.get("nome_portale", ""),
        percorso="",
        tipo=metadata.get("tipo_documento", ""),
        classificazione_portale=metadata.get("classificazione_portale", ""),
        tipo_atto_portale=metadata.get("tipo_atto_portale", ""),
        servizio_portale=metadata.get("servizio_portale", ""),
        mittente_portale=metadata.get("mittente_portale", ""),
        note=metadata.get("note", ""),
        tags=metadata.get("tags", []),
    )
    metadata_classification = classify_fascicolo_document(
        synthetic_document,
        filename=filename,
        extracted_text=extracted_text,
        tipo=metadata.get("tipo_documento", ""),
    )
    has_extracted_text = bool(str(extracted_text or "").strip())
    identity = _content_identity(extracted_text) if has_extracted_text else None
    if not has_extracted_text:
        classification = _unindexed_content_classification(metadata_classification)
    else:
        content_classification = identity.classification if identity is not None else _classify_indexed_content(extracted_text)
        procedural_only = identity is None and str(content_classification.evidence or "").startswith("nome o OCR: regola presidio ")
        if procedural_only:
            content_classification = _procedural_only_content_classification(content_classification)
        classification = (
            content_classification
            if procedural_only or (content_classification.role != "da_verificare" and content_classification.confidence >= 75)
            else _insufficient_content_classification(metadata_classification)
        )
    source_rows = profile_source_rows(profile_id) if profile_id else []
    has_manual_browser_evidence = any(row["source_type"] == "browser_evidence" for row in source_rows)
    source_state = "manual_browser_evidence" if has_manual_browser_evidence else "verified_snapshot"
    confidence = int(classification.confidence)
    status = "proposed"
    review_reason = ""
    if not has_extracted_text:
        status = "review_required"
        source_state = "review_required"
        confidence = 0
        review_reason = "Il contenuto del documento non è ancora indicizzato nel repository SQL: non viene catalogato dal nome del file."
    elif not profile_id:
        status = "review_required"
        source_state = "review_required"
        confidence = min(confidence, 55)
        review_reason = "Profilo giuridico del fascicolo non determinabile dai dati strutturati."
    elif confidence < 75 or classification.role == "da_verificare":
        status = "review_required"
        source_state = "review_required"
        confidence = min(confidence, 69)
        review_reason = "Le evidenze del documento non consentono una catalogazione automatica affidabile."

    now = utc_now()
    candidate = DocumentCatalogCandidate(
        id=new_id("catalog-candidate"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
        assignment_id="", rank_number=1, profile_id=profile_id,
        document_nature=classification.role, document_label=classification.label,
        document_section=classification.section, deposit_role=classification.deposit_role,
        confidence=confidence, reason=f"{profile_reason}; {classification.evidence}", created_at=now,
    )
    evidence = [
        DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="document_metadata", locator="nome/metadati documento",
            excerpt=filename[:240], weight=35, content_sha256=document_sha256 or None, created_at=now,
        ),
        DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="fascicolo_context", locator="profilo fascicolo",
            excerpt=" · ".join(item for item in (str(context.get("area") or context.get("area_pratica") or ""), str(context.get("branca") or ""), str(context.get("sottobranca") or "")) if item)[:240],
            weight=45 if profile_id else 0, content_sha256=None, created_at=now,
        ),
    ]
    inferred_reason = str(context.get("_profile_inference_reason") or "").strip()
    inferred_documents = context.get("_profile_evidence_documents")
    if inferred_reason:
        names = inferred_documents if isinstance(inferred_documents, list) else []
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="extracted_text", locator="contenuto indicizzato concordante del fascicolo",
            excerpt=f"{inferred_reason}. Documenti: {', '.join(str(name) for name in names[:5])}"[:240],
            weight=70, content_sha256=None, created_at=now,
        ))
    if has_extracted_text:
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="document_identity" if identity is not None else "extracted_text",
            locator="intestazione e contenuto indicizzato" if identity is not None else "testo estratto SQL",
            excerpt=identity.excerpt if identity is not None else "Testo estratto disponibile e valutato dal resolver; il contenuto resta nel lettore interno.",
            weight=100 if identity is not None else 40, content_sha256=document_sha256 or None, created_at=now,
        ))
        for signal in _procedural_signal_evidence(extracted_text):
            signal.tenant_id = tenant_id
            signal.fascicolo_id = fascicolo_id
            signal.content_sha256 = document_sha256 or None
            signal.created_at = now
            evidence.append(signal)
    for row in source_rows:
        source_label = str(row.get("label") or "Fonte ufficiale").strip()
        source_status = str(row.get("verification_status") or "fonte da verificare").strip()
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="legal_source", locator=row["id"],
            excerpt=f"{source_label} — {source_status}"[:240], weight=20,
            content_sha256=str(row.get("snapshot_sha256") or "") or None, created_at=now,
        ))
    review = None
    if status == "review_required":
        review = DocumentCatalogReview(
            id=new_id("catalog-review"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", state="open", reason_code="insufficient_evidence" if profile_id else "missing_fascicolo_profile",
            reason=review_reason, resolved_by=None, resolution_note=None, created_at=now, resolved_at=None,
        )
    return CatalogResolution(
        profile_id=profile_id,
        legal_area=str(context.get("area") or context.get("area_pratica") or ""),
        legal_branch=str(context.get("branca") or context.get("branch") or ""),
        legal_subfamily=str(context.get("sottobranca") or context.get("subfamily") or ""),
        jurisdiction=str(context.get("giurisdizione") or context.get("tribunale") or ""),
        rite=str(context.get("rito") or context.get("tipo_procedimento") or ""),
        proceeding_phase=str(context.get("fase") or ""),
        document_nature=classification.role, document_label=classification.label,
        document_section=classification.section, deposit_role=classification.deposit_role,
        deposit_candidate=bool(classification.deposit_candidate), confidence=confidence,
        status=status, source_state=source_state,
        reason=f"{profile_reason}; {classification.evidence}", candidates=[candidate], evidence=evidence, review=review,
    )


def assert_full_family_matrix(rows: Iterable[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Restituisce eventuali contesti del corpus non risolti dal resolver."""

    missing: list[tuple[str, str, str]] = []
    for row in rows:
        key = (_normalise(row.get("area")), _normalise(row.get("branca")), _normalise(row.get("sottobranca")))
        if key not in FAMILY_PROFILE_BY_CONTEXT:
            missing.append((str(row.get("area") or ""), str(row.get("branca") or ""), str(row.get("sottobranca") or "")))
    return missing


__all__ = [
    "CatalogResolution", "FAMILY_PROFILE_BY_CONTEXT", "FAMILY_PROFILE_ROWS", "PROFILE_SOURCES",
    "INFERRED_PROFILE_CONTEXT_ALIASES", "REGISTRY_VERSION", "RESOLVER_VERSION", "assert_full_family_matrix",
    "infer_fascicolo_context_from_document_corpus", "profile_source_rows",
    "resolve_document_catalog", "resolve_profile",
]
