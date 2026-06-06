from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pct.tariffario_catalogo import (
    tariffario_audit_rows,
    tariffario_fatturazione_rows,
    tariffario_option_rows,
    tariffario_profile_rows,
    tariffario_reference_rows,
    tariffario_rule_rows,
    tariffario_scaglioni_rows,
)

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
    monitor_urls: List[str] = field(default_factory=list)
    change_detection: str = "content_hash"

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
    "codice_deontologico_cnf": FonteOperativa(
        code="codice_deontologico_cnf",
        title="Codice Deontologico Forense - sito CNF",
        url="https://codicedeontologico-cnf.it/",
        note="Sito del Consiglio Nazionale Forense dedicato a codice deontologico, massime e aggiornamenti.",
        monitor_urls=[
            "https://codicedeontologico-cnf.it/nuovo-articolo-25-bis-cdf-con-tabella-di-confronto/",
            "https://codicedeontologico-cnf.it/tag/27-ncdf/",
        ],
        change_detection="content_hash",
    ),
    "cdf_art25bis_gazzetta_2026": FonteOperativa(
        code="cdf_art25bis_gazzetta_2026",
        title="G.U. n. 29/2026 - modifica art. 25-bis CDF",
        url=(
            "https://www.gazzettaufficiale.it/atto/vediMenuHTML?"
            "atto.codiceRedazionale=26A00480&atto.dataPubblicazioneGazzetta=2026-02-05"
            "&tipoSerie=serie_generale&tipoVigenza=originario"
        ),
        note="Comunicato CNF sulla delibera n. 959 del 23 gennaio 2026: art. 25-bis CDF in materia di equo compenso.",
    ),
    "cdf_modifiche_gazzetta_2025": FonteOperativa(
        code="cdf_modifiche_gazzetta_2025",
        title="G.U. n. 202/2025 - modifiche Codice Deontologico Forense",
        url=(
            "https://www.gazzettaufficiale.it/atto/vediMenuHTML?"
            "atto.codiceRedazionale=25A04804&atto.dataPubblicazioneGazzetta=2025-09-01"
            "&tipoSerie=serie_generale&tipoVigenza=originario"
        ),
        note="Comunicato CNF sulla delibera n. 636 del 21 marzo 2024: modifiche ad articoli 48, 50, 51, 56, 61, 62, 62-bis e Titolo IV CDF.",
    ),
    "cdf_circolare_1c_2026": FonteOperativa(
        code="cdf_circolare_1c_2026",
        title="CNF - circolare n. 1-C-2026 art. 25-bis CDF",
        url="https://www.ordineforense.re.it/wp-content/uploads/2026/04/N.-1-C-2026-Entrata-in-vigore-art.-25-bis-Codice-Deontologico-Forense.pdf",
        note="Circolare CNF dell'8 aprile 2026 sulla decorrenza e sull'ambito soggettivo del nuovo art. 25-bis CDF.",
        change_detection="availability_only",
    ),
    "registro_mediazione_portale": FonteOperativa(
        code="registro_mediazione_portale",
        title="Ministero della Giustizia - Registro organismi di mediazione",
        url="https://www.giustizia.it/giustizia/it/mg_3_4_15.page",
        note=(
            "Scheda ministeriale del registro organismi di mediazione, con rinvio al portale "
            "mediazione.giustizia.it e indicazioni ufficiali di consultazione."
        ),
    ),
    "registro_mediazione_diretto": FonteOperativa(
        code="registro_mediazione_diretto",
        title="Registro organismi di mediazione - consultazione diretta",
        url="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
        note=(
            "Consultazione diretta del registro ministeriale degli organismi di mediazione. "
            "La scheda ministeriale segnala che la consultazione puo richiedere Microsoft Edge "
            "in modalita compatibilita con Internet Explorer."
        ),
        change_detection="availability_only",
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
    "legge_forense_247_2012": FonteOperativa(
        code="legge_forense_247_2012",
        title="L. 247/2012 - legge professionale forense",
        url="https://www.gazzettaufficiale.it/eli/id/2013/01/18/13G00018/sg",
        note="Fonte primaria per incarico, informativa sul compenso e principi della professione forense.",
    ),
    "dm_55_2014_parametri": FonteOperativa(
        code="dm_55_2014_parametri",
        title="D.M. 55/2014 - parametri forensi",
        url=(
            "https://www.normattiva.it/atto/caricaDettaglioAtto?"
            "atto.codiceRedazionale=14G00067&atto.dataPubblicazioneGazzetta=2014-04-02"
            "&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=01%2F04%2F2026"
        ),
        note="Fonte primaria per parametri forensi, fasi e criteri di liquidazione.",
    ),
    "dm_147_2022_parametri": FonteOperativa(
        code="dm_147_2022_parametri",
        title="D.M. 147/2022 - aggiornamento parametri forensi",
        url=(
            "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
            "atto.codiceRedazionale=22G00157&atto.dataPubblicazioneGazzetta=2022-10-08"
            "&atto.tipoProvvedimento=DECRETO"
        ),
        note="Aggiornamento ufficiale dei parametri forensi e del bonus telematico.",
    ),
    "dm_150_2023_mediazione": FonteOperativa(
        code="dm_150_2023_mediazione",
        title="D.M. 150/2023 - organismi di mediazione",
        url=(
            "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
            "atto.codiceRedazionale=23G00163&atto.dataPubblicazioneGazzetta=2023-10-31"
            "&atto.tipoProvvedimento=DECRETO"
        ),
        note=(
            "Fonte primaria per spese di avvio, spese del primo incontro, Tabella A e "
            "maggiorazioni dei costi organismo mediazione dopo la riforma Cartabia."
        ),
    ),
    "equo_compenso_49_2023": FonteOperativa(
        code="equo_compenso_49_2023",
        title="L. 49/2023 - equo compenso",
        url=(
            "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
            "atto.codiceRedazionale=23G00051&atto.dataPubblicazioneGazzetta=2023-05-05"
            "&atto.tipoProvvedimento=LEGGE"
        ),
        note="Fonte primaria per il presidio dell'equo compenso.",
    ),
    "cassa_forense_art11": FonteOperativa(
        code="cassa_forense_art11",
        title="L. 576/1980 - contributo integrativo Cassa Forense",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1980-09-20%3B576",
        note="Base normativa del contributo integrativo Cassa Forense addebitabile al cliente.",
    ),
    "dpr_633_1972_art15": FonteOperativa(
        code="dpr_633_1972_art15",
        title="D.P.R. 633/1972 - art. 15",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1972-10-26%3B633",
        note="Fonte primaria per anticipazioni e spese vive escluse da imponibile IVA.",
    ),
    "dlgs_127_2015_fatturazione": FonteOperativa(
        code="dlgs_127_2015_fatturazione",
        title="D.Lgs. 127/2015 - fatturazione elettronica",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2015-08-05%3B127",
        note="Base normativa per fatturazione elettronica e Sistema di Interscambio.",
    ),
    "agenzia_entrate_fec": FonteOperativa(
        code="agenzia_entrate_fec",
        title="Agenzia delle Entrate - Fatturazione elettronica",
        url="https://www.agenziaentrate.gov.it/portale/aree-tematiche/fatturazione-elettronica",
        note="Portale ufficiale per predisposizione, trasmissione e consultazione delle fatture elettroniche.",
    ),
    "fatturapa_specifiche": FonteOperativa(
        code="fatturapa_specifiche",
        title="FatturaPA - tracciato XML ufficiale",
        url="https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf",
        note="Specifiche ufficiali del tracciato XML FPR12/FPA12 e controlli extra-schema.",
    ),
    "dpr_115_2002": FonteOperativa(
        code="dpr_115_2002",
        title="D.P.R. 115/2002 - art. 13 contributo unificato",
        url=(
            "https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?"
            "articolo=Articolo+13&codiceOrdinamento=0000000000000130000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            "&id=%7B79FB509F-FF10-413B-9949-D26DACEF6AAE%7D"
        ),
        note=(
            "Fonte ufficiale art. 13 DPR 115/2002: scaglioni CU, impugnazione +50%, Cassazione x2, "
            "sezioni specializzate x2, riduzioni e maggiorazioni per dati obbligatori mancanti."
        ),
        monitor_urls=[
            "https://www.normattiva.it/eli/id/2002/06/15/002G0139/CONSOLIDATED/20241015",
            "https://www.gazzettaufficiale.it/",
        ],
    ),
    "cu_viterbo": FonteOperativa(
        code="cu_viterbo",
        title="Portali uffici giudiziari - tabella contributo unificato civile",
        url="https://tribunale-matera.giustizia.it/it/contributo_unificato.page",
        note=(
            "Fonte pratica ufficiale di supporto per iscrizione a ruolo civile e decreti ingiuntivi, "
            "con mirror su portali uffici giudiziari."
        ),
        monitor_urls=["https://www.tribunale.viterbo.giustizia.it/it/Content/Index/58499"],
        change_detection="availability_only",
    ),
    "cu_admin": FonteOperativa(
        code="cu_admin",
        title="Giustizia Amministrativa - Carta dei servizi TAR Calabria",
        url="https://www.giustizia-amministrativa.it/documents/20142/17127638/T.A.R.%2BCalabria_sede%2Bdi%2BCatanzaro%2B-%2BCarta%2Bdei%2Bservizi%2B2022_QRcode.pdf/86de0520-27bb-2db2-733b-a58ac97df323?t=1671443142000",
        note="Importi ufficiali pubblicati per ricorsi ordinari, rito abbreviato, appalti e ottemperanza.",
        change_detection="availability_only",
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
        url="https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A06705&atto.dataPubblicazioneGazzetta=2025-12-13&tipoSerie=serie_generale&tipoVigenza=originario",
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
    # ── Banca d'Italia ──────────────────────────────────────────────────────
    "bancaditalia_portale": FonteOperativa(
        code="bancaditalia_portale",
        title="Banca d'Italia - portale ufficiale",
        url="https://www.bancaditalia.it/",
        note="Fonte primaria per tassi, usura, accertamenti bancari e normativa di settore.",
    ),
    "bancaditalia_tassi_usura": FonteOperativa(
        code="bancaditalia_tassi_usura",
        title="Banca d'Italia - TEGM e soglie antiusura",
        url="https://www.bancaditalia.it/compiti/vigilanza/compiti-vigilanza/tegm/",
        note=(
            "Pubblicazione trimestrale dei TEGM (Tassi Effettivi Globali Medi) e soglie antiusura "
            "ai sensi della L. 108/1996. I tassi soglia = TEGM × 1,25 + 4 punti percentuali. "
            "Rilevante per mutui, leasing, aperture di credito e prestiti personali."
        ),
        change_detection="availability_only",
    ),
    "mef_decreto_usura": FonteOperativa(
        code="mef_decreto_usura",
        title="MEF - rilevazione trimestrale tassi soglia usura",
        url="https://www.dt.mef.gov.it/it/attivita_istituzionali/sistema_bancario_finanziario/anti_usura/categorie_creditizie/",
        note="Sezione MEF Dipartimento del Tesoro con i decreti trimestrali TEGM e soglie antiusura per categoria di operazione.",
        change_detection="availability_only",
    ),
    "mef_tassi_usura_2026_q1": FonteOperativa(
        code="mef_tassi_usura_2026_q1",
        title="G.U. n. 302/2025 - tassi soglia usura Q1 2026",
        url=(
            "https://www.gazzettaufficiale.it/atto/vediMenuHTML?"
            "atto.codiceRedazionale=25A07045&atto.dataPubblicazioneGazzetta=2025-12-31"
            "&tipoSerie=serie_generale&tipoVigenza=originario"
        ),
        note=(
            "D.M. MEF 23 dicembre 2025: rilevazione 1 luglio - 30 settembre 2025, "
            "applicazione dal 1 gennaio al 31 marzo 2026."
        ),
        change_detection="content_hash",
    ),
    "mef_tassi_usura_2026_q2": FonteOperativa(
        code="mef_tassi_usura_2026_q2",
        title="G.U. n. 75/2026 - tassi soglia usura Q2 2026",
        url=(
            "https://www.gazzettaufficiale.it/atto/vediMenuHTML?"
            "atto.codiceRedazionale=26A01653&atto.dataPubblicazioneGazzetta=2026-03-31"
            "&tipoSerie=serie_generale&tipoVigenza=originario"
        ),
        note=(
            "D.M. MEF 27 marzo 2026: rilevazione 1 ottobre - 31 dicembre 2025, "
            "applicazione dal 1 aprile al 30 giugno 2026."
        ),
        change_detection="content_hash",
    ),
    # ── ISTAT ────────────────────────────────────────────────────────────────
    "istat_portale": FonteOperativa(
        code="istat_portale",
        title="ISTAT - portale ufficiale",
        url="https://www.istat.it/",
        note="Fonte primaria per indici dei prezzi al consumo, rivalutazioni monetarie e statistiche nazionali.",
    ),
    "istat_indici_prezzi": FonteOperativa(
        code="istat_indici_prezzi",
        title="ISTAT - indici dei prezzi al consumo (FOI e NIC)",
        url="https://www.istat.it/notizia/indice-dei-prezzi-per-le-rivalutazioni-monetarie/",
        note=(
            "Comunicati mensili ISTAT con indice FOI (famiglie di operai e impiegati, per adeguamento "
            "canoni di locazione ex L. 392/1978) e NIC (per rivalutazioni monetarie generali, assegni "
            "divorzili, liquidazioni). Aggiornati ogni mese intorno al 15. "
            "Dal gennaio 2026 base di riferimento 2025=100 (ECOICOP v2)."
        ),
        change_detection="availability_only",
    ),
    # ── Cassa Forense ────────────────────────────────────────────────────────
    "cassa_forense_portale": FonteOperativa(
        code="cassa_forense_portale",
        title="Cassa Forense - portale ufficiale",
        url="https://www.cassaforense.it/",
        note="Fonte primaria per contributi previdenziali avvocati, aliquote, minimali e comunicati annuali.",
    ),
    "cassa_forense_contributi_2026": FonteOperativa(
        code="cassa_forense_contributi_2026",
        title="Cassa Forense - contributi minimi obbligatori 2026",
        url="https://www.cassaforense.it/media/pkxmzmvw/tabella-contributi-minimi.pdf",
        note=(
            "Tabella ufficiale contributi minimi: per il 2026 contributo soggettivo minimo EUR 2.790, "
            "aliquota autoliquidazione 17%, contributo integrativo minimo EUR 355 con aliquota 4%; "
            "contributo maternita indicato come da definire nella tabella consultata."
        ),
        change_detection="availability_only",
    ),
    # ── Corte dei Conti ──────────────────────────────────────────────────────
    "corte_conti_portale": FonteOperativa(
        code="corte_conti_portale",
        title="Corte dei Conti - portale ufficiale",
        url="https://www.corteconti.it/",
        note="Fonte primaria per giurisprudenza contabile, sezioni regionali e sentenze su responsabilita erariale.",
    ),
    # ── Ministero del Lavoro ──────────────────────────────────────────────────
    "ministero_lavoro_portale": FonteOperativa(
        code="ministero_lavoro_portale",
        title="Ministero del Lavoro e delle Politiche Sociali - portale ufficiale",
        url="https://www.lavoro.gov.it/",
        note=(
            "Fonte primaria per CCNL, circolari lavoro, tutela minori, collocamento disabili "
            "e normativa previdenziale/assistenziale."
        ),
    ),
    # ── ANAC ─────────────────────────────────────────────────────────────────
    "anac_portale": FonteOperativa(
        code="anac_portale",
        title="ANAC - Autorita Nazionale Anticorruzione",
        url="https://www.anticorruzione.it/",
        note=(
            "Fonte primaria per appalti pubblici (D.Lgs. 36/2023 Codice dei Contratti), "
            "commissioni ANAC, bandi tipo e soglie di rilevanza comunitaria."
        ),
    ),
    "anac_soglie_2024": FonteOperativa(
        code="anac_soglie_2024",
        title="ANAC - soglie di rilevanza europea appalti 2024-2025",
        url="https://www.anticorruzione.it/",
        note=(
            "Soglie di rilevanza europea in vigore dal 1 gennaio 2024 (Reg. UE 2023/2469): "
            "lavori EUR 5.538.000, forniture/servizi PA centrale EUR 143.000, "
            "altre stazioni appaltanti EUR 221.000, enti aggiudicatori EUR 443.000. "
            "Scadute il 31 dicembre 2025 — sostituite dalle soglie 2026-2027."
        ),
    ),
    "anac_soglie_2026": FonteOperativa(
        code="anac_soglie_2026",
        title="ANAC - soglie di rilevanza europea appalti 2026-2027",
        url="https://www.anticorruzione.it/",
        note=(
            "Soglie di rilevanza europea in vigore dal 1 gennaio 2026 (Reg. UE 2025/2150, 2025/2151, 2025/2152): "
            "lavori EUR 5.404.000, forniture/servizi PA centrale EUR 140.000, "
            "altre stazioni appaltanti EUR 216.000, enti aggiudicatori EUR 432.000. "
            "Aggiornate ogni 2 anni dalla Commissione europea."
        ),
    ),
    # ── Senato ────────────────────────────────────────────────────────────────
    "senato_portale": FonteOperativa(
        code="senato_portale",
        title="Senato della Repubblica - portale ufficiale",
        url="https://www.senato.it/",
        note="Fonte per iter legislativo, disegni di legge, commissioni e testi approvati.",
    ),
    # ── Corte EDU / CEDU ─────────────────────────────────────────────────────
    "cedu_portale": FonteOperativa(
        code="cedu_portale",
        title="Corte europea dei diritti dell'uomo (CEDU)",
        url="https://www.echr.coe.int/",
        note=(
            "Fonte primaria per sentenze CEDU rilevanti per il diritto italiano (equo processo, "
            "liberta personale, privacy, proprieta). Ricerca in HUDOC: https://hudoc.echr.coe.int/"
        ),
    ),
    # ── Normativa antiusura (L. 108/1996) ────────────────────────────────────
    "legge_108_1996_usura": FonteOperativa(
        code="legge_108_1996_usura",
        title="L. 108/1996 - disciplina antiusura",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1996-03-07%3B108%21vig=",
        note="Base normativa per usura, soglie antiusura e criteri di determinazione dei TEGM.",
    ),
    # ── Normativa canoni di locazione ─────────────────────────────────────────
    "legge_431_1998_locazioni": FonteOperativa(
        code="legge_431_1998_locazioni",
        title="L. 431/1998 - locazioni abitative",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1998-12-09%3B431%21vig=",
        note="Disciplina delle locazioni ad uso abitativo con aggiornamento ISTAT FOI.",
    ),
    # ── Codice dei Contratti Pubblici ─────────────────────────────────────────
    "dlgs_36_2023_contratti": FonteOperativa(
        code="dlgs_36_2023_contratti",
        title="D.Lgs. 36/2023 - Codice dei contratti pubblici",
        url="https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2023-03-31%3B36%21vig=",
        note="Testo vigente del Codice dei contratti pubblici (in vigore dal 1 luglio 2023), rilevante per studi che assistono in appalti e concessioni.",
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
        ("codicedeontologico-cnf.it", "cnf"),
        ("mediazione.giustizia.it", "registro_mediazione"),
        ("mg_3_4_15.page", "registro_mediazione"),
        ("registro_organismi_mediazione", "registro_mediazione"),
        ("pst.giustizia.it", "pst_giustizia"),
        ("giustizia-amministrativa.it", "giustizia_amministrativa"),
        ("cortedicassazione.it", "cassazione"),
        ("cortecostituzionale.it", "corte_costituzionale"),
        ("eur-lex.europa.eu", "eur_lex"),
        ("fatturapa.gov.it", "fatturapa"),
        ("agenziaentrate.gov.it", "agenzia_entrate"),
        ("www1.agenziaentrate.gov.it", "agenzia_entrate"),
        ("inps.it", "gazzetta_ufficiale"),
        ("bancaditalia.it", "bancaditalia"),
        ("mef.gov.it", "bancaditalia"),
        ("istat.it", "istat"),
        ("cassaforense.it", "cassa_forense"),
        ("corteconti.it", "corte_conti"),
        ("lavoro.gov.it", "ministero_lavoro"),
        ("anticorruzione.it", "anac"),
        ("senato.it", "senato"),
        ("echr.coe.int", "cedu"),
        ("hudoc.echr.coe.int", "cedu"),
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
        "registro_mediazione": "registro_mediazione_portale",
        "pst_giustizia": "pst_portale",
        "giustizia_amministrativa": "giustizia_amministrativa_portale",
        "cassazione": "cassazione_portale",
        "corte_costituzionale": "corte_costituzionale_portale",
        "eur_lex": "eur_lex_portale",
        "agenzia_entrate": "agenzia_entrate_fec",
        "fatturapa": "fatturapa_specifiche",
        "bancaditalia": "bancaditalia_portale",
        "istat": "istat_portale",
        "cassa_forense": "cassa_forense_portale",
        "corte_conti": "corte_conti_portale",
        "ministero_lavoro": "ministero_lavoro_portale",
        "anac": "anac_portale",
        "senato": "senato_portale",
        "cedu": "cedu_portale",
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


USURA_CATEGORY_ALIASES = {
    "carte_credito_revolving": "credito_revolving",
    "factoring": "factoring_fino_50000",
}


def _normalize_usura_category(category: str) -> str:
    value = (category or "").strip()
    return USURA_CATEGORY_ALIASES.get(value, value)


def _tasso_usura_rows_2026() -> List[Dict[str, Any]]:
    labels = {
        "aperture_credito_cc_fino_5000": "Aperture di credito in conto corrente fino a EUR 5.000",
        "aperture_credito_cc_oltre_5000": "Aperture di credito in conto corrente oltre EUR 5.000",
        "scoperti_senza_affidamento_fino_1500": "Scoperti senza affidamento fino a EUR 1.500",
        "scoperti_senza_affidamento_oltre_1500": "Scoperti senza affidamento oltre EUR 1.500",
        "anticipi_sconti_crediti_fino_50000": "Anticipi su crediti e sconti fino a EUR 50.000",
        "anticipi_sconti_crediti_50000_200000": "Anticipi su crediti e sconti da EUR 50.000 a EUR 200.000",
        "anticipi_sconti_crediti_oltre_200000": "Anticipi su crediti e sconti oltre EUR 200.000",
        "credito_personale": "Credito personale",
        "credito_finalizzato": "Credito finalizzato",
        "factoring_fino_50000": "Factoring fino a EUR 50.000",
        "factoring_oltre_50000": "Factoring oltre EUR 50.000",
        "leasing_immobiliare_fisso": "Leasing immobiliare a tasso fisso",
        "leasing_immobiliare_variabile": "Leasing immobiliare a tasso variabile",
        "leasing_aeronavale_autoveicoli_fino_25000": "Leasing aeronavale e su autoveicoli fino a EUR 25.000",
        "leasing_aeronavale_autoveicoli_oltre_25000": "Leasing aeronavale e su autoveicoli oltre EUR 25.000",
        "leasing_strumentale_fino_25000": "Leasing strumentale fino a EUR 25.000",
        "leasing_strumentale_oltre_25000": "Leasing strumentale oltre EUR 25.000",
        "mutui_ipotecari_fisso": "Mutui con garanzia ipotecaria a tasso fisso",
        "mutui_ipotecari_variabile": "Mutui con garanzia ipotecaria a tasso variabile",
        "cessione_quinto_fino_15000": "Cessione del quinto fino a EUR 15.000",
        "cessione_quinto_oltre_15000": "Cessione del quinto oltre EUR 15.000",
        "credito_revolving": "Credito revolving",
        "carte_credito": "Finanziamenti con utilizzo di carte di credito",
        "altri_finanziamenti": "Altri finanziamenti",
    }
    quarters = [
        (
            "2026-Q1",
            "2026-01-01",
            "2026-03-31",
            "mef_tassi_usura_2026_q1",
            [
                ("aperture_credito_cc_fino_5000", 10.54, 17.1750),
                ("aperture_credito_cc_oltre_5000", 8.88, 15.1000),
                ("scoperti_senza_affidamento_fino_1500", 15.65, 23.5625),
                ("scoperti_senza_affidamento_oltre_1500", 15.74, 23.6750),
                ("anticipi_sconti_crediti_fino_50000", 8.05, 14.0625),
                ("anticipi_sconti_crediti_50000_200000", 6.51, 12.1375),
                ("anticipi_sconti_crediti_oltre_200000", 4.99, 10.2375),
                ("credito_personale", 11.46, 18.3250),
                ("credito_finalizzato", 11.03, 17.7875),
                ("factoring_fino_50000", 6.39, 11.9875),
                ("factoring_oltre_50000", 4.72, 9.9000),
                ("leasing_immobiliare_fisso", 5.77, 11.2125),
                ("leasing_immobiliare_variabile", 5.28, 10.6000),
                ("leasing_aeronavale_autoveicoli_fino_25000", 9.26, 15.5750),
                ("leasing_aeronavale_autoveicoli_oltre_25000", 8.20, 14.2500),
                ("leasing_strumentale_fino_25000", 9.88, 16.3500),
                ("leasing_strumentale_oltre_25000", 7.17, 12.9625),
                ("mutui_ipotecari_fisso", 3.96, 8.9500),
                ("mutui_ipotecari_variabile", 4.13, 9.1625),
                ("cessione_quinto_fino_15000", 13.73, 21.1625),
                ("cessione_quinto_oltre_15000", 9.46, 15.8250),
                ("credito_revolving", 15.77, 23.7125),
                ("carte_credito", 11.76, 18.7000),
                ("altri_finanziamenti", 14.54, 22.1750),
            ],
        ),
        (
            "2026-Q2",
            "2026-04-01",
            "2026-06-30",
            "mef_tassi_usura_2026_q2",
            [
                ("aperture_credito_cc_fino_5000", 10.53, 17.1625),
                ("aperture_credito_cc_oltre_5000", 8.86, 15.0750),
                ("scoperti_senza_affidamento_fino_1500", 15.76, 23.7000),
                ("scoperti_senza_affidamento_oltre_1500", 15.65, 23.5625),
                ("anticipi_sconti_crediti_fino_50000", 8.06, 14.0750),
                ("anticipi_sconti_crediti_50000_200000", 6.50, 12.1250),
                ("anticipi_sconti_crediti_oltre_200000", 4.97, 10.2125),
                ("credito_personale", 11.32, 18.1500),
                ("credito_finalizzato", 10.88, 17.6000),
                ("factoring_fino_50000", 6.41, 12.0125),
                ("factoring_oltre_50000", 4.66, 9.8250),
                ("leasing_immobiliare_fisso", 6.16, 11.7000),
                ("leasing_immobiliare_variabile", 5.43, 10.7875),
                ("leasing_aeronavale_autoveicoli_fino_25000", 9.24, 15.5500),
                ("leasing_aeronavale_autoveicoli_oltre_25000", 8.26, 14.3250),
                ("leasing_strumentale_fino_25000", 9.92, 16.4000),
                ("leasing_strumentale_oltre_25000", 7.21, 13.0125),
                ("mutui_ipotecari_fisso", 4.05, 9.0625),
                ("mutui_ipotecari_variabile", 4.08, 9.1000),
                ("cessione_quinto_fino_15000", 13.85, 21.3125),
                ("cessione_quinto_oltre_15000", 9.44, 15.8000),
                ("credito_revolving", 16.07, 24.0700),
                ("carte_credito", 11.57, 18.4625),
                ("altri_finanziamenti", 14.23, 21.7875),
            ],
        ),
    ]
    rows: List[Dict[str, Any]] = []
    for quarter, start, end, source_code, values in quarters:
        for category, tegm, soglia in values:
            rows.append(
                {
                    "quarter": quarter,
                    "start": start,
                    "end": end,
                    "category": category,
                    "tegm": tegm,
                    "soglia": soglia,
                    "label": labels[category],
                    "source_code": source_code,
                }
            )
    return rows


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
            "defaults": {
                "indeterminabile_amount": 518.0,
                "non_indicato_amount": 1686.0,
            },
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
            "defaults": {
                "indeterminabile_amount": 120.0,
                "non_indicato_amount": 1500.0,
            },
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
                {"category": "ricerca_beni_492bis", "amount": 43.0},
                {"category": "cittadinanza_italiana", "amount": 600.0},
                {"category": "esecuzione_immobiliare", "amount": 278.0},
                {"category": "altri_processi_esecutivi", "amount": 139.0},
                {"category": "esecuzione_mobiliare_sotto_2500", "amount": 43.0},
                {"category": "opposizione_atti_esecutivi", "amount": 168.0},
                {"category": "procedura_fallimentare", "amount": 851.0},
                {"category": "amministrativo_accesso_soggiorno_cittadinanza", "amount": 300.0},
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
        "registro_organismi_mediazione": {
            "id": "registro_organismi_mediazione",
            "title": "Registro organismi di mediazione",
            "category": "registri_ministeriali",
            "description": (
                "Metadata ufficiali del registro ministeriale degli organismi di mediazione, "
                "utili per verifiche operative, checklist ADR e preventivi."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["registro_mediazione_portale", "registro_mediazione_diretto"],
            "watch_source_ids": ["registro_mediazione"],
            "rows": [
                {
                    "registry_code": "rom",
                    "title": "Registro degli organismi di mediazione",
                    "official_info_url": "https://www.giustizia.it/giustizia/it/mg_3_4_15.page",
                    "official_registry_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                    "consultation_mode": "Microsoft Edge in modalita compatibilita con Internet Explorer",
                    "responsible_office": "Dipartimento per gli affari di giustizia - Reparto IV - Registri e Albi",
                    "support_email": "assistenza.mediazione.dgcivile.dag@giustizia.it",
                    "notes": (
                        "Scheda ministeriale aggiornata al 4 marzo 2026; il portale albi, registri ed elenchi "
                        "risulta aggiornato al 30 marzo 2026."
                    ),
                }
            ],
            "defaults": {"registry_kind": "organismi_mediazione"},
            "published_at": "2026-03-04",
            "effective_from": "2026-03-04",
        },
        "organismi_mediazione_elenco": {
            "id": "organismi_mediazione_elenco",
            "title": "Elenco organismi di mediazione italiani",
            "category": "registri_ministeriali",
            "description": (
                "Elenco consultabile degli organismi di mediazione italiani, sincronizzato quando "
                "il registro ministeriale diretto e disponibile."
            ),
            "strategy": "live_registry",
            "source_codes": ["registro_mediazione_portale", "registro_mediazione_diretto"],
            "watch_source_ids": ["registro_mediazione"],
            "rows": [],
            "defaults": {
                "registry_kind": "organismi_mediazione",
                "official_info_url": "https://www.giustizia.it/giustizia/it/mg_3_4_15.page",
                "official_registry_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                "consultation_mode": "Microsoft Edge in modalita compatibilita con Internet Explorer",
                "row_count": 0,
            },
            "published_at": "2026-03-04",
            "effective_from": "2026-03-04",
        },
        "mediazione_costi_odm_dm150": {
            "id": "mediazione_costi_odm_dm150",
            "title": "Mediazione civile - costi organismo D.M. 150/2023",
            "category": "adr_mediazione",
            "description": (
                "Scaglioni ufficiali per spese di avvio, spese del primo incontro e importi "
                "minimi Tabella A degli organismi di mediazione ex D.M. 150/2023."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["dm_150_2023_mediazione", "registro_mediazione_portale"],
            "watch_source_ids": ["gazzetta_ufficiale", "registro_mediazione"],
            "rows": [
                {
                    "from_value": 0.0,
                    "to_value": 1000.0,
                    "label": "Fino a EUR 1.000",
                    "spese_avvio": 40.0,
                    "spese_primo_incontro": 60.0,
                    "tabella_a_minimo": 80.0,
                },
                {
                    "from_value": 1000.01,
                    "to_value": 5000.0,
                    "label": "Da EUR 1.000,01 a EUR 5.000",
                    "spese_avvio": 75.0,
                    "spese_primo_incontro": 120.0,
                    "tabella_a_minimo": 160.0,
                },
                {
                    "from_value": 5000.01,
                    "to_value": 10000.0,
                    "label": "Da EUR 5.000,01 a EUR 10.000",
                    "spese_avvio": 75.0,
                    "spese_primo_incontro": 120.0,
                    "tabella_a_minimo": 290.0,
                },
                {
                    "from_value": 10000.01,
                    "to_value": 25000.0,
                    "label": "Da EUR 10.000,01 a EUR 25.000",
                    "spese_avvio": 75.0,
                    "spese_primo_incontro": 120.0,
                    "tabella_a_minimo": 440.0,
                },
                {
                    "from_value": 25000.01,
                    "to_value": 50000.0,
                    "label": "Da EUR 25.000,01 a EUR 50.000",
                    "spese_avvio": 75.0,
                    "spese_primo_incontro": 120.0,
                    "tabella_a_minimo": 720.0,
                },
                {
                    "from_value": 50000.01,
                    "to_value": 150000.0,
                    "label": "Da EUR 50.000,01 a EUR 150.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 1200.0,
                },
                {
                    "from_value": 150000.01,
                    "to_value": 250000.0,
                    "label": "Da EUR 150.000,01 a EUR 250.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 1500.0,
                },
                {
                    "from_value": 250000.01,
                    "to_value": 500000.0,
                    "label": "Da EUR 250.000,01 a EUR 500.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 2500.0,
                },
                {
                    "from_value": 500000.01,
                    "to_value": 1500000.0,
                    "label": "Da EUR 500.000,01 a EUR 1.500.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 3900.0,
                },
                {
                    "from_value": 1500000.01,
                    "to_value": 2500000.0,
                    "label": "Da EUR 1.500.000,01 a EUR 2.500.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 4600.0,
                },
                {
                    "from_value": 2500000.01,
                    "to_value": 5000000.0,
                    "label": "Da EUR 2.500.000,01 a EUR 5.000.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 6500.0,
                },
                {
                    "from_value": 5000000.01,
                    "to_value": None,
                    "label": "Oltre EUR 5.000.000",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo_rate_min": 0.002,
                    "tabella_a_minimo_rate_max": 0.003,
                },
                {
                    "from_value": 0.0,
                    "to_value": None,
                    "label": "Valore indeterminabile",
                    "kind": "indeterminabile",
                    "spese_avvio": 110.0,
                    "spese_primo_incontro": 170.0,
                    "tabella_a_minimo": 1200.0,
                },
            ],
            "defaults": {
                "regime_standard": "volontaria",
                "regime_ridotto": "obbligatoria_demandata",
                "riduzione_obbligatoria_multiplier": 0.8,
                "esito_primo_accordo_multiplier": 1.10,
                "esito_successivi_accordo_multiplier": 1.25,
                "maggiorazione_art31_comma3_multiplier": 1.20,
                "indeterminabile_reference_label": "Da EUR 50.000,01 a EUR 150.000",
            },
            "published_at": "2023-10-31",
            "effective_from": "2023-11-15",
        },
        "tariffario_forense_scaglioni": {
            "id": "tariffario_forense_scaglioni",
            "title": "Tariffario forense - scaglioni e tabelle",
            "category": "tariffario_forense",
            "description": "Scaglioni tabellari DM 55/2014 aggiornati dal DM 147/2022, distinti per tabella e fase.",
            "strategy": "seed_mirror",
            "source_codes": ["dm_55_2014_parametri", "dm_147_2022_parametri"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": tariffario_scaglioni_rows(),
            "published_at": "2022-10-08",
            "effective_from": "2022-10-23",
        },
        "tariffario_forense_profili": {
            "id": "tariffario_forense_profili",
            "title": "Tariffario forense - profili di calcolo",
            "category": "tariffario_forense",
            "description": "Profili operativi per materia, grado, fasi, coefficiente e pratica suggerita.",
            "strategy": "seed_mirror",
            "source_codes": ["dm_55_2014_parametri", "dm_147_2022_parametri", "legge_forense_247_2012", "equo_compenso_49_2023"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": tariffario_profile_rows(),
            "published_at": "2022-10-08",
            "effective_from": "2022-10-23",
        },
        "tariffario_forense_regole": {
            "id": "tariffario_forense_regole",
            "title": "Tariffario forense - regole tariffarie e competenza",
            "category": "tariffario_forense",
            "description": "Regole operative per materia, competenza, grado e pratica guidata condivise tra tariffario e preventivi.",
            "strategy": "seed_mirror",
            "source_codes": ["dm_55_2014_parametri", "dm_147_2022_parametri", "legge_forense_247_2012", "equo_compenso_49_2023"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": tariffario_rule_rows(),
            "published_at": "2026-04-02",
            "effective_from": "2026-04-02",
        },
        "tariffario_forense_audit": {
            "id": "tariffario_forense_audit",
            "title": "Tariffario forense - audit di conformita",
            "category": "tariffario_forense",
            "description": "Audit strutturato delle regole tariffarie con stato di copertura, snapshot e note di verifica.",
            "strategy": "seed_mirror",
            "source_codes": ["dm_55_2014_parametri", "dm_147_2022_parametri", "legge_forense_247_2012", "equo_compenso_49_2023"],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": tariffario_audit_rows(),
            "published_at": "2026-04-02",
            "effective_from": "2026-04-02",
        },
        "tariffario_forense_opzioni": {
            "id": "tariffario_forense_opzioni",
            "title": "Tariffario forense - opzioni compenso",
            "category": "tariffario_forense",
            "description": "Opzioni compenso e componenti fiscali riusabili in tariffario, preventivi e parcelle.",
            "strategy": "seed_mirror",
            "source_codes": [
                "dm_55_2014_parametri",
                "dm_147_2022_parametri",
                "cassa_forense_art11",
                "dpr_633_1972_art15",
                "equo_compenso_49_2023",
            ],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale"],
            "rows": tariffario_option_rows(),
            "published_at": "2022-10-08",
            "effective_from": "2022-10-23",
        },
        "tariffario_forense_riferimenti": {
            "id": "tariffario_forense_riferimenti",
            "title": "Tariffario forense - riferimenti ufficiali",
            "category": "tariffario_forense",
            "description": "Catalogo dei riferimenti normativi ufficiali utilizzati dal tariffario e dal flusso economico.",
            "strategy": "seed_mirror",
            "source_codes": [
                "legge_forense_247_2012",
                "dm_55_2014_parametri",
                "dm_147_2022_parametri",
                "equo_compenso_49_2023",
                "cassa_forense_art11",
                "dpr_633_1972_art15",
                "dlgs_127_2015_fatturazione",
                "agenzia_entrate_fec",
                "fatturapa_specifiche",
            ],
            "watch_source_ids": ["normattiva", "gazzetta_ufficiale", "agenzia_entrate", "fatturapa"],
            "rows": tariffario_reference_rows(),
            "published_at": "2026-04-01",
            "effective_from": "2026-04-01",
        },
        "tariffario_forense_fatturazione": {
            "id": "tariffario_forense_fatturazione",
            "title": "Tariffario forense - canali fatturazione",
            "category": "tariffario_forense",
            "description": "Canali operativi che collegano il tariffario a preventivi, parcelle e fatturazione elettronica.",
            "strategy": "seed_mirror",
            "source_codes": ["legge_forense_247_2012", "dlgs_127_2015_fatturazione", "agenzia_entrate_fec", "fatturapa_specifiche"],
            "watch_source_ids": ["normattiva", "agenzia_entrate", "fatturapa"],
            "rows": tariffario_fatturazione_rows(),
            "published_at": "2026-04-01",
            "effective_from": "2026-04-01",
        },
        # ── Tassi usura ───────────────────────────────────────────────────────
        "tasso_usura": {
            "id": "tasso_usura",
            "title": "Tassi usura - soglie antiusura trimestrali",
            "category": "tassi",
            "description": (
                "Soglie antiusura trimestrali per categoria di operazione, calcolate come TEGM × 1,25 + 4 pp "
                "ai sensi della L. 108/1996. Aggiornate trimestralmente da MEF/Banca d'Italia e pubblicate "
                "in Gazzetta Ufficiale. Rilevanti per mutui, leasing, aperture di credito, prestiti personali "
                "e valutazione di nullita di clausole contrattuali per usura."
            ),
            "strategy": "seed_mirror",
            "source_codes": [
                "legge_108_1996_usura",
                "bancaditalia_tassi_usura",
                "mef_decreto_usura",
                "mef_tassi_usura_2026_q1",
                "mef_tassi_usura_2026_q2",
            ],
            "watch_source_ids": ["bancaditalia", "gazzetta_ufficiale"],
            "rows": _tasso_usura_rows_2026(),
            "defaults": {
                "note": (
                    "Soglia = TEGM x 1,25 + 4 punti percentuali, con differenza massima "
                    "di 8 punti tra limite e tasso medio (L. 108/1996 come modificata "
                    "dal D.L. 70/2011). Dati Q1/Q2 2026 letti dagli allegati ufficiali "
                    "ai decreti MEF in Gazzetta Ufficiale. Aggiornare ogni trimestre da "
                    "https://www.bancaditalia.it/compiti/vigilanza/compiti-vigilanza/tegm/ "
                    "e relativo decreto MEF in "
                    "https://www.dt.mef.gov.it/it/attivita_istituzionali/sistema_bancario_finanziario/anti_usura/categorie_creditizie/"
                ),
                "formula": "soglia = tegm * 1.25 + 4",
                "aggiornamento": "trimestrale",
            },
            "published_at": "2026-03-31",
            "effective_from": "2026-01-01",
        },
        # ── Tassi BCE ─────────────────────────────────────────────────────────
        "tasso_bce": {
            "id": "tasso_bce",
            "title": "Tassi BCE - operazioni di rifinanziamento principali",
            "category": "tassi",
            "description": (
                "Tassi di interesse BCE sulle operazioni di rifinanziamento principali. "
                "Rilevanti per il calcolo degli interessi moratori ex D.Lgs. 231/2002 "
                "e per la valutazione di clausole di indicizzazione."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["bancaditalia_portale"],
            "watch_source_ids": ["bancaditalia", "gazzetta_ufficiale"],
            "rows": [
                {"start": "2024-06-12", "end": "2024-09-17", "rate": 4.25,
                 "label": "BCE operazioni principali rifinanziamento — dal 12/06/2024"},
                {"start": "2024-09-18", "end": "2024-10-22", "rate": 3.65,
                 "label": "BCE operazioni principali rifinanziamento — dal 18/09/2024"},
                {"start": "2024-10-23", "end": "2024-12-17", "rate": 3.40,
                 "label": "BCE operazioni principali rifinanziamento — dal 23/10/2024"},
                {"start": "2024-12-18", "end": "2025-01-29", "rate": 3.15,
                 "label": "BCE operazioni principali rifinanziamento — dal 18/12/2024"},
                {"start": "2025-01-30", "end": "2025-03-05", "rate": 2.90,
                 "label": "BCE operazioni principali rifinanziamento — dal 30/01/2025"},
                {"start": "2025-03-06", "end": "2025-04-16", "rate": 2.65,
                 "label": "BCE operazioni principali rifinanziamento — dal 06/03/2025"},
                {"start": "2025-04-17", "end": "2025-06-10", "rate": 2.40,
                 "label": "BCE operazioni principali rifinanziamento — dal 17/04/2025"},
                {"start": "2025-06-11", "end": None, "rate": 2.15,
                 "label": "BCE operazioni principali rifinanziamento — dal 11/06/2025"},
            ],
            "defaults": {
                "note": (
                    "Tasso BCE sulle operazioni di rifinanziamento principali. "
                    "Aggiornare dopo ogni decisione del Consiglio direttivo BCE "
                    "da https://www.bancaditalia.it/compiti/politica-monetaria/tassi-interesse/"
                ),
                "aggiornamento": "variabile (decisioni BCE)",
            },
            "published_at": "2025-06-11",
            "effective_from": "2024-06-12",
        },
        # ── ISTAT FOI ─────────────────────────────────────────────────────────
        "istat_foi": {
            "id": "istat_foi",
            "title": "ISTAT - Indice FOI (famiglie di operai e impiegati)",
            "category": "indici_rivalutazione",
            "description": (
                "Indice ISTAT dei prezzi al consumo per le famiglie di operai e impiegati (FOI), "
                "al netto dei tabacchi. Utilizzato per l'aggiornamento dei canoni di locazione "
                "ad uso abitativo (L. 431/1998 e L. 392/1978) e per adeguamenti contrattuali. "
                "Comunicato mensile ISTAT — aggiornato ogni mese intorno al 15."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["istat_indici_prezzi", "legge_431_1998_locazioni"],
            "watch_source_ids": ["istat", "normattiva"],
            "rows": [
                # Indici FOI (base 2015=100) — anno su anno
                {"year": 2023, "month": 1, "index": 118.6, "variation_yoy": 10.7},
                {"year": 2023, "month": 2, "index": 119.2, "variation_yoy": 9.7},
                {"year": 2023, "month": 3, "index": 119.6, "variation_yoy": 8.3},
                {"year": 2023, "month": 4, "index": 119.9, "variation_yoy": 8.5},
                {"year": 2023, "month": 5, "index": 120.2, "variation_yoy": 8.0},
                {"year": 2023, "month": 6, "index": 120.2, "variation_yoy": 6.7},
                {"year": 2023, "month": 7, "index": 120.9, "variation_yoy": 6.3},
                {"year": 2023, "month": 8, "index": 121.1, "variation_yoy": 5.5},
                {"year": 2023, "month": 9, "index": 120.9, "variation_yoy": 5.3},
                {"year": 2023, "month": 10, "index": 120.9, "variation_yoy": 1.8},
                {"year": 2023, "month": 11, "index": 120.6, "variation_yoy": 0.7},
                {"year": 2023, "month": 12, "index": 120.7, "variation_yoy": 0.6},
                {"year": 2024, "month": 1, "index": 120.8, "variation_yoy": 0.2},
                {"year": 2024, "month": 2, "index": 121.0, "variation_yoy": 0.7},
                {"year": 2024, "month": 3, "index": 121.2, "variation_yoy": 1.3},
                {"year": 2024, "month": 4, "index": 121.5, "variation_yoy": 0.9},
                {"year": 2024, "month": 5, "index": 121.7, "variation_yoy": 0.8},
                {"year": 2024, "month": 6, "index": 121.7, "variation_yoy": 0.9},
                {"year": 2024, "month": 7, "index": 122.1, "variation_yoy": 1.0},
                {"year": 2024, "month": 8, "index": 122.0, "variation_yoy": 1.2},
                {"year": 2024, "month": 9, "index": 122.1, "variation_yoy": 0.8},
                {"year": 2024, "month": 10, "index": 122.4, "variation_yoy": 0.9},
                {"year": 2024, "month": 11, "index": 122.5, "variation_yoy": 1.5},
                {"year": 2024, "month": 12, "index": 122.8, "variation_yoy": 1.7},
                {"year": 2025, "month": 1, "index": 123.2, "variation_yoy": 2.0},
                {"year": 2025, "month": 2, "index": 123.4, "variation_yoy": 2.0},
                {"year": 2025, "month": 3, "index": 123.3, "variation_yoy": 1.7},
            ],
            "defaults": {
                "base_year": 2015,
                "note": (
                    "Indice base 2015=100, al netto dei tabacchi. "
                    "Aggiornare mensilmente con i dati ISTAT da "
                    "https://www.istat.it/it/prezzi/prezzi-al-consumo/"
                ),
                "aggiornamento": "mensile",
            },
            "published_at": "2025-04-15",
            "effective_from": "2023-01-01",
        },
        # ── ISTAT NIC ─────────────────────────────────────────────────────────
        "istat_nic": {
            "id": "istat_nic",
            "title": "ISTAT - Indice NIC (prezzi al consumo per l'intera collettivita nazionale)",
            "category": "indici_rivalutazione",
            "description": (
                "Indice ISTAT NIC dei prezzi al consumo per l'intera collettivita nazionale, "
                "comprensivo dei tabacchi. Utilizzato per rivalutazione monetaria generale, "
                "assegni divorzili (L. 898/1970), liquidazioni, pensioni e adeguamenti contrattuali. "
                "Comunicato mensile ISTAT — aggiornato ogni mese."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["istat_indici_prezzi"],
            "watch_source_ids": ["istat"],
            "rows": [
                {"year": 2023, "month": 1, "index": 118.9, "variation_yoy": 11.6},
                {"year": 2023, "month": 2, "index": 119.5, "variation_yoy": 9.8},
                {"year": 2023, "month": 3, "index": 119.9, "variation_yoy": 8.3},
                {"year": 2023, "month": 4, "index": 120.3, "variation_yoy": 8.7},
                {"year": 2023, "month": 5, "index": 120.6, "variation_yoy": 7.6},
                {"year": 2023, "month": 6, "index": 120.6, "variation_yoy": 6.4},
                {"year": 2023, "month": 7, "index": 121.3, "variation_yoy": 6.0},
                {"year": 2023, "month": 8, "index": 121.5, "variation_yoy": 5.4},
                {"year": 2023, "month": 9, "index": 121.4, "variation_yoy": 5.3},
                {"year": 2023, "month": 10, "index": 121.4, "variation_yoy": 1.8},
                {"year": 2023, "month": 11, "index": 121.2, "variation_yoy": 0.7},
                {"year": 2023, "month": 12, "index": 121.3, "variation_yoy": 0.6},
                {"year": 2024, "month": 1, "index": 121.4, "variation_yoy": 0.8},
                {"year": 2024, "month": 2, "index": 121.6, "variation_yoy": 0.8},
                {"year": 2024, "month": 3, "index": 121.8, "variation_yoy": 1.2},
                {"year": 2024, "month": 4, "index": 122.1, "variation_yoy": 0.9},
                {"year": 2024, "month": 5, "index": 122.3, "variation_yoy": 0.8},
                {"year": 2024, "month": 6, "index": 122.3, "variation_yoy": 0.9},
                {"year": 2024, "month": 7, "index": 122.7, "variation_yoy": 1.1},
                {"year": 2024, "month": 8, "index": 122.7, "variation_yoy": 1.1},
                {"year": 2024, "month": 9, "index": 122.8, "variation_yoy": 0.7},
                {"year": 2024, "month": 10, "index": 123.1, "variation_yoy": 0.9},
                {"year": 2024, "month": 11, "index": 123.3, "variation_yoy": 1.5},
                {"year": 2024, "month": 12, "index": 123.6, "variation_yoy": 1.4},
                {"year": 2025, "month": 1, "index": 124.1, "variation_yoy": 2.2},
                {"year": 2025, "month": 2, "index": 124.3, "variation_yoy": 2.2},
                {"year": 2025, "month": 3, "index": 124.2, "variation_yoy": 1.9},
            ],
            "defaults": {
                "base_year": 2015,
                "note": (
                    "Indice base 2015=100. Aggiornare mensilmente con i dati ISTAT da "
                    "https://www.istat.it/it/prezzi/prezzi-al-consumo/"
                ),
                "aggiornamento": "mensile",
            },
            "published_at": "2025-04-15",
            "effective_from": "2023-01-01",
        },
        # ── Contributi Cassa Forense ───────────────────────────────────────────
        "contributi_cassa_forense": {
            "id": "contributi_cassa_forense",
            "title": "Contributi Cassa Forense",
            "category": "previdenza",
            "description": (
                "Aliquote e minimali contributivi Cassa Forense per anno. "
                "Comprende: contributo soggettivo (% sul reddito netto), contributo integrativo "
                "(% sui compensi, addebitabile al cliente ex L. 576/1980), contributo di maternita "
                "e assistenza. Fonte ufficiale: comunicati annuali Cassa Forense."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["cassa_forense_portale", "cassa_forense_contributi_2026", "cassa_forense_art11"],
            "watch_source_ids": ["cassa_forense", "gazzetta_ufficiale"],
            "rows": [
                {
                    "year": 2025,
                    "tipo": "soggettivo",
                    "aliquota": 15.0,
                    "minimo_eur": 2625.0,
                    "base": "reddito_netto_professionale",
                    "label": "Contributo soggettivo 2025",
                    "note": "Aliquota 15% sul reddito netto professionale. Minimo EUR 2.625.",
                },
                {
                    "year": 2025,
                    "tipo": "integrativo",
                    "aliquota": 4.0,
                    "minimo_eur": 700.0,
                    "base": "compensi_lordi",
                    "label": "Contributo integrativo 2025",
                    "note": "4% sui compensi lordi fatturati, addebitabile al cliente ex L. 576/1980. Minimo EUR 700.",
                },
                {
                    "year": 2025,
                    "tipo": "maternita_assistenza",
                    "aliquota": 0.0,
                    "minimo_eur": 183.0,
                    "base": "importo_fisso",
                    "label": "Contributo maternita/assistenza 2025",
                    "note": "Importo fisso EUR 183 annuo.",
                },
                {
                    "year": 2026,
                    "tipo": "soggettivo",
                    "aliquota": 17.0,
                    "minimo_eur": 2790.0,
                    "base": "reddito_netto_professionale",
                    "label": "Contributo soggettivo 2026",
                    "note": "Aliquota 17% in autoliquidazione Mod. 5. Minimo EUR 2.790 secondo tabella ufficiale Cassa Forense.",
                },
                {
                    "year": 2026,
                    "tipo": "integrativo",
                    "aliquota": 4.0,
                    "minimo_eur": 355.0,
                    "base": "compensi_lordi",
                    "label": "Contributo integrativo 2026",
                    "note": "4% sui compensi lordi fatturati, addebitabile al cliente ex L. 576/1980. Minimo EUR 355 secondo tabella ufficiale Cassa Forense.",
                },
                {
                    "year": 2026,
                    "tipo": "maternita_assistenza",
                    "aliquota": 0.0,
                    "minimo_eur": 0.0,
                    "status": "da_definire",
                    "base": "importo_fisso",
                    "label": "Contributo maternita/assistenza 2026",
                    "note": "Importo da definire nella tabella ufficiale Cassa Forense consultata: non usare come importo definitivo.",
                },
            ],
            "defaults": {
                "note": (
                    "Aggiornare annualmente con la circolare Cassa Forense da "
                    "https://www.cassaforense.it/media/pkxmzmvw/tabella-contributi-minimi.pdf"
                ),
                "aggiornamento": "annuale",
            },
            "published_at": "2025-12-01",
            "effective_from": "2025-01-01",
        },
        # ── Soglie appalti pubblici (ANAC) ────────────────────────────────────
        "soglie_appalti_anac": {
            "id": "soglie_appalti_anac",
            "title": "Soglie di rilevanza europea - appalti pubblici",
            "category": "appalti_pubblici",
            "description": (
                "Soglie di rilevanza europea per contratti pubblici di lavori, servizi e forniture "
                "ai sensi del D.Lgs. 36/2023 (Codice dei Contratti Pubblici). "
                "Aggiornate ogni due anni dalla Commissione europea con regolamento delegato UE. "
                "Rilevanti per studi che assistono imprese in gare pubbliche, concessioni e appalti."
            ),
            "strategy": "seed_mirror",
            "source_codes": ["anac_portale", "anac_soglie_2024", "anac_soglie_2026", "dlgs_36_2023_contratti"],
            "watch_source_ids": ["anac", "eur_lex", "gazzetta_ufficiale"],
            "rows": [
                # Soglie 2024-2025 (Reg. UE 2023/2469) — scadute il 31/12/2025
                {"category": "lavori", "threshold_eur": 5538000.0,
                 "start": "2024-01-01", "end": "2025-12-31",
                 "label": "Lavori - soglia rilevanza europea 2024-2025",
                 "note": "Art. 14 co. 1 lett. a D.Lgs. 36/2023 — Reg. UE 2023/2469"},
                {"category": "forniture_servizi_pa_centrale", "threshold_eur": 143000.0,
                 "start": "2024-01-01", "end": "2025-12-31",
                 "label": "Forniture e servizi - PA centrale 2024-2025",
                 "note": "Art. 14 co. 1 lett. b D.Lgs. 36/2023 — Reg. UE 2023/2469"},
                {"category": "forniture_servizi_altre_sa", "threshold_eur": 221000.0,
                 "start": "2024-01-01", "end": "2025-12-31",
                 "label": "Forniture e servizi - altre stazioni appaltanti 2024-2025",
                 "note": "Art. 14 co. 1 lett. c D.Lgs. 36/2023 — Reg. UE 2023/2469"},
                {"category": "forniture_servizi_enti_aggiudicatori", "threshold_eur": 443000.0,
                 "start": "2024-01-01", "end": "2025-12-31",
                 "label": "Forniture e servizi - enti aggiudicatori 2024-2025",
                 "note": "Art. 114 co. 1 D.Lgs. 36/2023 — Reg. UE 2023/2469"},
                {"category": "concessioni", "threshold_eur": 5538000.0,
                 "start": "2024-01-01", "end": "2025-12-31",
                 "label": "Concessioni di lavori e servizi 2024-2025",
                 "note": "Art. 177 co. 1 D.Lgs. 36/2023 — Reg. UE 2023/2469"},
                # Soglie 2026-2027 (Reg. UE 2025/2150, 2025/2151, 2025/2152) — in vigore dal 01/01/2026
                {"category": "lavori", "threshold_eur": 5404000.0,
                 "start": "2026-01-01", "end": None,
                 "label": "Lavori - soglia rilevanza europea 2026-2027",
                 "note": "Art. 14 co. 1 lett. a D.Lgs. 36/2023 — Reg. UE 2025/2150"},
                {"category": "forniture_servizi_pa_centrale", "threshold_eur": 140000.0,
                 "start": "2026-01-01", "end": None,
                 "label": "Forniture e servizi - PA centrale 2026-2027",
                 "note": "Art. 14 co. 1 lett. b D.Lgs. 36/2023 — Reg. UE 2025/2151"},
                {"category": "forniture_servizi_altre_sa", "threshold_eur": 216000.0,
                 "start": "2026-01-01", "end": None,
                 "label": "Forniture e servizi - altre stazioni appaltanti 2026-2027",
                 "note": "Art. 14 co. 1 lett. c D.Lgs. 36/2023 — Reg. UE 2025/2151"},
                {"category": "forniture_servizi_enti_aggiudicatori", "threshold_eur": 432000.0,
                 "start": "2026-01-01", "end": None,
                 "label": "Forniture e servizi - enti aggiudicatori 2026-2027",
                 "note": "Art. 114 co. 1 D.Lgs. 36/2023 — Reg. UE 2025/2152"},
                {"category": "concessioni", "threshold_eur": 5404000.0,
                 "start": "2026-01-01", "end": None,
                 "label": "Concessioni di lavori e servizi 2026-2027",
                 "note": "Art. 177 co. 1 D.Lgs. 36/2023 — Reg. UE 2025/2150"},
                # Servizi sociali (soglia nazionale, invariata)
                {"category": "servizi_sociali", "threshold_eur": 750000.0,
                 "start": "2024-01-01", "end": None,
                 "label": "Servizi sociali e specifici",
                 "note": "Art. 14 co. 6 D.Lgs. 36/2023 — soglia nazionale invariata"},
                # Sotto-soglia ANAC (affidamenti diretti / procedure negoziate — soglie nazionali, invariate)
                {"category": "affidamento_diretto_lavori", "threshold_eur": 150000.0,
                 "start": "2024-01-01", "end": None,
                 "label": "Affidamento diretto - lavori",
                 "note": "Art. 50 co. 1 lett. a D.Lgs. 36/2023"},
                {"category": "affidamento_diretto_forniture_servizi", "threshold_eur": 140000.0,
                 "start": "2024-01-01", "end": None,
                 "label": "Affidamento diretto - forniture e servizi",
                 "note": "Art. 50 co. 1 lett. b D.Lgs. 36/2023"},
            ],
            "defaults": {
                "note": (
                    "Soglie vigenti dal 1 gennaio 2026 (Reg. UE 2025/2150-2152). "
                    "Aggiornare ogni 2 anni con il regolamento delegato UE e comunicato ANAC da "
                    "https://www.anticorruzione.it/"
                ),
                "aggiornamento": "biennale",
            },
            "published_at": "2026-01-01",
            "effective_from": "2026-01-01",
        },
    }
    reference_definition = canonical_reference_catalog_definition()
    definitions[reference_definition["id"]] = reference_definition
    return definitions


class GestioneTabelleNormative:
    def __init__(self, db_path: str = "./intelligence/tabelle_normative.json"):
        self.db_path = db_path
        self._data: Dict[str, Any] = {"tables": {}, "sync_runs": [], "source_checks": {}}
        self._load()
        self._ensure_seeded()

    def _load(self) -> None:
        from pct import cache as _cache
        try:
            raw = _cache.load(self.db_path, default={})
            self._data["tables"] = dict(raw.get("tables") or {})
            self._data["sync_runs"] = list(raw.get("sync_runs") or [])
            self._data["source_checks"] = dict(raw.get("source_checks") or {})
        except Exception:
            self._data = {"tables": {}, "sync_runs": [], "source_checks": {}}

    def _save(self) -> None:
        from pct import cache as _cache
        # indent=None: file fino a 6 MB, non serve leggibilità umana
        _cache.save(self.db_path, self._data, indent=None)

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

    def _build_dynamic_version_payload(
        self,
        *,
        table_id: str,
        rows: Iterable[Mapping[str, Any]],
        now: datetime,
        label: str = "",
        effective_from: str = "",
        published_at: str = "",
        notes: Optional[Iterable[str]] = None,
        origin: str = "sync",
    ) -> Dict[str, Any]:
        normalized_rows = [dict(row) for row in rows or []]
        data_hash = _json_hash(normalized_rows)
        return {
            "id": f"{table_id}:{(effective_from or now.date().isoformat())}:{data_hash[:12]}",
            "label": label or f"Aggiornamento {now.date().isoformat()}",
            "created_at": _now_iso(now),
            "effective_from": effective_from or now.date().isoformat(),
            "effective_to": "",
            "published_at": published_at,
            "acquired_at": _now_iso(now),
            "status": "active",
            "origin": origin,
            "data_hash": data_hash,
            "rows": normalized_rows,
            "notes": list(notes or []),
        }

    def _build_table_payload(
        self,
        definition: Mapping[str, Any],
        now: datetime,
        *,
        created: bool = False,
    ) -> Dict[str, Any]:
        version = self._build_version_payload(definition, now, origin="bootstrap" if created else "sync")
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
            "rows": list(version.get("rows") or []),
            "versions": [version],
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

    def source_checks(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._data.get("source_checks") or {})

    def relevant_source_codes(self, source_ids: Optional[Iterable[str]] = None) -> List[str]:
        watched_ids = set(source_ids or [])
        rows: List[str] = []
        for definition in canonical_table_definitions().values():
            watch_source_ids = set(definition.get("watch_source_ids") or [])
            if watched_ids and not (watch_source_ids & watched_ids):
                continue
            for code in definition.get("source_codes") or []:
                if code not in rows:
                    rows.append(code)
        return rows

    def get_table(self, table_id: str, on_date: Optional[date] = None) -> Dict[str, Any]:
        table = self._data.get("tables", {}).get(table_id)
        if not table:
            raise KeyError(f"Tabella normativa non trovata: {table_id}")
        active = self._active_version(table, on_date=on_date)
        definition = canonical_table_definitions().get(table_id) or {}
        merged_defaults = dict(definition.get("defaults") or {})
        merged_defaults.update(table.get("defaults") or {})
        return {
            "id": table["id"],
            "title": table.get("title", table_id),
            "category": table.get("category", ""),
            "description": table.get("description", ""),
            "strategy": table.get("strategy", ""),
            "defaults": merged_defaults,
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

    def update_table_rows(
        self,
        table_id: str,
        rows: Iterable[Mapping[str, Any]],
        *,
        now: Optional[datetime] = None,
        published_at: str = "",
        effective_from: str = "",
        label: str = "",
        notes: Optional[Iterable[str]] = None,
        defaults: Optional[Mapping[str, Any]] = None,
        sync_status: str = "sincronizzata",
        warning: str = "",
        origin: str = "sync",
        source_changed: bool = False,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        definitions = canonical_table_definitions()
        definition = definitions.get(table_id)
        table = self._data.setdefault("tables", {}).get(table_id)
        if table is None:
            if definition is None:
                raise KeyError(f"Tabella normativa non trovata: {table_id}")
            table = self._build_table_payload(definition, current_time, created=True)
            self._data["tables"][table_id] = table

        normalized_rows = [dict(row) for row in rows or []]
        new_version = self._build_dynamic_version_payload(
            table_id=table_id,
            rows=normalized_rows,
            now=current_time,
            label=label,
            effective_from=effective_from,
            published_at=published_at,
            notes=notes,
            origin=origin,
        )
        active = self._active_version(table)
        changed = not active or active.get("data_hash") != new_version.get("data_hash")
        if changed:
            for version in table.get("versions") or []:
                if version.get("status") == "active":
                    version["status"] = "superseded"
                    version["effective_to"] = effective_from or current_time.date().isoformat()
            table.setdefault("versions", []).append(new_version)

        if defaults is not None:
            table["defaults"] = dict(defaults)
        elif table.get("defaults") is None:
            table["defaults"] = {}
        table["rows"] = normalized_rows
        table["sync_status"] = sync_status
        table["last_warning"] = warning
        table["last_synced_at"] = _now_iso(current_time)
        if source_changed:
            table["last_source_change_at"] = _now_iso(current_time)
        self._save()
        return {
            "table_id": table_id,
            "updated": changed,
            "rows": len(normalized_rows),
            "sync_status": sync_status,
            "warning": warning,
        }

    def set_table_sync_status(
        self,
        table_id: str,
        *,
        sync_status: str,
        warning: str = "",
        now: Optional[datetime] = None,
        source_changed: bool = False,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        table = self._data.setdefault("tables", {}).get(table_id)
        if table is None:
            definition = canonical_table_definitions().get(table_id)
            if definition is None:
                raise KeyError(f"Tabella normativa non trovata: {table_id}")
            table = self._build_table_payload(definition, current_time, created=True)
            self._data["tables"][table_id] = table
        table["sync_status"] = sync_status
        table["last_warning"] = warning
        table["last_synced_at"] = _now_iso(current_time)
        if source_changed:
            table["last_source_change_at"] = _now_iso(current_time)
        self._save()
        return {
            "table_id": table_id,
            "sync_status": sync_status,
            "warning": warning,
        }

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

    def tariffario_scaglioni(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_scaglioni")

    def tariffario_profili(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_profili")

    def tariffario_regole(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_regole")

    def tariffario_audit(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_audit")

    def tariffario_opzioni(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_opzioni")

    def tariffario_riferimenti(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_riferimenti")

    def tariffario_fatturazione(self) -> List[Dict[str, Any]]:
        return self.rows("tariffario_forense_fatturazione")

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

    # ── Helper: Cassa Forense ────────────────────────────────────────────────

    def cassa_forense_aliquota_integrativa(self, year: Optional[int] = None) -> float:
        """Aliquota contributo integrativo Cassa Forense per l'anno indicato (default: anno corrente).
        Restituisce la percentuale (es. 4.0 per il 4%).
        Fallback: 4.0% se tabella non disponibile."""
        try:
            rows = self.rows("contributi_cassa_forense")
            target_year = year or date.today().year
            candidates = [r for r in rows if int(r.get("year", 0)) == target_year and r.get("tipo") == "integrativo"]
            if not candidates:
                candidates = [r for r in rows if r.get("tipo") == "integrativo"]
                if candidates:
                    candidates.sort(key=lambda r: int(r.get("year", 0)), reverse=True)
            if candidates:
                return float(candidates[0].get("aliquota", 4.0))
        except Exception:
            pass
        return 4.0

    def cassa_forense_minimo_integrativo(self, year: Optional[int] = None) -> float:
        """Minimo del contributo integrativo Cassa Forense per l'anno. Fallback: 700."""
        try:
            rows = self.rows("contributi_cassa_forense")
            target_year = year or date.today().year
            candidates = [r for r in rows if int(r.get("year", 0)) == target_year and r.get("tipo") == "integrativo"]
            if not candidates:
                candidates = [r for r in rows if r.get("tipo") == "integrativo"]
                if candidates:
                    candidates.sort(key=lambda r: int(r.get("year", 0)), reverse=True)
            if candidates:
                return float(candidates[0].get("minimo_eur", 700.0))
        except Exception:
            pass
        return 700.0

    def contributi_cassa_forense_anno(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tutti i contributi Cassa Forense per l'anno indicato."""
        try:
            rows = self.rows("contributi_cassa_forense")
            target_year = year or date.today().year
            candidates = [r for r in rows if int(r.get("year", 0)) == target_year]
            if candidates:
                return candidates
            # Ultimo anno disponibile
            candidates = sorted(rows, key=lambda r: int(r.get("year", 0)), reverse=True)
            if candidates:
                max_year = int(candidates[0].get("year", 0))
                return [r for r in candidates if int(r.get("year", 0)) == max_year]
        except Exception:
            pass
        return []

    # ── Helper: ISTAT ────────────────────────────────────────────────────────

    def istat_index(self, kind: str, year: int, month: int) -> Optional[float]:
        """Indice ISTAT (FOI o NIC) per il mese indicato. Restituisce None se non disponibile."""
        table_id = "istat_foi" if kind == "foi" else "istat_nic"
        try:
            for row in self.rows(table_id):
                if int(row.get("year", 0)) == year and int(row.get("month", 0)) == month:
                    return float(row["index"])
        except Exception:
            pass
        return None

    def istat_last_available(self, kind: str) -> Optional[Dict[str, Any]]:
        """Ultimo indice ISTAT disponibile nella tabella."""
        table_id = "istat_foi" if kind == "foi" else "istat_nic"
        try:
            rows = self.rows(table_id)
            if rows:
                return max(rows, key=lambda r: (int(r.get("year", 0)), int(r.get("month", 0))))
        except Exception:
            pass
        return None

    def istat_variation_yoy(self, kind: str, year: int, month: int) -> Optional[float]:
        """Variazione annua % ISTAT per il mese indicato."""
        table_id = "istat_foi" if kind == "foi" else "istat_nic"
        try:
            for row in self.rows(table_id):
                if int(row.get("year", 0)) == year and int(row.get("month", 0)) == month:
                    return float(row.get("variation_yoy", 0.0))
        except Exception:
            pass
        return None

    # ── Helper: Tassi usura ───────────────────────────────────────────────────

    def usura_categorie(self) -> List[Dict[str, Any]]:
        """Elenco categorie di credito con TEGM e soglia usura (dati più recenti per ogni categoria)."""
        try:
            rows = self.rows("tasso_usura")
            if not rows:
                return []
            # Prendi il quarter più recente
            latest_quarter = max(rows, key=lambda r: r.get("quarter", ""), default=None)
            if not latest_quarter:
                return []
            quarter = latest_quarter["quarter"]
            return [r for r in rows if r.get("quarter") == quarter]
        except Exception:
            return []

    def usura_soglia_per_categoria(self, category: str, on_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Soglia usura per la categoria e data indicata."""
        try:
            category = _normalize_usura_category(category)
            rows = self.rows("tasso_usura")
            if not rows:
                return None
            target = on_date or date.today()
            # Filtra per data
            valid = [
                r for r in rows
                if r.get("category") == category
                and (_parse_date(r.get("start")) or date.min) <= target
                and (not r.get("end") or (_parse_date(r.get("end")) or date.max) >= target)
            ]
            if valid:
                return valid[0]
            # Fallback al più recente per categoria
            candidates = [r for r in rows if r.get("category") == category]
            if candidates:
                return max(candidates, key=lambda r: r.get("quarter", ""))
        except Exception:
            pass
        return None

    # ── Helper: Tassi BCE ─────────────────────────────────────────────────────

    def tasso_bce(self, on_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Tasso BCE operazioni principali di rifinanziamento per la data indicata."""
        try:
            rows = self.rows("tasso_bce")
            if not rows:
                return None
            target = on_date or date.today()
            valid = [
                r for r in rows
                if (_parse_date(r.get("start")) or date.min) <= target
                and (not r.get("end") or (_parse_date(r.get("end")) or date.max) >= target)
            ]
            if valid:
                return valid[0]
            # Più recente
            return max(rows, key=lambda r: r.get("start", ""))
        except Exception:
            pass
        return None

    def sync_from_canonical(
        self,
        *,
        source_runs: Optional[Mapping[str, Any]] = None,
        source_code_runs: Optional[Mapping[str, Any]] = None,
        source_ids: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        watched_ids = set(source_ids or [])
        definitions = canonical_table_definitions()
        source_runs = dict(source_runs or {})
        source_code_runs = dict(source_code_runs or {})
        if source_code_runs:
            self._data.setdefault("source_checks", {}).update(source_code_runs)

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
                    version = self._build_version_payload(definition, current_time, origin="sync")
                    table.setdefault("versions", []).append(version)
                    table["rows"] = list(version.get("rows") or [])
                    updated += 1
                    table_changed = True
                elif "rows" not in table:
                    table["rows"] = list(active_version.get("rows") or [])

            relevant_runs = {
                source_id: source_runs[source_id]
                for source_id in definition.get("watch_source_ids") or []
                if source_id in source_runs
            }
            relevant_code_runs = {
                code: source_code_runs[code]
                for code in definition.get("source_codes") or []
                if code in source_code_runs
            }
            use_specific_sources = bool(source_code_runs) and bool(definition.get("source_codes") or [])
            changed_codes = [code for code, run in relevant_code_runs.items() if bool((run or {}).get("changed"))]
            failed_codes = [code for code, run in relevant_code_runs.items() if str((run or {}).get("status", "")) not in {"", "ok"}]
            changed_sources = [source_id for source_id, run in relevant_runs.items() if bool((run or {}).get("changed"))]
            failed_sources = [source_id for source_id, run in relevant_runs.items() if str((run or {}).get("status", "")) not in {"", "ok"}]
            effective_changed = changed_codes if use_specific_sources else changed_sources
            effective_failed = failed_codes if use_specific_sources else failed_sources
            if effective_failed:
                source_labels = [
                    (FONTI_OPERATIVE.get(code).title if code in FONTI_OPERATIVE else code)
                    for code in effective_failed
                ]
                if not use_specific_sources:
                    source_labels = list(effective_failed)
                table["sync_status"] = "fonte_non_raggiungibile"
                table["last_warning"] = f"Fonte monitorata non raggiungibile: {', '.join(source_labels)}."
                warnings.append({"table_id": table_id, "warning": table["last_warning"]})
            elif effective_changed and not table_changed:
                source_labels = [
                    (FONTI_OPERATIVE.get(code).title if code in FONTI_OPERATIVE else code)
                    for code in effective_changed
                ]
                if not use_specific_sources:
                    source_labels = list(effective_changed)
                table["sync_status"] = "verifica_richiesta"
                table["last_warning"] = (
                    "Fonte ufficiale specifica della tabella variata ma nessuna tabella strutturata e stata aggiornata automaticamente. "
                    f"Verificare: {', '.join(source_labels)}."
                )
                review_required += 1
                warnings.append({"table_id": table_id, "warning": table["last_warning"]})
            else:
                table["sync_status"] = "sincronizzata"
                table["last_warning"] = ""
            table["last_synced_at"] = _now_iso(current_time)
            if effective_changed:
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
