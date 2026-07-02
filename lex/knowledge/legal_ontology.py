"""Ontologia giuridica seed di Lex (dati puri, deterministici, zero import).

Mini-ontologia per area del diritto: concetti principali con sinonimi, fonti
primarie consigliate e concetti correlati. Le chiavi area coincidono con le
aree del Source Policy System (`lex.research.source_policy` / `ai_lex_sources`)
così `infer_area` e `allowed_domains` restano direttamente componibili.

Fonti certe: ogni concetto seed indica la propria base normativa primaria
(es. responsabilità civile → art. 2043 c.c.; trattamento dati → Regolamento
(UE) 2016/679; procedimento amministrativo → L. 241/1990). L'ontologia cresce
solo tramite ImprovementProposal approvate da un umano, mai in automatico.
"""

from __future__ import annotations

LEGAL_ONTOLOGY: dict[str, dict[str, dict[str, list[str]]]] = {
    "civile": {
        "responsabilità civile": {
            "synonyms": ["responsabilità aquiliana", "responsabilità extracontrattuale", "illecito civile"],
            "primary_sources": ["art. 2043 c.c.", "Cassazione civile"],
            "related": ["danno ingiusto", "nesso causale", "risarcimento del danno", "colpa"],
        },
        "contratto": {
            "synonyms": ["accordo contrattuale"],
            "primary_sources": ["art. 1321 c.c."],
            "related": ["obbligazione", "inadempimento", "buona fede", "nullità", "annullabilità"],
        },
        "obbligazione": {
            "synonyms": ["rapporto obbligatorio"],
            "primary_sources": ["art. 1173 c.c."],
            "related": ["adempimento", "mora", "prescrizione"],
        },
        "onere della prova": {
            "synonyms": ["riparto probatorio"],
            "primary_sources": ["art. 2697 c.c."],
            "related": ["presunzione", "prova documentale"],
        },
        "prescrizione": {
            "synonyms": ["estinzione per decorso del tempo"],
            "primary_sources": ["art. 2934 c.c."],
            "related": ["decadenza", "interruzione della prescrizione"],
        },
    },
    "privacy": {
        "trattamento dati": {
            "synonyms": ["trattamento dei dati personali", "trattamento di dati"],
            "primary_sources": ["Regolamento (UE) 2016/679", "Garante Privacy", "EDPB"],
            "related": ["consenso", "titolare del trattamento", "interessato", "base giuridica"],
        },
        "consenso": {
            "synonyms": ["consenso dell'interessato"],
            "primary_sources": ["art. 6 Regolamento (UE) 2016/679", "art. 7 Regolamento (UE) 2016/679"],
            "related": ["informativa", "revoca del consenso"],
        },
        "legittimo interesse": {
            "synonyms": ["interesse legittimo del titolare"],
            "primary_sources": ["art. 6 Regolamento (UE) 2016/679", "EDPB"],
            "related": ["bilanciamento", "base giuridica"],
        },
        "data breach": {
            "synonyms": ["violazione dei dati personali"],
            "primary_sources": ["art. 33 Regolamento (UE) 2016/679", "Garante Privacy"],
            "related": ["notifica al garante", "misure di sicurezza"],
        },
        "titolare del trattamento": {
            "synonyms": ["titolare"],
            "primary_sources": ["art. 4 Regolamento (UE) 2016/679"],
            "related": ["responsabile del trattamento", "contitolarità"],
        },
    },
    "amministrativo": {
        "procedimento amministrativo": {
            "synonyms": ["iter procedimentale amministrativo"],
            "primary_sources": ["L. 241/1990"],
            "related": ["responsabile del procedimento", "motivazione", "termine del procedimento"],
        },
        "accesso agli atti": {
            "synonyms": ["diritto di accesso", "accesso documentale"],
            "primary_sources": ["L. 241/1990", "D.Lgs. 33/2013"],
            "related": ["trasparenza", "controinteressati"],
        },
        "provvedimento": {
            "synonyms": ["provvedimento amministrativo"],
            "primary_sources": ["L. 241/1990"],
            "related": ["autotutela", "annullamento d'ufficio", "eccesso di potere"],
        },
        "interesse legittimo": {
            "synonyms": ["posizione di interesse legittimo"],
            "primary_sources": ["art. 103 Cost.", "Consiglio di Stato"],
            "related": ["giurisdizione amministrativa", "ricorso"],
        },
        "silenzio-assenso": {
            "synonyms": ["silenzio assenso", "silenzio significativo"],
            "primary_sources": ["L. 241/1990"],
            "related": ["silenzio-inadempimento", "conferenza di servizi"],
        },
    },
    "penale": {
        "reato": {
            "synonyms": ["fatto di reato", "illecito penale"],
            "primary_sources": ["c.p.", "Cassazione penale"],
            "related": ["dolo", "colpa", "tipicità", "antigiuridicità"],
        },
        "misura cautelare": {
            "synonyms": ["misure cautelari personali"],
            "primary_sources": ["art. 272 c.p.p."],
            "related": ["custodia cautelare", "esigenze cautelari"],
        },
        "querela": {
            "synonyms": ["atto di querela"],
            "primary_sources": ["art. 120 c.p.", "art. 336 c.p.p."],
            "related": ["remissione di querela", "procedibilità"],
        },
    },
    "tributario": {
        "accertamento": {
            "synonyms": ["avviso di accertamento", "accertamento tributario"],
            "primary_sources": ["D.P.R. 600/1973", "Agenzia delle Entrate"],
            "related": ["contraddittorio", "cartella di pagamento", "ravvedimento operoso"],
        },
        "imposta": {
            "synonyms": ["tributo"],
            "primary_sources": ["D.P.R. 917/1986"],
            "related": ["detrazione", "deduzione", "sanzione amministrativa"],
        },
    },
    "lavoro": {
        "licenziamento": {
            "synonyms": ["recesso datoriale"],
            "primary_sources": ["L. 604/1966", "art. 18 L. 300/1970"],
            "related": ["giusta causa", "giustificato motivo", "reintegrazione"],
        },
        "subordinazione": {
            "synonyms": ["lavoro subordinato"],
            "primary_sources": ["art. 2094 c.c."],
            "related": ["eterodirezione", "collaborazione coordinata"],
        },
    },
}


def ontology_areas() -> list[str]:
    return sorted(LEGAL_ONTOLOGY)


def known_concepts(area: str = "") -> set[str]:
    """Concetti e sinonimi noti (casefold), per area o globali."""

    areas = [area] if area and area in LEGAL_ONTOLOGY else list(LEGAL_ONTOLOGY)
    known: set[str] = set()
    for key in areas:
        for concept, payload in LEGAL_ONTOLOGY[key].items():
            known.add(concept.casefold())
            known.update(str(item).casefold() for item in payload.get("synonyms", []))
            known.update(str(item).casefold() for item in payload.get("related", []))
    return known


def is_known_concept(term: str, area: str = "") -> bool:
    return str(term or "").casefold().strip() in known_concepts(area)


def primary_sources_for(concept: str, area: str = "") -> list[str]:
    """Fonti primarie consigliate per un concetto (match su nome o sinonimo)."""

    needle = str(concept or "").casefold().strip()
    areas = [area] if area and area in LEGAL_ONTOLOGY else list(LEGAL_ONTOLOGY)
    for key in areas:
        for name, payload in LEGAL_ONTOLOGY[key].items():
            candidates = {name.casefold(), *(str(item).casefold() for item in payload.get("synonyms", []))}
            if needle in candidates:
                return list(payload.get("primary_sources", []))
    return []


__all__ = [
    "LEGAL_ONTOLOGY",
    "is_known_concept",
    "known_concepts",
    "ontology_areas",
    "primary_sources_for",
]
