"""Arricchimento ufficiale e non bloccante della Guida Pratica.

Il modulo applica a tutte le schede, già curate o generate, lo stesso livello
di presidio che viene usato per i nuovi materiali dell'utente: fonti ufficiali,
canali ADR/specialistici, controllo deposito separato e note operative per Lex.
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

ENRICHMENT_VERSION = "2026-05-24.web-fonti-adr-v1"
VERIFIED_ON = "2026-05-24"

SOURCE_LIBRARY: dict[str, dict[str, str]] = {
    "pst_download": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Download file ufficiali del Processo Civile Telematico",
        "url": "https://pst.giustizia.it/PST/it/download.page",
        "ambito": "XSD SICI, XSD Giudici di pace, XSD Cassazione e file ufficiali PCT",
    },
    "pst_xsd_sici_2024": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "XSD SICI e codici oggetto migrazione famiglia - 23 gennaio 2024",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3094",
        "ambito": "schemi XSD SICI, tipi-base.xsd e codici oggetto PST",
    },
    "pst_specifiche_2014": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Provvedimento 16 aprile 2014 - specifiche tecniche ex art. 34 D.M. 44/2011",
        "url": "https://servizipst.giustizia.it/PST/it/pst_26_1.wp?contentId=DOC416&previousPage=pst_1_0",
        "ambito": "regole tecniche deposito telematico e rinvio ai file XSD ufficiali",
    },
    "normattiva_cpc": {
        "ente": "Normattiva",
        "titolo": "R.D. 28 ottobre 1940, n. 1443 - Codice di procedura civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=multivigenza",
        "ambito": "rito civile, cautelari, opposizioni, esecuzioni, famiglia, volontaria giurisdizione e impugnazioni",
    },
    "normattiva_cc": {
        "ente": "Normattiva",
        "titolo": "R.D. 16 marzo 1942, n. 262 - Codice civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=multivigenza",
        "ambito": "famiglia, successioni, diritti reali, contratti, responsabilità, società e persone",
    },
    "normattiva_mediazione": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 4 marzo 2010, n. 28, art. 5 - mediazione civile e commerciale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010;28~art5=",
        "ambito": "condizione di procedibilità e materie soggette a mediazione",
    },
    "normattiva_negoziazione_assistita": {
        "ente": "Normattiva",
        "titolo": "D.L. 12 settembre 2014, n. 132, art. 3 - negoziazione assistita",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2014;132~art3=",
        "ambito": "risarcimento da circolazione e domande di pagamento entro soglia, fuori dai casi di mediazione",
    },
    "normattiva_riforma_cartabia": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 ottobre 2022, n. 149 - riforma del processo civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17",
        "ambito": "rito civile, famiglia, esecuzione forzata, mediazione, negoziazione assistita e arbitrato",
    },
    "normattiva_614bis": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 ottobre 2022, n. 149 - modifica art. 614-bis c.p.c.",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=3&atto.articolo.sottoArticolo=1&atto.articolo.tipoArticolo=0&atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17",
        "ambito": "misure di coercizione indiretta e obblighi diversi dal pagamento di somme",
    },
    "normattiva_cpi": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 febbraio 2005, n. 30 - Codice della proprietà industriale",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente",
        "ambito": "marchi, brevetti, disegni, modelli, inibitoria, descrizione e sequestro CPI",
    },
    "normattiva_sanitaria": {
        "ente": "Normattiva",
        "titolo": "Legge 8 marzo 2017, n. 24 - responsabilità sanitaria",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017-03-08;24~art10-com2=",
        "ambito": "responsabilità sanitaria, assicurazione, rivalsa e regresso",
    },
    "normattiva_consumo": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 6 settembre 2005, n. 206 - Codice del consumo",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005;206!vig=",
        "ambito": "garanzia legale, difetto di conformità, clausole e tutele consumeristiche",
    },
    "normattiva_lavoro_604": {
        "ente": "Normattiva",
        "titolo": "Legge 15 luglio 1966, n. 604 - licenziamenti individuali",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=066U0604&atto.dataPubblicazioneGazzetta=1966-08-06",
        "ambito": "licenziamento, motivazione, impugnazione e giustificato motivo",
    },
    "normattiva_lavoro_300": {
        "ente": "Normattiva",
        "titolo": "Legge 20 maggio 1970, n. 300 - Statuto dei lavoratori",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1970;300~art35-com=",
        "ambito": "tutele del lavoratore e rinvii alla disciplina reintegratoria/organizzativa",
    },
    "banca_italia_abf": {
        "ente": "Banca d'Italia",
        "titolo": "Arbitro Bancario Finanziario",
        "url": "https://www.bancaditalia.it/compiti/tutela-educazione/abf/index.html",
        "ambito": "ADR per controversie bancarie e finanziarie con intermediari vigilati",
    },
    "consob_acf": {
        "ente": "CONSOB",
        "titolo": "Arbitro per le Controversie Finanziarie",
        "url": "https://www.consob.it/web/area-pubblica/arbitro-per-le-controversie-finanziarie",
        "ambito": "ADR per controversie finanziarie tra investitori e intermediari",
    },
    "ivass_arbitro_assicurativo": {
        "ente": "IVASS",
        "titolo": "Arbitro Assicurativo",
        "url": "https://www.ivass.it/consumatori/aas/index.html",
        "ambito": "ricorso assicurativo dopo reclamo all'impresa o all'intermediario",
    },
    "agcom_conciliaweb": {
        "ente": "AGCOM",
        "titolo": "ConciliaWeb",
        "url": "https://www.agcom.it/agcom-per-te/i-miei-diritti/contenzioso-tra-utenti-e-operatori",
        "ambito": "conciliazione e definizione controversie utenti/operatori comunicazioni elettroniche",
    },
    "ministero_patrocinio_spese_stato": {
        "ente": "Ministero della Giustizia",
        "titolo": "Patrocinio a spese dello Stato nei giudizi civili e amministrativi",
        "url": "https://www.giustizia.it/giustizia/page/it/patrocinio_a_spese_dello_stato_nei_giudizi_civili_e_amministrativi",
        "ambito": "verifica facoltativa dei presupposti di ammissione al patrocinio a spese dello Stato",
    },
    "ministero_pagopa_pst": {
        "ente": "Ministero della Giustizia",
        "titolo": "Contributo unificato e pagamenti telematici tramite PagoPA",
        "url": "https://www.giustizia.it/giustizia/it/mg_1_40_0.page?contentId=IGC408325&facetNode_2=0_23",
        "ambito": "pagamento telematico contributo unificato, diritti e spese nei procedimenti civili telematici",
    },
    "pst_servizi_pagopa": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Servizi telematici e pagamenti online tramite pagoPA",
        "url": "https://pst.giustizia.it/PST/it/services.page",
        "ambito": "punti di accesso, pagamenti online, consultazioni registri e servizi PCT",
    },
    "agenzia_entrate_tassazione_atti_giudiziari": {
        "ente": "Agenzia delle Entrate",
        "titolo": "Calcolo degli importi per la tassazione degli atti giudiziari",
        "url": "https://www1.agenziaentrate.gov.it/servizi/tassazioneattigiudiziari/registrazione.htm?passo=0",
        "ambito": "registrazione e tassazione di provvedimenti giudiziari",
    },
    "inail_infortunio_malattia_professionale": {
        "ente": "INAIL",
        "titolo": "Denunce di infortunio e malattia professionale",
        "url": "https://www.inail.it/portale/assicurazione/it/Datore-di-Lavoro/Impresa-con-dipendenti-industria-artigianato-terziario-altre-attivita/denunce-infortuni-e-malattie-professionali-impresa-con-dipendenti/denuncia-malattia-professionale-impresa-con-dipendenti.html",
        "ambito": "denuncia di infortunio, malattia professionale e presidi amministrativi collegati al lavoro",
    },
    "inps_ricorsi_amministrativi": {
        "ente": "INPS",
        "titolo": "Ricorsi amministrativi",
        "url": "https://www.inps.it/it/it/dettaglio-scheda.it.schede-servizio-strumento.schede-servizi.ricorsi-amministrativi.html",
        "ambito": "ricorsi amministrativi previdenziali e assistenziali prima o accanto al contenzioso",
    },
    "registro_imprese": {
        "ente": "Camera di Commercio",
        "titolo": "Registro delle imprese e adempimenti societari",
        "url": "https://www.vr.camcom.gov.it/content/il-registro-imprese",
        "ambito": "visure, assetti societari, scioglimento, liquidazione e pubblicità legale dell'impresa",
    },
    "tribunale_minorenni_competenza": {
        "ente": "Ministero della Giustizia - Tribunale per i Minorenni",
        "titolo": "Competenza per materia del Tribunale per i Minorenni",
        "url": "https://tribmin-trento.giustizia.it/it/comp_per_materia.page",
        "ambito": "competenza civile minorile, volontaria giurisdizione, adozione e tutela dei minori",
    },
    "procura_negoziazione_famiglia": {
        "ente": "Ministero della Giustizia - Procura della Repubblica",
        "titolo": "Nulla osta e autorizzazioni per negoziazione assistita in materia di famiglia",
        "url": "https://procura-roma.giustizia.it/it/nulla_osta_separaz_divorzi.page",
        "ambito": "separazione, divorzio e modifiche consensuali con negoziazione assistita",
    },
    "pst_albo_ctu": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Portale albo CTU, periti ed elenco nazionale",
        "url": "https://pst.giustizia.it/PST/it/services.page",
        "ambito": "consultazione consulenti tecnici e periti, utile per CTU/ATP e cause tecniche",
    },
    "normattiva_tu_spese_giustizia": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 30 maggio 2002, n. 115 - Testo unico spese di giustizia",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=002G0139&atto.dataPubblicazioneGazzetta=2002-06-15&tipoDettaglio=vigente",
        "ambito": "contributo unificato, spese di giustizia, patrocinio a spese dello Stato e prenotazioni a debito",
    },
    "normattiva_tu_bancario": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 1 settembre 1993, n. 385 - Testo unico bancario",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=093G0427&atto.dataPubblicazioneGazzetta=1993-09-30&tipoDettaglio=vigente",
        "ambito": "contratti bancari, mutui, credito, ABF e trasparenza bancaria",
    },
    "normattiva_tuf": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 24 febbraio 1998, n. 58 - Testo unico della finanza",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=098G0075&atto.dataPubblicazioneGazzetta=1998-03-26&tipoDettaglio=vigente",
        "ambito": "servizi di investimento, intermediari finanziari, obblighi informativi e ACF",
    },
    "normattiva_codice_assicurazioni": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 7 settembre 2005, n. 209 - Codice delle assicurazioni private",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0233&atto.dataPubblicazioneGazzetta=2005-10-13&tipoDettaglio=vigente",
        "ambito": "contratti assicurativi, sinistri, azioni dirette e reclami assicurativi",
    },
    "normattiva_tu_inail": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 30 giugno 1965, n. 1124 - Testo unico assicurazione infortuni sul lavoro",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=065U1124&atto.dataPubblicazioneGazzetta=1965-10-13&tipoDettaglio=vigente",
        "ambito": "infortuni sul lavoro, malattie professionali, denuncia e prestazioni INAIL",
    },
    "normattiva_codice_proprieta_industriale": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 febbraio 2005, n. 30 - Codice della proprietà industriale",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente",
        "ambito": "proprietà industriale, marchi, brevetti, disegni e modelli",
    },
}

SOURCE_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "processo civile e riforma Cartabia",
        ("rito", "ricorso", "citazione", "opposizione", "impugnazione", "cautel", "esecuzione", "volontaria"),
        ("normattiva_cpc", "normattiva_riforma_cartabia"),
    ),
    (
        "codice civile sostanziale",
        (
            "famiglia",
            "minori",
            "succession",
            "eredit",
            "divisione",
            "diritti reali",
            "contratto",
            "appalto",
            "vendita",
            "locazione",
            "responsabilità",
            "servit",
            "societ",
            "adozione",
            "stato",
        ),
        ("normattiva_cc",),
    ),
    (
        "mediazione civile",
        (
            "mediazione",
            "condominio",
            "diritti reali",
            "divisione",
            "succession",
            "patti di famiglia",
            "locazione",
            "comodato",
            "affitto",
            "responsabilità medica",
            "sanitaria",
            "diffamazione",
            "assicurativ",
            "bancari",
            "finanziari",
            "franchising",
            "consorzio",
            "subfornitura",
            "opera",
            "rete",
            "somministrazione",
            "società di persone",
        ),
        ("normattiva_mediazione",),
    ),
    (
        "negoziazione assistita",
        ("negoziazione", "circolazione", "veicoli", "natanti", "pagamento", "risarcimento", "somma", "indennizzo"),
        ("normattiva_negoziazione_assistita",),
    ),
    ("proprietà industriale", ("marchio", "brevetto", "disegno", "modello", "proprietà industriale"), ("normattiva_cpi", "normattiva_codice_proprieta_industriale")),
    ("responsabilità sanitaria", ("sanitaria", "medico", "struttura sanitaria", "malpractice"), ("normattiva_sanitaria",)),
    ("consumo", ("consumatore", "consumo", "conformità", "clausole vessatorie"), ("normattiva_consumo",)),
    ("lavoro", ("lavoro", "lavoratore", "licenziamento", "mobbing", "straining", "retribuzione", "demansionamento"), ("normattiva_lavoro_604", "normattiva_lavoro_300")),
    ("bancario", ("bancari", "bancario", "mutuo", "anatocismo", "usura", "conto corrente"), ("normattiva_tu_bancario", "banca_italia_abf")),
    ("finanziario", ("finanziari", "investimento", "intermediario finanziario", "tuf"), ("normattiva_tuf", "consob_acf")),
    ("assicurativo", ("assicurativ", "polizza", "sinistro", "indennizzo"), ("normattiva_codice_assicurazioni", "ivass_arbitro_assicurativo")),
    ("comunicazioni elettroniche", ("telefon", "telecomunicazioni", "conciliaweb", "operatore"), ("agcom_conciliaweb",)),
    ("obblighi di fare", ("obblighi di fare", "non fare", "614-bis", "coercizione indiretta", "astreinte"), ("normattiva_614bis",)),
    ("patrocinio a spese dello Stato", ("patrocinio", "spese dello stato", "gratuito patrocinio", "non abbiente"), ("normattiva_tu_spese_giustizia", "ministero_patrocinio_spese_stato")),
    ("pagamenti telematici e contributo unificato", ("contributo unificato", "pagopa", "diritti di cancelleria", "spese di giustizia"), ("normattiva_tu_spese_giustizia", "ministero_pagopa_pst", "pst_servizi_pagopa")),
    ("tassazione atti giudiziari", ("registrazione", "imposta di registro", "atti giudiziari", "agenzia entrate"), ("agenzia_entrate_tassazione_atti_giudiziari",)),
    ("infortuni e malattie professionali", ("infortunio", "malattia professionale", "inail"), ("normattiva_tu_inail", "inail_infortunio_malattia_professionale")),
    ("previdenza e assistenza", ("previdenza", "assistenziale", "inps", "invalidità", "pensione"), ("inps_ricorsi_amministrativi",)),
    ("societario e registro imprese", ("registro imprese", "liquidazione", "scioglimento societ", "visura", "camera di commercio"), ("registro_imprese",)),
    ("famiglia e minori", ("minore", "minori", "adozione", "responsabilità genitoriale", "tutela minore"), ("tribunale_minorenni_competenza",)),
    ("negoziazione assistita famiglia", ("separazione", "divorzio", "modifica condizioni", "negoziazione assistita famiglia"), ("procura_negoziazione_famiglia",)),
    ("consulenza tecnica", ("ctu", "ctp", "atp", "696-bis", "consulente tecnico", "perizia"), ("pst_albo_ctu",)),
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value).casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9_]+", " ", ascii_text).strip()


def _collect_text(value: Any, *, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(value, dict):
        return " ".join(_collect_text(item, depth=depth + 1) for item in value.values())
    if isinstance(value, list):
        return " ".join(_collect_text(item, depth=depth + 1) for item in value[:40])
    return _text(value)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_entry(key: str, *, matched_by: str) -> dict[str, str]:
    source = deepcopy(SOURCE_LIBRARY[key])
    source["verificato_il"] = VERIFIED_ON
    source["metodo"] = "ricerca web su fonte ufficiale"
    source["matched_by"] = matched_by
    return source


def _add_source(out: list[dict[str, str]], seen: set[str], key: str, *, matched_by: str) -> None:
    url = SOURCE_LIBRARY[key]["url"]
    if url in seen:
        return
    seen.add(url)
    out.append(_source_entry(key, matched_by=matched_by))


def web_sources_for_guidance(guidance: dict[str, Any]) -> list[dict[str, str]]:
    """Restituisce fonti ufficiali pertinenti per una scheda guida."""

    haystack = _fold(_collect_text(guidance))
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in ("pst_download", "pst_xsd_sici_2024", "pst_specifiche_2014"):
        _add_source(out, seen, key, matched_by="presidio catalogo PST/XSD e deposito")
    for label, tokens, source_keys in SOURCE_RULES:
        if any(_fold(token) in haystack for token in tokens):
            for key in source_keys:
                _add_source(out, seen, key, matched_by=label)
    if len(out) == 3:
        for key in ("normattiva_cpc", "normattiva_cc"):
            _add_source(out, seen, key, matched_by="presidio generale civile")
    return out


def _source_titles(sources: list[dict[str, str]]) -> list[str]:
    return [_text(source.get("titolo")) for source in sources if _text(source.get("titolo"))]


def _procedibilita_note(guidance: dict[str, Any], sources: list[dict[str, str]]) -> list[dict[str, str]]:
    titles = " ".join(_source_titles(sources)).casefold()
    notes: list[dict[str, str]] = []
    mediazione = guidance.get("obbligo_mediazione") or guidance.get("obbligo_mediazione_o_negoziazione_assistita")
    if mediazione or "mediazione" in titles:
        notes.append(
            {
                "presidio": "Mediazione civile",
                "azione": "Verifica se la materia richiede mediazione come condizione di procedibilità prima della domanda.",
                "fonte": "D.Lgs. 28/2010, art. 5",
            }
        )
    if "negoziazione assistita" in titles:
        notes.append(
            {
                "presidio": "Negoziazione assistita",
                "azione": "Controlla circolazione, pagamento somme e soglie prima di iscrivere la causa.",
                "fonte": "D.L. 132/2014, art. 3",
            }
        )
    if "arbitro bancario finanziario" in titles:
        notes.append(
            {
                "presidio": "ABF",
                "azione": "Valuta reclamo e ricorso ABF quando la controversia è bancaria o finanziaria non d'investimento.",
                "fonte": "Banca d'Italia",
            }
        )
    if "controversie finanziarie" in titles:
        notes.append(
            {
                "presidio": "ACF",
                "azione": "Valuta reclamo e ricorso ACF quando emergono servizi di investimento o obblighi informativi dell'intermediario.",
                "fonte": "CONSOB",
            }
        )
    if "arbitro assicurativo" in titles:
        notes.append(
            {
                "presidio": "Arbitro Assicurativo",
                "azione": "Prima del ricorso verifica reclamo assicurativo e decorso dei termini di risposta.",
                "fonte": "IVASS",
            }
        )
    if "conciliaweb" in titles:
        notes.append(
            {
                "presidio": "ConciliaWeb",
                "azione": "Per operatori di comunicazioni elettroniche verifica reclamo, conciliazione e definizione AGCOM.",
                "fonte": "AGCOM",
            }
        )
    if "patrocinio a spese" in titles:
        notes.append(
            {
                "presidio": "Patrocinio a spese dello Stato",
                "azione": "Valuta requisiti reddituali, non manifesta infondatezza e documenti prima o durante l'apertura del fascicolo.",
                "fonte": "Ministero della Giustizia",
            }
        )
    if "pagamenti telematici" in titles or "pagopa" in titles:
        notes.append(
            {
                "presidio": "Contributo unificato e PagoPA",
                "azione": "Prepara pagamento, ricevuta e dati economici senza bloccare la redazione dell'atto.",
                "fonte": "Ministero della Giustizia / PST",
            }
        )
    if "tassazione degli atti giudiziari" in titles:
        notes.append(
            {
                "presidio": "Tassazione atti giudiziari",
                "azione": "Dopo il provvedimento valuta registrazione e importi tramite il servizio Agenzia delle Entrate.",
                "fonte": "Agenzia delle Entrate",
            }
        )
    if "infortunio" in titles or "malattia professionale" in titles:
        notes.append(
            {
                "presidio": "INAIL",
                "azione": "Per infortunio o malattia professionale verifica denuncia, certificati e termini amministrativi collegati.",
                "fonte": "INAIL",
            }
        )
    if "ricorsi amministrativi" in titles:
        notes.append(
            {
                "presidio": "INPS",
                "azione": "Nelle materie previdenziali controlla il ricorso amministrativo e il relativo stato prima del giudizio.",
                "fonte": "INPS",
            }
        )
    if "registro delle imprese" in titles:
        notes.append(
            {
                "presidio": "Registro imprese",
                "azione": "Acquisisci visura aggiornata, assetti, liquidazione o cancellazione prima di impostare domanda e legittimazione.",
                "fonte": "Camera di Commercio",
            }
        )
    if "tribunale per i minorenni" in titles:
        notes.append(
            {
                "presidio": "Competenza minorile",
                "azione": "Distingui Tribunale ordinario, Tribunale per i Minorenni e Giudice tutelare prima di selezionare ufficio e template.",
                "fonte": "Ministero della Giustizia",
            }
        )
    if "albo ctu" in titles:
        notes.append(
            {
                "presidio": "CTU/ATP",
                "azione": "Quando la pratica è tecnica, collega quesiti, documenti e possibile consulenza preventiva senza trasformarla in blocco.",
                "fonte": "PST / Ministero della Giustizia",
            }
        )
    return notes


def operational_presidi_for_guidance(guidance: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    deposito = _as_dict(guidance.get("codice_deposito"))
    depositabile = bool(deposito.get("depositabile"))
    allegati_count = len(_as_list(guidance.get("allegati_obbligatori")))
    termini_count = len(_as_list(guidance.get("termini_processuali")))
    return {
        "versione": ENRICHMENT_VERSION,
        "verificato_il": VERIFIED_ON,
        "deposito": {
            "regola": "Il codice deposito resta sempre quello ufficiale del fascicolo; la guida non lo sostituisce.",
            "depositabile_dalla_scheda": depositabile,
            "azione_avvocato": (
                "Usa il codice già valorizzato nel fascicolo e verifica solo coerenza con atto e ufficio."
                if depositabile
                else "Usa questa scheda come guida operativa e seleziona nel fascicolo il codice PST/XSD ufficiale pertinente."
            ),
        },
        "procedibilita_e_adr": _procedibilita_note(guidance, sources),
        "termini": {
            "termini_censiti": termini_count,
            "azione_avvocato": "Trasforma i termini pertinenti in scadenze solo dopo aver fissato decorrenza e atto/fase reale.",
        },
        "allegati": {
            "allegati_censiti": allegati_count,
            "azione_avvocato": "Usa gli allegati come checklist fascicolo, non come blocco preventivo della redazione.",
        },
        "lex": {
            "profilo": "conversazionale_avvocato",
            "azione": "Lex deve spiegare fonte, limite, dato mancante e prossimo passo operativo senza confondere guida e deposito.",
        },
        "template": {
            "azione": "Il template va filtrato su codice/guida, rito, fase, ufficio, valore, documenti presenti e atto suggerito.",
        },
    }


def enrich_guidance_with_web_sources(guidance: dict[str, Any]) -> dict[str, Any]:
    """Applica l'arricchimento a una scheda senza sovrascrivere il contenuto curato."""

    out = deepcopy(guidance)
    existing = out.get("fonti_verifica_web") if isinstance(out.get("fonti_verifica_web"), list) else []
    by_url = {str(source.get("url")): dict(source) for source in existing if isinstance(source, dict) and source.get("url")}
    for source in web_sources_for_guidance(out):
        by_url.setdefault(source["url"], source)
    sources = list(by_url.values())
    out["fonti_verifica_web"] = sources

    existing_presidi = _as_dict(out.get("presidi_operativi_integrativi"))
    presidi = operational_presidi_for_guidance(out, sources)
    out["presidi_operativi_integrativi"] = {**presidi, **existing_presidi}
    out["arricchimento_iusentra"] = {
        "versione": ENRICHMENT_VERSION,
        "generato_il": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "applicato a tutte le schede Guida Pratica restituite dal servizio",
        "fonti_ufficiali": len(sources),
        "non_bloccante": True,
    }
    return out
