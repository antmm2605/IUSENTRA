from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

MAX_SYNC_RUNS = 200
SEED_REVISION = "2026-04-01"


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _json_hash(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _unique_sources(codes: Iterable[str]) -> List[Dict[str, str]]:
    unique: List[Dict[str, str]] = []
    seen = set()
    for code in codes or []:
        source = FONTI_OPERATIVE.get(code)
        if not source or code in seen:
            continue
        unique.append(source.to_dict())
        seen.add(code)
    return unique


@dataclass(frozen=True)
class FonteOperativa:
    code: str
    title: str
    url: str
    note: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class InterestPeriod:
    start: date
    end: date
    rate: float
    label: str
    source: FonteOperativa
    mode: str
    reference_rate: Optional[float] = None


FONTI_OPERATIVE: Dict[str, FonteOperativa] = {
    "normattiva_portale": FonteOperativa(
        code="normattiva_portale",
        title="Normattiva - portale ufficiale",
        url="https://www.normattiva.it/",
        note="Fonte primaria per testi vigenti, multivigenza e riferimenti normativi nazionali.",
    ),
    "gazzetta_ufficiale_portale": FonteOperativa(
        code="gazzetta_ufficiale_portale",
        title="Gazzetta Ufficiale - portale ufficiale",
        url="https://www.gazzettaufficiale.it/",
        note="Fonte primaria per pubblicazione, decorrenza e versioni ufficiali degli atti.",
    ),
    "cnf_portale": FonteOperativa(
        code="cnf_portale",
        title="CNF - portale ufficiale",
        url="https://www.consiglionazionaleforense.it/",
        note="Fonte primaria per professione forense, codice deontologico e riferimenti professionali.",
    ),
    "pst_portale": FonteOperativa(
        code="pst_portale",
        title="PST Giustizia - portale ufficiale",
        url="https://pst.giustizia.it/",
        note="Fonte primaria per regole tecniche, servizi web, XSD e note software house.",
    ),
    "giustizia_amministrativa_portale": FonteOperativa(
        code="giustizia_amministrativa_portale",
        title="Giustizia amministrativa - portale ufficiale",
        url="https://www.giustizia-amministrativa.it/",
        note="Fonte primaria per processo amministrativo, decisioni e documentazione tecnica collegata.",
    ),
    "cassazione_portale": FonteOperativa(
        code="cassazione_portale",
        title="Corte di Cassazione - portale ufficiale",
        url="https://www.cortedicassazione.it/",
        note="Fonte primaria per servizi online, massimario e raccolte ufficiali di legittimita.",
    ),
    "corte_costituzionale_portale": FonteOperativa(
        code="corte_costituzionale_portale",
        title="Corte costituzionale - portale ufficiale",
        url="https://www.cortecostituzionale.it/",
        note="Fonte primaria per decisioni, depositi e comunicati costituzionali.",
    ),
    "eur_lex_portale": FonteOperativa(
        code="eur_lex_portale",
        title="EUR-Lex - portale ufficiale",
        url="https://eur-lex.europa.eu/",
        note="Fonte primaria per normativa e giurisprudenza dell'Unione europea.",
    ),
    "dpr_115_2002": FonteOperativa(
        code="dpr_115_2002",
        title="D.P.R. 115/2002 - art. 13 (Normattiva)",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A2002-05-30%3B115~art130=",
        note="Base normativa del contributo unificato nei processi civile, amministrativo e tributario.",
    ),
    "cu_viterbo": FonteOperativa(
        code="cu_viterbo",
        title="Tribunale di Viterbo - tabelle contributo unificato",
        url="https://www.tribunale.viterbo.giustizia.it/it/Content/Index/58499",
        note="Tabella pratica per iscrizione a ruolo civile e decreti ingiuntivi.",
    ),
    "cu_admin": FonteOperativa(
        code="cu_admin",
        title="Giustizia Amministrativa - Carta dei servizi TAR Calabria",
        url="https://www.giustizia-amministrativa.it/documents/20142/17127638/T.A.R.%2BCalabria_sede%2Bdi%2BCatanzaro%2B-%2BCarta%2Bdei%2Bservizi%2B2022_QRcode.pdf/86de0520-27bb-2db2-733b-a58ac97df323?t=1671443142000",
        note="Importi ufficiali pubblicati per ricorsi ordinari, rito abbreviato, appalti e ottemperanza.",
    ),
    "interesse_legale_2024": FonteOperativa(
        code="interesse_legale_2024",
        title="G.U. - saggio interessi legali 2024",
        url="https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=23A00141&art.dataPubblicazioneGazzetta=2023-01-16&art.flagTipoArticolo=0&art.idArticolo=1&art.idGruppo=1&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=16&art.versione=1",
        note="Misura del saggio legale pari al 2,50% dal 1 gennaio 2024.",
    ),
    "interesse_legale_2025": FonteOperativa(
        code="interesse_legale_2025",
        title="G.U. - saggio interessi legali 2025",
        url="https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticolo?art.codiceRedazionale=012G0252&art.dataPubblicazioneGazzetta=2012-12-29&art.flagTipoArticolo=0&art.idArticolo=1&art.idGruppo=0&art.idSottoArticolo=1&art.idSottoArticolo1=10&art.progressivo=20&art.versione=1",
        note="Dal 1 gennaio 2025 il saggio legale e pari al 2,00%.",
    ),
    "interesse_legale_2026": FonteOperativa(
        code="interesse_legale_2026",
        title="G.U. - saggio interessi legali 2026",
        url="https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloDefault/originario?atto.codiceRedazionale=25A07054&atto.dataPubblicazioneGazzetta=2025-12-31&atto.tipoProvvedimento=DECRETO",
        note="Dal 1 gennaio 2026 il saggio legale e pari all'1,60%.",
    ),
    "mora_231_2025_h1": FonteOperativa(
        code="mora_231_2025_h1",
        title="G.U. - tasso di riferimento 1 gennaio / 30 giugno 2025",
        url="https://www.gazzettaufficiale.it/do/gazzetta/downloadPdf?dataPubblicazioneGazzetta=20250317&edizione=0&estensione=pdf&home=true&numeroGazzetta=63&numeroSupplemento=0&progressivo=0&tipoSerie=SG&tipoSupplemento=GU",
        note="Comunicazione ex art. 5 D.Lgs. 231/2002: tasso di riferimento 3,15%.",
    ),
    "mora_231_2025_h2": FonteOperativa(
        code="mora_231_2025_h2",
        title="G.U. - tasso di riferimento 1 luglio / 31 dicembre 2025",
        url="https://www.gazzettaufficiale.it/do/gazzetta/downloadPdf?dataPubblicazioneGazzetta=20250714&edizione=0&estensione=pdf&home=true&numeroGazzetta=161&numeroSupplemento=0&progressivo=0&tipoSerie=SG&tipoSupplemento=GU",
        note="Comunicazione ex art. 5 D.Lgs. 231/2002: tasso di riferimento 2,15%.",
    ),
    "mora_231_2026_h1": FonteOperativa(
        code="mora_231_2026_h1",
        title="G.U. - tasso di riferimento 1 gennaio / 30 giugno 2026",
        url="https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=26A00172&atto.dataPubblicazioneGazzetta=2026-01-20&tipoSerie=serie_generale&tipoVigenza=originario",
        note="Comunicazione ex art. 5 D.Lgs. 231/2002: tasso di riferimento 2,15%.",
    ),
    "art_545_cpc": FonteOperativa(
        code="art_545_cpc",
        title="Codice di procedura civile - art. 545 (Normattiva)",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Aregio.decreto%3A1940-10-28%3B1443%21vig=",
        note="Pignorabilita di stipendi, salari, pensioni e altre indennita.",
    ),
    "dpr_602_1973": FonteOperativa(
        code="dpr_602_1973",
        title="D.P.R. 602/1973 - art. 72-ter (Normattiva)",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1973-09-29%3B602%21vig=",
        note="Limiti di pignoramento per riscossione esattoriale.",
    ),
    "assegno_sociale_2026": FonteOperativa(
        code="assegno_sociale_2026",
        title="INPS - Allegato perequazione 2026",
        url="https://www.inps.it/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2025/12/Circolare_15109/Allegati/16486_Circolare-numero-153-del-19-12-2025_Allegato-n-2.pdf",
        note="Assegno sociale 2026: EUR 546,24 mensili.",
    ),
    "l_319_1980": FonteOperativa(
        code="l_319_1980",
        title="L. 319/1980 - onorari a vacazione",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1980-07-08%3B319%21vig=",
        note="Disciplina generale di periti, consulenti tecnici, interpreti e traduttori.",
    ),
    "dm_30_05_2002": FonteOperativa(
        code="dm_30_05_2002",
        title="D.M. 30 maggio 2002 - adeguamento vacazioni",
        url="https://www.gazzettaufficiale.it/eli/gu/2002/08/05/182/sg/pdf",
        note="Importi vigenti delle vacazioni: EUR 14,68 la prima e EUR 8,15 le successive.",
    ),
}


def _slug_component(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return value.strip("_")


def _watch_source_ids_for_url(url: str) -> List[str]:
    value = (url or "").lower()
    source_ids: List[str] = []
    mapping = (
        ("normattiva.it", "normattiva"),
        ("gazzettaufficiale.it", "gazzetta_ufficiale"),
        ("consiglionazionaleforense.it", "cnf"),
        ("pst.giustizia.it", "pst_giustizia"),
        ("giustizia-amministrativa.it", "giustizia_amministrativa"),
        ("cortedicassazione.it", "cassazione"),
        ("cortecostituzionale.it", "corte_costituzionale"),
        ("eur-lex.europa.eu", "eur_lex"),
        ("inps.it", "gazzetta_ufficiale"),
    )
    for needle, source_id in mapping:
        if needle in value and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids or ["normattiva"]


def _source_codes_for_watch_ids(source_ids: Iterable[str]) -> List[str]:
    mapping = {
        "normattiva": "normattiva_portale",
        "gazzetta_ufficiale": "gazzetta_ufficiale_portale",
        "cnf": "cnf_portale",
        "pst_giustizia": "pst_portale",
        "giustizia_amministrativa": "giustizia_amministrativa_portale",
        "cassazione": "cassazione_portale",
        "corte_costituzionale": "corte_costituzionale_portale",
        "eur_lex": "eur_lex_portale",
    }
    rows: List[str] = []
    for source_id in source_ids or []:
        code = mapping.get(source_id)
        if code and code not in rows:
            rows.append(code)
    return rows


def _build_reference_code(title: str, article: str, url: str) -> str:
    base = _slug_component(title) or "riferimento"
    article_part = _slug_component(article)
    url_part = hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:8]
    if article_part:
        return f"{base}_{article_part}_{url_part}"
    return f"{base}_{url_part}"


def canonical_reference_catalog_definition() -> Dict[str, Any]:
    from pct.motore_preventivo import catalogo_riferimenti_normativi

    reference_rows = []
    source_ids: List[str] = []
    source_codes: List[str] = []
    for ref in catalogo_riferimenti_normativi():
        watch_ids = _watch_source_ids_for_url(ref.get("url", ""))
        for source_id in watch_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
        for code in _source_codes_for_watch_ids(watch_ids):
            if code not in source_codes:
                source_codes.append(code)
        reference_rows.append(
            {
                "reference_code": _build_reference_code(
                    ref.get("title", ""),
                    ref.get("article", ""),
                    ref.get("url", ""),
                ),
                "title": ref.get("title", ""),
                "article": ref.get("article", ""),
                "description": ref.get("description", ""),
                "url": ref.get("url", ""),
                "areas": list(ref.get("areas", []) or []),
                "tipologie_ids": list(ref.get("tipologie_ids", []) or []),
                "tipologie_labels": list(ref.get("tipologie_labels", []) or []),
                "motori": list(ref.get("motori", []) or []),
                "redattori": list(ref.get("redattori", []) or []),
                "watch_source_ids": watch_ids,
            }
        )

    reference_rows.sort(key=lambda item: (item["title"], item["article"], item["url"]))
    return {
        "id": "riferimenti_normativi_catalogo",
        "title": "Catalogo riferimenti normativi ufficiali",
        "category": "riferimenti_normativi",
        "description": (
            "Catalogo centralizzato delle norme ufficiali richiamate dai motori legali, "
            "dal preventivo guidato e dai redattori interni."
        ),
        "strategy": "seed_mirror",
        "source_codes": source_codes or ["normattiva_portale", "gazzetta_ufficiale_portale"],
        "watch_source_ids": source_ids or ["normattiva", "gazzetta_ufficiale"],
        "rows": reference_rows,
        "defaults": {"total_references": len(reference_rows)},
        "published_at": SEED_REVISION,
        "effective_from": SEED_REVISION,
    }


def canonical_table_definitions() -> Dict[str, Dict[str, Any]]:
    definitions = {
        "contributo_unificato_civile": {
            "id": "contributo_unificato_civile",
            "title": "Contributo unificato civile",
            "category": "contributi",
            "description": "Scaglioni contributo unificato per il civile ordinario e base di calcolo per il decreto ingiuntivo.",
            "strategy": "seed_mirror",
            "source_codes": ["dpr_115_2002", "cu_viterbo"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": [
                {"max_value": 1100.0, "amount": 43.0},
                {"max_value": 5200.0, "amount": 98.0},
                {"max_value": 26000.0, "amount": 237.0},
                {"max_value": 52000.0, "amount": 518.0},
                {"max_value": 260000.0, "amount": 759.0},
                {"max_value": 520000.0, "amount": 1214.0},
                {"max_value": None, "amount": 1686.0},
            ],
            "defaults": {"indeterminabile_amount": 518.0},
            "published_at": "",
            "effective_from": "2024-01-01",
        },
        "contributo_unificato_tributario": {
            "id": "contributo_unificato_tributario",
            "title": "Contributo unificato tributario",
            "category": "contributi",
            "description": "Scaglioni contributo unificato per il contenzioso tributario.",
            "strategy": "seed_mirror",
            "source_codes": ["dpr_115_2002"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": [
                {"max_value": 2582.28, "amount": 30.0},
                {"max_value": 5000.0, "amount": 60.0},
                {"max_value": 25000.0, "amount": 120.0},
                {"max_value": 75000.0, "amount": 250.0},
                {"max_value": 200000.0, "amount": 500.0},
                {"max_value": None, "amount": 1500.0},
            ],
            "published_at": "",
            "effective_from": "2024-01-01",
        },
        "contributo_unificato_speciali": {
            "id": "contributo_unificato_speciali",
            "title": "Contributo unificato casi speciali",
            "category": "contributi",
            "description": "Importi fissi o speciali per volontaria giurisdizione e amministrativo.",
            "strategy": "seed_mirror",
            "source_codes": ["dpr_115_2002", "cu_admin"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": [
                {"category": "volontaria_giurisdizione", "amount": 98.0},
                {"category": "separazione_consensuale", "amount": 43.0},
                {"category": "amministrativo_ordinario", "amount": 650.0},
                {"category": "amministrativo_rito_abbreviato", "amount": 1800.0},
                {"category": "amministrativo_appalti", "max_value": 200000.0, "amount": 2000.0},
                {"category": "amministrativo_appalti", "max_value": 1000000.0, "amount": 4000.0},
                {"category": "amministrativo_appalti", "max_value": None, "amount": 6000.0},
                {"category": "amministrativo_ottemperanza", "amount": 300.0},
            ],
            "published_at": "",
            "effective_from": "2024-01-01",
        },
        "interesse_legale": {
            "id": "interesse_legale",
            "title": "Interessi legali",
            "category": "tassi",
            "description": "Saggi di interesse legale articolati per periodo di validita.",
            "strategy": "seed_mirror",
            "source_codes": ["interesse_legale_2024", "interesse_legale_2025", "interesse_legale_2026"],
            "watch_source_ids": ["gazzetta_ufficiale"],
            "rows": [
                {"start": "2024-01-01", "end": "2024-12-31", "rate": 2.50, "label": "Interesse legale 2024", "source_code": "interesse_legale_2024"},
                {"start": "2025-01-01", "end": "2025-12-31", "rate": 2.00, "label": "Interesse legale 2025", "source_code": "interesse_legale_2025"},
                {"start": "2026-01-01", "end": "2026-12-31", "rate": 1.60, "label": "Interesse legale 2026", "source_code": "interesse_legale_2026"},
            ],
            "published_at": "2025-12-31",
            "effective_from": "2024-01-01",
        },
        "mora_commerciale": {
            "id": "mora_commerciale",
            "title": "Interessi moratori ex D.Lgs. 231/2002",
            "category": "tassi",
            "description": "Tassi di mora commerciale per semestre con riferimento BCE.",
            "strategy": "seed_mirror",
            "source_codes": ["mora_231_2025_h1", "mora_231_2025_h2", "mora_231_2026_h1"],
            "watch_source_ids": ["gazzetta_ufficiale"],
            "rows": [
                {"start": "2025-01-01", "end": "2025-06-30", "rate": 11.15, "reference_rate": 3.15, "label": "Mora commerciale 1 semestre 2025", "source_code": "mora_231_2025_h1"},
                {"start": "2025-07-01", "end": "2025-12-31", "rate": 10.15, "reference_rate": 2.15, "label": "Mora commerciale 2 semestre 2025", "source_code": "mora_231_2025_h2"},
                {"start": "2026-01-01", "end": "2026-06-30", "rate": 10.15, "reference_rate": 2.15, "label": "Mora commerciale 1 semestre 2026", "source_code": "mora_231_2026_h1"},
            ],
            "published_at": "2026-01-20",
            "effective_from": "2025-01-01",
        },
        "pignoramento_soglie": {
            "id": "pignoramento_soglie",
            "title": "Soglie pignoramento stipendio e pensione",
            "category": "esecuzioni",
            "description": "Regole operative per quote ordinarie, esattoriali, alimentari e minimo pensionistico.",
            "strategy": "seed_mirror",
            "source_codes": ["art_545_cpc", "dpr_602_1973", "assegno_sociale_2026"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": [
                {"rule_code": "ordinario_quota", "value": 20.0, "unit": "percent"},
                {"rule_code": "esattoriale_fino_2500", "value": 10.0, "unit": "percent"},
                {"rule_code": "esattoriale_fino_5000", "value": 14.2857, "unit": "percent"},
                {"rule_code": "esattoriale_oltre_5000", "value": 20.0, "unit": "percent"},
                {"rule_code": "alimentare_default", "value": 33.33, "unit": "percent"},
                {"rule_code": "pensione_minimo_multiplier", "value": 1.5, "unit": "multiplier"},
            ],
            "published_at": "2025-12-19",
            "effective_from": "2026-01-01",
        },
        "assegno_sociale": {
            "id": "assegno_sociale",
            "title": "Assegno sociale",
            "category": "previdenza",
            "description": "Importi annuali dell'assegno sociale utili ai limiti di pignorabilita.",
            "strategy": "seed_mirror",
            "source_codes": ["assegno_sociale_2026"],
            "watch_source_ids": ["gazzetta_ufficiale"],
            "rows": [
                {"year": 2026, "monthly_amount": 546.24, "source_code": "assegno_sociale_2026"},
            ],
            "published_at": "2025-12-19",
            "effective_from": "2026-01-01",
        },
        "ctu_vacazioni": {
            "id": "ctu_vacazioni",
            "title": "Vacazioni CTU",
            "category": "compensi_ausiliari",
            "description": "Importi per vacazioni di consulenti tecnici, interpreti e ausiliari.",
            "strategy": "seed_mirror",
            "source_codes": ["l_319_1980", "dm_30_05_2002"],
            "watch_source_ids": ["gazzetta_ufficiale", "normattiva"],
            "rows": [
                {"kind": "prima", "amount": 14.68},
                {"kind": "successiva", "amount": 8.15},
            ],
            "published_at": "2002-08-05",
            "effective_from": "2002-08-05",
        },
    }
    reference_definition = canonical_reference_catalog_definition()
    definitions[reference_definition["id"]] = reference_definition
    return definitions


class GestioneTabelleNormative:
    def __init__(self, db_path: str = "./intelligence/tabelle_normative.json"):
        self.db_path = db_path
        self._data: Dict[str, Any] = {"tables": {}, "sync_runs": []}
        self._load()
        self._ensure_seeded()

    def _load(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
            self._data["tables"] = dict(raw.get("tables") or {})
            self._data["sync_runs"] = list(raw.get("sync_runs") or [])
        except Exception:
            self._data = {"tables": {}, "sync_runs": []}

    def _save(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def _ensure_seeded(self) -> None:
        seed_time = datetime.now()
        existing_tables = self._data.setdefault("tables", {})
        created_tables: List[str] = []
        for table_id, definition in canonical_table_definitions().items():
            if table_id in existing_tables:
                continue
            existing_tables[table_id] = self._build_table_payload(definition, seed_time, created=True)
            created_tables.append(table_id)
        if created_tables:
            self._append_sync_run(
                {
                    "id": uuid.uuid4().hex,
                    "created_at": _now_iso(seed_time),
                    "status": "bootstrap" if len(created_tables) == len(existing_tables) else "bootstrap_incrementale",
                    "processed_tables": len(canonical_table_definitions()),
                    "created": len(created_tables),
                    "updated": 0,
                    "review_required": 0,
                    "tables": created_tables,
                }
            )
            self._save()

    def _append_sync_run(self, payload: Dict[str, Any]) -> None:
        self._data.setdefault("sync_runs", []).append(payload)
        if len(self._data["sync_runs"]) > MAX_SYNC_RUNS:
            self._data["sync_runs"] = self._data["sync_runs"][-MAX_SYNC_RUNS:]

    def _build_version_payload(
        self,
        definition: Mapping[str, Any],
        now: datetime,
        *,
        origin: str = "seed",
    ) -> Dict[str, Any]:
        rows = list(definition.get("rows") or [])
        data_hash = _json_hash(rows)
        return {
            "id": f"{definition['id']}:{SEED_REVISION}:{data_hash[:12]}",
            "label": f"Seed ufficiale {SEED_REVISION}",
            "created_at": _now_iso(now),
            "effective_from": definition.get("effective_from", ""),
            "effective_to": "",
            "published_at": definition.get("published_at", ""),
            "acquired_at": _now_iso(now),
            "status": "active",
            "origin": origin,
            "data_hash": data_hash,
            "rows": rows,
            "notes": list(definition.get("notes") or []),
        }

    def _build_table_payload(
        self,
        definition: Mapping[str, Any],
        now: datetime,
        *,
        created: bool = False,
    ) -> Dict[str, Any]:
        return {
            "id": definition["id"],
            "title": definition["title"],
            "category": definition.get("category", ""),
            "description": definition.get("description", ""),
            "strategy": definition.get("strategy", "seed_mirror"),
            "defaults": dict(definition.get("defaults") or {}),
            "source_codes": list(definition.get("source_codes") or []),
            "watch_source_ids": list(definition.get("watch_source_ids") or []),
            "sync_status": "sincronizzata",
            "last_synced_at": _now_iso(now),
            "last_source_change_at": "",
            "last_warning": "",
            "versions": [self._build_version_payload(definition, now, origin="bootstrap" if created else "sync")],
        }

    def _active_version(self, table: Mapping[str, Any], on_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        versions = list(table.get("versions") or [])
        versions.sort(key=lambda item: (item.get("effective_from", ""), item.get("created_at", "")), reverse=True)
        if on_date:
            for version in versions:
                start = _parse_date(version.get("effective_from"))
                end = _parse_date(version.get("effective_to"))
                if start and on_date < start:
                    continue
                if end and on_date > end:
                    continue
                return version
        return next((version for version in versions if version.get("status") == "active"), versions[0] if versions else None)

    def catalogo_fonti(self) -> List[Dict[str, str]]:
        return [source.to_dict() for source in FONTI_OPERATIVE.values()]

    def get_table(self, table_id: str, on_date: Optional[date] = None) -> Dict[str, Any]:
        table = self._data.get("tables", {}).get(table_id)
        if not table:
            raise KeyError(f"Tabella normativa non trovata: {table_id}")
        active = self._active_version(table, on_date=on_date)
        return {
            "id": table["id"],
            "title": table.get("title", table_id),
            "category": table.get("category", ""),
            "description": table.get("description", ""),
            "strategy": table.get("strategy", ""),
            "defaults": dict(table.get("defaults") or {}),
            "sync_status": table.get("sync_status", "sconosciuta"),
            "last_synced_at": table.get("last_synced_at", ""),
            "last_source_change_at": table.get("last_source_change_at", ""),
            "last_warning": table.get("last_warning", ""),
            "sources": _unique_sources(table.get("source_codes") or []),
            "watch_source_ids": list(table.get("watch_source_ids") or []),
            "active_version": dict(active or {}),
            "versions_count": len(table.get("versions") or []),
        }

    def rows(self, table_id: str, on_date: Optional[date] = None) -> List[Dict[str, Any]]:
        table = self.get_table(table_id, on_date=on_date)
        return list((table.get("active_version") or {}).get("rows") or [])

    def catalogo_riferimenti_normativi(self) -> List[Dict[str, Any]]:
        try:
            rows = list(self.rows("riferimenti_normativi_catalogo"))
        except KeyError:
            return []
        rows.sort(key=lambda item: (item.get("title", ""), item.get("article", "")))
        return rows

    def catalogo_tabelle(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for table_id in sorted(self._data.get("tables", {})):
            table = self.get_table(table_id)
            active = table.get("active_version") or {}
            rows.append(
                {
                    "id": table["id"],
                    "title": table["title"],
                    "category": table["category"],
                    "description": table["description"],
                    "sync_status": table["sync_status"],
                    "last_synced_at": table["last_synced_at"],
                    "last_source_change_at": table["last_source_change_at"],
                    "last_warning": table["last_warning"],
                    "versions_count": table["versions_count"],
                    "data_hash": active.get("data_hash", ""),
                    "sources": table["sources"],
                    "watch_source_ids": table["watch_source_ids"],
                }
            )
        return rows

    def snapshot(self) -> Dict[str, Any]:
        catalogo = self.catalogo_tabelle()
        riferimenti = self.catalogo_riferimenti_normativi()
        return {
            "totali": len(catalogo),
            "sincronizzate": sum(1 for row in catalogo if row["sync_status"] == "sincronizzata"),
            "verifica_richiesta": sum(1 for row in catalogo if row["sync_status"] == "verifica_richiesta"),
            "fonte_non_raggiungibile": sum(1 for row in catalogo if row["sync_status"] == "fonte_non_raggiungibile"),
            "riferimenti_normativi_totali": len(riferimenti),
            "riferimenti_normativi": riferimenti[:20],
            "tabelle": catalogo,
            "recent_sync_runs": list(reversed(self._data.get("sync_runs", [])[-8:])),
        }

    def interest_periods(self, mode: str) -> List[InterestPeriod]:
        table_id = "interesse_legale" if mode == "legali" else "mora_commerciale"
        periods: List[InterestPeriod] = []
        for row in self.rows(table_id):
            source = FONTI_OPERATIVE[row["source_code"]]
            periods.append(
                InterestPeriod(
                    start=_parse_date(row["start"]) or date.today(),
                    end=_parse_date(row["end"]) or date.today(),
                    rate=float(row["rate"]),
                    label=str(row.get("label", table_id)),
                    source=source,
                    mode=mode,
                    reference_rate=float(row["reference_rate"]) if row.get("reference_rate") is not None else None,
                )
            )
        return periods

    def contributo_tiers(self, kind: str) -> List[tuple[float, float]]:
        table_id = "contributo_unificato_civile" if kind == "civile" else "contributo_unificato_tributario"
        tiers: List[tuple[float, float]] = []
        for row in self.rows(table_id):
            limit = float(row["max_value"]) if row.get("max_value") is not None else float("inf")
            tiers.append((limit, float(row["amount"])))
        return tiers

    def contributo_defaults(self, kind: str) -> Dict[str, Any]:
        table_id = "contributo_unificato_civile" if kind == "civile" else "contributo_unificato_tributario"
        return dict(self.get_table(table_id).get("defaults") or {})

    def contributo_speciale(self, category: str, value: float = 0.0) -> float:
        rows = [row for row in self.rows("contributo_unificato_speciali") if row.get("category") == category]
        if not rows:
            raise KeyError(f"Categoria contributo speciale non trovata: {category}")
        if any(row.get("max_value") is not None for row in rows):
            ordered = sorted(rows, key=lambda row: float(row["max_value"]) if row.get("max_value") is not None else float("inf"))
            for row in ordered:
                limit = float(row["max_value"]) if row.get("max_value") is not None else float("inf")
                if value <= limit:
                    return float(row["amount"])
            return float(ordered[-1]["amount"])
        return float(rows[0]["amount"])

    def assegno_sociale(self, year: Optional[int] = None) -> float:
        rows = sorted(self.rows("assegno_sociale"), key=lambda row: int(row.get("year", 0)))
        if not rows:
            raise ValueError("Tabella assegno sociale non disponibile.")
        if year is not None:
            candidates = [row for row in rows if int(row.get("year", 0)) <= year]
            if candidates:
                return float(candidates[-1]["monthly_amount"])
        return float(rows[-1]["monthly_amount"])

    def pignoramento_rules(self) -> Dict[str, Dict[str, Any]]:
        return {row["rule_code"]: dict(row) for row in self.rows("pignoramento_soglie")}

    def ctu_vacazioni(self) -> Dict[str, float]:
        amounts = {row["kind"]: float(row["amount"]) for row in self.rows("ctu_vacazioni")}
        return {
            "prima": amounts.get("prima", 0.0),
            "successiva": amounts.get("successiva", 0.0),
        }

    def sync_from_canonical(
        self,
        *,
        source_runs: Optional[Mapping[str, Any]] = None,
        source_ids: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        watched_ids = set(source_ids or [])
        definitions = canonical_table_definitions()
        source_runs = dict(source_runs or {})

        processed = 0
        created = 0
        updated = 0
        review_required = 0
        warnings: List[Dict[str, str]] = []
        touched_tables: List[Dict[str, Any]] = []

        for table_id, definition in definitions.items():
            watch_source_ids = set(definition.get("watch_source_ids") or [])
            if watched_ids and not (watch_source_ids & watched_ids):
                continue

            processed += 1
            table = self._data["tables"].get(table_id)
            canonical_hash = self._build_version_payload(definition, current_time)["data_hash"]
            table_changed = False
            if not table:
                table = self._build_table_payload(definition, current_time, created=True)
                self._data["tables"][table_id] = table
                created += 1
                table_changed = True
            else:
                table["title"] = definition["title"]
                table["category"] = definition.get("category", "")
                table["description"] = definition.get("description", "")
                table["strategy"] = definition.get("strategy", "seed_mirror")
                table["defaults"] = dict(definition.get("defaults") or {})
                table["source_codes"] = list(definition.get("source_codes") or [])
                table["watch_source_ids"] = list(definition.get("watch_source_ids") or [])
                active_version = self._active_version(table)
                if not active_version or active_version.get("data_hash") != canonical_hash:
                    for version in table.get("versions") or []:
                        if version.get("status") == "active":
                            version["status"] = "superseded"
                            version["effective_to"] = current_time.date().isoformat()
                    table.setdefault("versions", []).append(self._build_version_payload(definition, current_time, origin="sync"))
                    updated += 1
                    table_changed = True

            relevant_runs = {
                source_id: source_runs[source_id]
                for source_id in definition.get("watch_source_ids") or []
                if source_id in source_runs
            }
            changed_sources = [source_id for source_id, run in relevant_runs.items() if bool((run or {}).get("changed"))]
            failed_sources = [source_id for source_id, run in relevant_runs.items() if str((run or {}).get("status", "")) not in {"", "ok"}]
            if failed_sources:
                table["sync_status"] = "fonte_non_raggiungibile"
                table["last_warning"] = f"Fonte monitorata non raggiungibile: {', '.join(failed_sources)}."
                warnings.append({"table_id": table_id, "warning": table["last_warning"]})
            elif changed_sources and not table_changed:
                table["sync_status"] = "verifica_richiesta"
                table["last_warning"] = (
                    "Fonte ufficiale variata ma nessuna tabella strutturata e stata aggiornata automaticamente. "
                    f"Verificare: {', '.join(changed_sources)}."
                )
                review_required += 1
                warnings.append({"table_id": table_id, "warning": table["last_warning"]})
            else:
                table["sync_status"] = "sincronizzata"
                table["last_warning"] = ""
            table["last_synced_at"] = _now_iso(current_time)
            if changed_sources:
                table["last_source_change_at"] = _now_iso(current_time)
            touched_tables.append(
                {
                    "id": table_id,
                    "title": table.get("title", table_id),
                    "sync_status": table.get("sync_status", "sincronizzata"),
                    "updated": table_changed,
                }
            )

        report = {
            "ok": True,
            "processed_tables": processed,
            "created": created,
            "updated": updated,
            "review_required": review_required,
            "warnings": warnings,
            "tables": touched_tables,
            "checked_source_ids": sorted(watched_ids) if watched_ids else [],
        }
        self._append_sync_run(
            {
                "id": uuid.uuid4().hex,
                "created_at": _now_iso(current_time),
                "status": "ok",
                **report,
            }
        )
        self._save()
        return report
