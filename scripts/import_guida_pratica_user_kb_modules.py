from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica.service import normalize_codice_materia  # noqa: E402
from pct.guida_pratica.web_enrichment import SOURCE_LIBRARY, VERIFIED_ON, web_sources_for_guidance  # noqa: E402
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry  # noqa: E402


MODULES_DIR = ROOT / "pct" / "data" / "legal_knowledge_base_modules"
DEFAULT_ARTIFACTS_DIR = ROOT / "artifacts" / "guida-pratica"


@dataclass(frozen=True)
class ConversionRule:
    alias: str
    related_official_codes: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ExistingGuidanceDuplicate:
    canonical_code: str
    title: str
    reason: str


CONVERSION_RULES: dict[str, ConversionRule] = {
    "140011": ConversionRule(
        "GUIDA_GARANZIA_VIZI_COSA_VENDUTA_140011",
        ("140011", "140012", "140999"),
        "Il codice 140011 è ufficiale nel catalogo locale per vendita di cose immobili; la scheda ricevuta riguarda la garanzia per vizi della cosa venduta in senso più ampio. Resta guida interna per non sostituire la denominazione ministeriale del deposito.",
    ),
    "160021": ConversionRule(
        "GUIDA_RESPONSABILITA_COSE_CUSTODIA_160021",
        ("145013", "145999"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda viene conservata come guida interna per responsabilità da cose in custodia e collegata ai codici di responsabilità extracontrattuale pertinenti.",
    ),
    "130011": ConversionRule(
        "GUIDA_DISTANZE_LEGALI_COSTRUZIONI_130011",
        ("130001", "130041", "130111", "130131"),
        "Il codice 130011 è ufficiale nel catalogo locale, ma riguarda la superficie; la scheda ricevuta riguarda distanze legali tra costruzioni e rapporti di vicinato, quindi resta interna per non alterare il deposito.",
    ),
    "211001": ConversionRule(
        "GUIDA_SCIOGLIMENTO_SOCIETA_PERSONE_211001",
        ("152004", "152999", "455001", "455999"),
        "Il codice 211001 è ufficiale nel catalogo locale, ma riguarda sequestro conservativo in area lavoro; la scheda ricevuta riguarda scioglimento giudiziale di società di persone e resta interna.",
    ),
    "413051": ConversionRule(
        "GUIDA_TUTELA_MAGGIORE_GRAVE_HANDICAP_413051",
        ("110001", "110002", "B02001", "C15001"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda viene conservata come guida interna per interdizione, inabilitazione e tutela del maggiore d'età.",
    ),
    "142001": ConversionRule(
        "GUIDA_RISOLUZIONE_MUTUO_DECADENZA_TERMINE_142001",
        ("140038", "140041", "140999"),
        "Il codice 142001 è ufficiale nel catalogo locale, ma riguarda prestazione d'opera intellettuale; la scheda ricevuta riguarda risoluzione del mutuo e decadenza dal beneficio del termine, quindi resta interna.",
    ),
    "199001": ConversionRule(
        "GUIDA_OPPOSIZIONE_PRECETTO_199001",
        ("100001",),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; esiste il codice ufficiale 100001 per opposizione a precetto ex art. 615, primo comma, c.p.c., da usare per il deposito se confermato.",
    ),
    "130070": ConversionRule(
        "GUIDA_DIVISIONE_COMUNIONE_ORDINARIA_130070",
        ("131011", "130001", "120011"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda la divisione della comunione ordinaria, mentre il deposito va scelto tra i codici ufficiali di divisione/diritti reali pertinenti.",
    ),
    "142005": ConversionRule(
        "GUIDA_NULLITA_CLAUSOLE_BANCARIE_ANATOCISMO_USURA_142005",
        ("140041", "143131", "010006", "050001"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda resta guida interna per contenzioso bancario, anatocismo, usura e restituzioni, senza sostituire i codici ufficiali bancari o finanziari.",
    ),
    "220050": ConversionRule(
        "GUIDA_MOBBING_STRAINING_DANNO_LAVORATORE_220050",
        ("220070", "220071", "220072", "220999"),
        "Il codice 220050 è ufficiale nel catalogo locale per retribuzione; la scheda ricevuta riguarda mobbing/straining e danni al lavoratore, quindi resta guida interna per non alterare il deposito.",
    ),
    "220120": ConversionRule(
        "GUIDA_APPRENDISTATO_RISOLUZIONE_CONVERSIONE_220120",
        ("220011", "221011", "222011", "220120", "221120", "222120"),
        "Il codice 220120 è ufficiale nel catalogo locale per dimissioni; la scheda ricevuta riguarda apprendistato, risoluzione e conversione del rapporto. Resta guida interna e propone i codici ufficiali apprendistato/dimissioni da valutare nel fascicolo.",
    ),
    "411603": ConversionRule(
        "GUIDA_AMMONIMENTO_QUESTORE_VIOLENZA_DOMESTICA_411603",
        ("111602", "411002", "411603", "B02023"),
        "Il codice 411603 è ufficiale nel catalogo locale per attuazione dei provvedimenti sull'affidamento; la scheda ricevuta riguarda ammonimento del questore, atti persecutori e violenza domestica. Resta guida interna e non sostituisce il codice ministeriale del deposito.",
    ),
    "140030": ConversionRule(
        "GUIDA_ASSICURAZIONE_INDENNIZZO_RISOLUZIONE_140030",
        ("140051", "140052", "010009", "140999"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda controversie assicurative e indennizzo e viene collegata ai codici ufficiali assicurativi pertinenti.",
    ),
    "121005": ConversionRule(
        "GUIDA_COLLAZIONE_EREDITARIA_121005",
        ("120011", "120001"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la collazione ereditaria viene conservata come guida interna collegata alla divisione ereditaria e alle impugnazioni successorie pertinenti.",
    ),
    "160040": ConversionRule(
        "GUIDA_RESPONSABILITA_MEDICO_SANITARIA_160040",
        ("012002", "142002", "145999"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda resta guida interna per responsabilità medico-sanitaria, da agganciare al codice ufficiale coerente con rito e domanda.",
    ),
    "143005": ConversionRule(
        "GUIDA_APPALTO_VIZI_DIFFORMITA_GARANZIA_143005",
        ("140022", "140021", "010025", "010026"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda appalto, vizi e garanzie, e resta separata dai codici ufficiali di appalto.",
    ),
    "130013": ConversionRule(
        "GUIDA_SERVITU_PREDIALI_130013",
        ("130041", "130001"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda servitù prediali e deve restare distinta dai codici ufficiali di diritti reali selezionabili nel fascicolo.",
    ),
    "414001": ConversionRule(
        "GUIDA_VOLONTARIA_GIURISDIZIONE_MINORI_AUTORIZZAZIONI_414001",
        ("413001", "413013", "413014", "B02031", "B02039", "B02041"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda viene conservata come guida interna per autorizzazioni e atti nell'interesse di minori.",
    ),
    "140005": ConversionRule(
        "GUIDA_DIFETTO_CONFORMITA_BENI_CONSUMO_140005",
        ("140011", "140012", "145021", "140999"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda resta guida interna per garanzia legale di conformità e vendita di beni di consumo.",
    ),
    "220005": ConversionRule(
        "GUIDA_LICENZIAMENTO_GMO_220005",
        ("220101", "220111", "220999"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; il licenziamento per giustificato motivo oggettivo ha codice ufficiale dedicato 220101 da valutare nel fascicolo.",
    ),
    "511020": ConversionRule(
        "GUIDA_ESECUZIONE_OBBLIGHI_FARE_NON_FARE_511020",
        ("512020", "512021", "512022"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda l'esecuzione di obblighi di fare/non fare, che nel catalogo locale ricade nell'area 512.",
    ),
    "412001": ConversionRule(
        "GUIDA_ADOZIONE_MAGGIORENNE_412001",
        ("111404", "411620", "411683"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; l'adozione di maggiorenne resta guida interna e il deposito va collegato al codice ufficiale coerente con ufficio e registro.",
    ),
    "123001": ConversionRule(
        "GUIDA_PETIZIONE_RECLAMO_STATO_FAMILIARE_123001",
        ("111101", "111102", "111402", "110999", "400240", "411681"),
        "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; la scheda riguarda stato familiare e filiazione e resta guida interna non depositabile.",
    ),
    "140035": ConversionRule(
        "GUIDA_ANNULLAMENTO_CONTRATTO_VIZI_CONSENSO_140035",
        ("140999", "140031", "140041"),
        "Il codice 140035 è ufficiale nel catalogo locale per agenzia; la scheda ricevuta riguarda annullamento del contratto per dolo, errore o violenza e resta guida interna per non alterare il deposito.",
    ),
    "143105": ConversionRule(
        "GUIDA_CONTRATTO_SUBFORNITURA_ABUSO_DIPENDENZA_ECONOMICA_143105",
        ("140021", "140022", "140999"),
        "Il codice 143105 è ufficiale nel catalogo locale per noleggio; la scheda ricevuta riguarda subfornitura e abuso di dipendenza economica. Resta guida interna non depositabile per non sostituire il modello ufficiale già presente.",
    ),
    "112001": ConversionRule(
        "GUIDA_FONDO_PATRIMONIALE_REVOCATORIA_112001",
        ("111214", "411640", "411679", "102002"),
        "Il codice 112001 è ufficiale nel catalogo locale come voce deprecata diversa; la scheda ricevuta riguarda fondo patrimoniale, opponibilità ai creditori e revocatoria. Resta guida interna e propone i codici ufficiali fondo patrimoniale/revocatoria da valutare nel fascicolo.",
    ),
    "151120": ConversionRule(
        "GUIDA_AZIONI_DI_CATEGORIA_SPA_ASSEMBLEA_SPECIALE_151120",
        ("151120",),
        "Il codice 151120 è ufficiale nel catalogo PST/XSD locale per rapporti sociali e cessione di partecipazioni; la scheda ricevuta riguarda in modo specifico azioni di categoria e assemblea speciale S.p.A. Resta guida interna collegata al codice ufficiale da valutare, senza sostituire l'oggetto ministeriale.",
    ),
    "211010": ConversionRule(
        "GUIDA_ARBITRATO_IRRITUALE_VALIDITA_IMPUGNAZIONE_211010",
        (),
        "Il codice 211010 è ufficiale nel catalogo PST/XSD locale per provvedimento d'urgenza ex art. 700 in area lavoro; la scheda ricevuta riguarda arbitrato irrituale ex art. 808-ter c.p.c. Resta guida interna non depositabile e non sostituisce il codice ministeriale.",
    ),
    "510100": ConversionRule(
        "GUIDA_ASSEGNAZIONE_CREDITO_PIGNORATO_ART_552_554_CPC_510100",
        ("510100",),
        "Il codice 510100 è ufficiale nel catalogo PST/XSD locale per deposito verbale di pagamento a mani dell'Ufficiale Giudiziario; la scheda ricevuta riguarda assegnazione del credito pignorato. Resta guida interna collegata al codice ufficiale da valutare, senza sostituire l'oggetto ministeriale.",
    ),
}


# Materiale ricevuto il 15/08/2026: la scheda 415120 ripete una guida gia'
# presente. Non va importata come seconda scheda perche' il testo in ingresso
# diverge anche su un presupposto operativo; la guida canonica resta l'unico
# punto di consultazione, con fonti e termini gia' governati.
EXISTING_GUIDANCE_DUPLICATES: dict[str, ExistingGuidanceDuplicate] = {
    "415120": ExistingGuidanceDuplicate(
        canonical_code="GUIDA_ESECUTORE_TESTAMENTARIO_NOMINA_POTERI_E_RESPONSABILIT_ARTT_700_712_C_C_415055",
        title="Esecutore testamentario: nomina, poteri e responsabilità (artt. 700-712 c.c.)",
        reason=(
            "La scheda ricevuta replica una guida interna già presente e contiene un contenuto "
            "divergente sulla durata del possesso. È mantenuta la sola guida canonica, da "
            "verificare sulle fonti collegate."
        ),
    ),
}

WEB_SOURCE_LIBRARY = SOURCE_LIBRARY

WEB_SOURCE_RULES: tuple[tuple[set[str], tuple[str, ...]], ...] = (
    ({"112001"}, ("normattiva_cc", "normattiva_cpc")),
    ({"120075"}, ("normattiva_l_47_2017_minori_stranieri", "normattiva_d_lgs_142_2015_accoglienza", "ministero_lavoro_minori_stranieri", "tribunale_minorenni_competenza")),
    ({"121022", "413130"}, ("normattiva_l_184_1983_adozione", "commissione_adozioni_internazionali", "tribunale_minorenni_competenza")),
    ({"413135"}, ("normattiva_dpr_396_2000_stato_civile", "normattiva_l_164_1982_rettificazione_sesso", "normattiva_l_218_1995")),
    ({"141080"}, ("eurlex_reg_2021_782_rail", "art_passeggeri_ferroviari")),
    ({"143115"}, ("normattiva_codice_assicurazioni", "ivass_arbitro_assicurativo", "normattiva_negoziazione_assistita")),
    ({"143120"}, ("normattiva_tuf", "consob_acf")),
    ({"145025"}, ("normattiva_locazioni_392", "normattiva_locazioni_431")),
    ({"152025"}, ("normattiva_d_lgs_14_2019", "unioncamere_composizione_negoziata")),
    ({"160250"}, ("eurlex_gdpr", "normattiva_privacy_196_2003", "garante_privacy_gdpr")),
    ({"160255"}, ("normattiva_l_219_2017", "normattiva_sanitaria")),
    ({"160260", "220250"}, ("normattiva_sicurezza_81_2008", "ministero_lavoro_dlgs_81_2008", "normattiva_tu_inail", "inail_infortunio_malattia_professionale")),
    ({"190040"}, ("eurlex_reg_805_2004_titolo_esecutivo_europeo", "eurlex_reg_1896_2006_ingiunzione_europea", "ejustice_ingiunzione_europea")),
    ({"199020"}, ("uncitral_new_york_convention", "normattiva_cpc")),
    ({"220255", "220265", "220270"}, ("normattiva_d_lgs_81_2015_lavoro", "normattiva_d_lgs_276_2003", "normattiva_lavoro_300", "normattiva_lavoro_604")),
    ({"220260"}, ("normattiva_l_335_1995_pensioni", "normattiva_dl_201_2011", "inps_ricorsi_amministrativi")),
    ({"240060"}, ("normattiva_codice_navigazione_327_1942", "normattiva_d_lgs_59_2010", "normattiva_l_241_1990", "normattiva_cpa_104_2010", "giustizia_amministrativa_provvedimenti")),
    ({"240065"}, ("normattiva_l_89_2001_pinto", "hudoc_cedu", "corte_costituzionale_pronunce", "cassazione_sentenzeweb")),
    ({"512125"}, ("normattiva_dpr_633_1972", "normattiva_dpr_600_1973")),
    ({"512130"}, ("normattiva_l_197_2022", "normattiva_l_130_2022", "agenzia_entrate_definizione_liti_197_2022", "giustizia_tributaria_banca_dati")),
    ({"512135"}, ("normattiva_dl_201_2011", "agenzia_entrate_ivie_ivafe_quadro_w", "normattiva_tuir_917_1986")),
    ({"130070", "121005", "140030", "142005", "160040", "130013", "143005", "140005"}, ("normattiva_mediazione",)),
    ({"140030", "142005", "143005", "160040", "140005"}, ("normattiva_negoziazione_assistita",)),
    ({"170001", "170002"}, ("normattiva_cpi",)),
    ({"160040"}, ("normattiva_sanitaria",)),
    ({"140005"}, ("normattiva_consumo",)),
    ({"142005"}, ("banca_italia_abf", "consob_acf")),
    ({"140030"}, ("ivass_arbitro_assicurativo",)),
    ({"140005"}, ("agcom_conciliaweb",)),
    ({"220005", "220050"}, ("normattiva_lavoro_604", "normattiva_lavoro_300")),
    ({"015011", "510001", "511012", "511020", "130070"}, ("normattiva_cpc",)),
    ({"511020"}, ("normattiva_614bis",)),
    (
        {
            "130070",
            "121005",
            "140030",
            "142005",
            "143005",
            "130013",
            "414001",
            "140005",
            "412001",
            "123001",
            "140011",
            "160021",
            "130011",
            "211001",
            "142001",
            "199001",
        },
        ("normattiva_cc",),
    ),
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_bytes(data: bytes) -> dict[str, Any]:
    payload = json.loads(data.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Il modulo Guida Pratica deve essere un oggetto JSON.")
    return payload


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _source_files(paths: Iterable[Path]) -> Iterable[tuple[str, bytes]]:
    for source in paths:
        if not source.exists():
            raise FileNotFoundError(source)
        if source.suffix.casefold() == ".zip":
            with zipfile.ZipFile(source) as archive:
                for info in sorted(archive.infolist(), key=lambda item: item.filename):
                    name = info.filename.replace("\\", "/")
                    if info.is_dir() or not name.endswith(".json"):
                        continue
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise ValueError(f"Percorso ZIP non sicuro: {info.filename}")
                    yield f"{source}::{name}", archive.read(info)
        else:
            yield str(source), source.read_bytes()


def _target_name(source_name: str) -> str:
    name = Path(source_name.split("::")[-1]).name
    if not name.startswith("kb_"):
        raise ValueError(f"Nome modulo non valido: {name}")
    if name.startswith("kb_98_"):
        return name
    return "kb_98_" + name.removeprefix("kb_")


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("codici_materia") or []:
        if isinstance(item, dict):
            rows.append(item)
    for section in payload.get("sezioni") or []:
        if not isinstance(section, dict):
            continue
        for item in section.get("codici_materia") or []:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _count_terms(payload: dict[str, Any]) -> int:
    return sum(len(item.get("termini_processuali") or []) for item in _items(payload) if isinstance(item.get("termini_processuali"), list))


def _normalized_title(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _existing_guidance_duplicate(item: dict[str, Any]) -> ExistingGuidanceDuplicate | None:
    original_code = normalize_codice_materia(
        item.get("codice_originale_ricevuto") or item.get("codice") or item.get("codice_logico") or item.get("codice_materia")
    )
    rule = EXISTING_GUIDANCE_DUPLICATES.get(original_code)
    if not rule:
        return None
    return rule if _normalized_title(item.get("denominazione")) == _normalized_title(rule.title) else None


def _convert_item(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    row = deepcopy(item)
    original_code = normalize_codice_materia(
        row.get("codice_originale_ricevuto") or row.get("codice") or row.get("codice_logico") or row.get("codice_materia")
    )
    if not original_code:
        return row, None, None
    rule = CONVERSION_RULES.get(original_code)
    if not rule and not codice_oggetto_pst_entry(original_code):
        if original_code.startswith("GUIDA_"):
            alias = original_code
        else:
            slug = re.sub(r"[^A-Z0-9]+", "_", str(row.get("denominazione") or original_code).upper()).strip("_")[:72]
            alias = f"GUIDA_{slug}_{original_code}"
        rule = ConversionRule(
            alias,
            tuple(str(code) for code in row.get("codici_ufficiali_correlati_da_valutare") or ()),
            "Codice ricevuto non presente nel catalogo PST/XSD ufficiale locale; conservato come guida interna non depositabile.",
        )
    if not rule:
        row["codice"] = original_code
        return row, None, original_code

    alias = normalize_codice_materia(rule.alias)
    row["codice_originale_ricevuto"] = original_code
    row["codice"] = alias
    row["codice_logico"] = alias
    row["guida_interna_non_depositabile"] = True
    row["depositabile"] = False
    row["codice_deposito_automatico"] = False
    row["codici_ufficiali_correlati_da_valutare"] = list(rule.related_official_codes)
    row["nota_integrazione_iusentra"] = rule.reason
    conversion = {
        "codice_originale": original_code,
        "codice_integrato": alias,
        "codici_ufficiali_correlati_da_valutare": list(rule.related_official_codes),
        "reason": rule.reason,
    }
    return row, conversion, None


def _source_entry(key: str, *, original_code: str) -> dict[str, str]:
    source = dict(WEB_SOURCE_LIBRARY[key])
    source["verificato_il"] = VERIFIED_ON
    source["metodo"] = "ricerca web su fonte ufficiale"
    source["codice_originale_guida"] = original_code
    return source


def _web_sources_for_item(original_code: str) -> list[dict[str, str]]:
    keys: list[str] = ["pst_download", "pst_xsd_sici_2024", "pst_specifiche_2014"]
    for codes, source_keys in WEB_SOURCE_RULES:
        if original_code in codes:
            keys.extend(source_keys)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        out.append(_source_entry(key, original_code=original_code))
    return out


def _attach_web_sources(item: dict[str, Any]) -> None:
    original_code = normalize_codice_materia(
        item.get("codice_originale_ricevuto") or item.get("codice") or item.get("codice_logico") or item.get("codice_materia")
    )
    if not original_code:
        return
    existing = item.get("fonti_verifica_web") if isinstance(item.get("fonti_verifica_web"), list) else []
    by_url = {str(source.get("url")): dict(source) for source in existing if isinstance(source, dict)}
    for source in [*_web_sources_for_item(original_code), *web_sources_for_guidance(item)]:
        by_url.setdefault(source["url"], source)
    item["fonti_verifica_web"] = list(by_url.values())


def _convert_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    converted = deepcopy(payload)
    original_codes: list[str] = []
    integrated_codes: list[str] = []
    conversions: list[dict[str, Any]] = []
    official_kept: list[str] = []
    existing_guidance_duplicates: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    for item in converted.get("codici_materia") or []:
        if not isinstance(item, dict):
            continue
        original_code = normalize_codice_materia(
            item.get("codice_originale_ricevuto") or item.get("codice") or item.get("codice_logico") or item.get("codice_materia")
        )
        if original_code:
            original_codes.append(original_code)
        new_item, conversion, official_code = _convert_item(item)
        duplicate = _existing_guidance_duplicate(new_item)
        if duplicate:
            existing_guidance_duplicates.append(
                {
                    "source_codice": original_code,
                    "denominazione": str(new_item.get("denominazione") or ""),
                    "canonical_code": duplicate.canonical_code,
                    "reason": duplicate.reason,
                }
            )
            continue
        _attach_web_sources(new_item)
        rows.append(new_item)
        integrated = normalize_codice_materia(new_item.get("codice"))
        if integrated:
            integrated_codes.append(integrated)
        if conversion:
            conversions.append(conversion)
        if official_code:
            official_kept.append(official_code)
    converted["codici_materia"] = rows
    report = {
        "macro_area_id": converted.get("macro_area_id") or (converted.get("macro_area") or {}).get("codice") or "",
        "denominazione": converted.get("denominazione") or "",
        "codici_materia_originali": original_codes,
        "codici_materia_integrati": integrated_codes,
        "conversioni_deposito": conversions,
        "codici_ufficiali_mantenuti_depositabili": official_kept,
        "deduplicati_su_guida_esistente": existing_guidance_duplicates,
        "termini_processuali_raw": sum(
            len(item.get("termini_processuali") or [])
            for item in rows
            if isinstance(item.get("termini_processuali"), list)
        ),
    }
    return converted, report


def _write_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    new_bytes = _json_bytes(payload)
    if path.exists():
        try:
            current = _read_json_bytes(path.read_bytes())
        except Exception:
            current = None
        if current == payload:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(new_bytes)
    return True


def import_sources(paths: Iterable[Path], *, modules_dir: Path = MODULES_DIR, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    duplicates_skipped: list[dict[str, str]] = []
    seen_hashes: dict[str, str] = {}
    official_kept: list[str] = []
    aliases: list[str] = []
    existing_guidance_duplicates: list[dict[str, str]] = []
    total_terms = 0
    for source_name, data in _source_files(paths):
        digest = _sha256(data)
        if digest in seen_hashes:
            duplicates_skipped.append(
                {
                    "source": source_name,
                    "duplicate_of": seen_hashes[digest],
                    "sha256": digest,
                }
            )
            continue
        seen_hashes[digest] = source_name
        payload = _read_json_bytes(data)
        converted, report = _convert_payload(payload)
        destination = modules_dir / _target_name(source_name)
        changed = _write_if_changed(destination, converted)
        file_report = {
            "source": source_name,
            "destination": str(destination.relative_to(ROOT)),
            "sha256": digest,
            "changed": changed,
            **report,
        }
        files.append(file_report)
        official_kept.extend(report["codici_ufficiali_mantenuti_depositabili"])
        aliases.extend(item["codice_integrato"] for item in report["conversioni_deposito"])
        existing_guidance_duplicates.extend(report["deduplicati_su_guida_esistente"])
        total_terms += int(report["termini_processuali_raw"])

        match = re.search(r"set(\d+)_(?:parte|p)(\d+)", destination.name)
        if match:
            dedicated = artifacts_dir / f"kb-set{match.group(1)}-parte{match.group(2)}-import-report.json"
            dedicated.parent.mkdir(parents=True, exist_ok=True)
            dedicated.write_text(json.dumps(file_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "generated_at": _utc_now(),
        "sources": [str(path) for path in paths],
        "files": files,
        "duplicates_skipped": duplicates_skipped,
        "records_received": sum(len(file["codici_materia_originali"]) for file in files),
        "records_integrated": sum(len(file["codici_materia_integrati"]) for file in files),
        "official_depositable_kept": sorted(set(official_kept)),
        "internal_non_depositable_aliases": sorted(set(aliases)),
        "deduplicati_su_guida_esistente": existing_guidance_duplicates,
        "termini_processuali_raw": total_terms,
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    set_ids = sorted({match.group(1) for file in files if (match := re.search(r"set(\d+)_(?:parte|p)", str(file.get("destination", ""))))})
    suffix = "set" + "-".join(set_ids) if set_ids else "import"
    (artifacts_dir / f"kb-{suffix}-structural-validation-report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa moduli Guida Pratica ricevuti dall'utente da JSON o ZIP.")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--modules-dir", type=Path, default=MODULES_DIR)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    summary = import_sources(args.sources, modules_dir=args.modules_dir, artifacts_dir=args.artifacts_dir)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
