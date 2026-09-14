"""Fonti trasversali del catalogo: identità, provenienza e ricevute.

I riferimenti sono prove della regola, non aumenti del punteggio del file.
La revisione giuridica di ogni atto resta distinta dalla sua classificazione.
"""
from __future__ import annotations

from typing import Any

from .titoli.fonti import FONTI_TITOLI

CATALOG_SOURCES: dict[str, dict[str, Any]] = {
    "catalog_pst_xsd": {
        "label": "Ministero della Giustizia: catalogo ufficiale degli oggetti e schemi XSD",
        "official_url": "https://pst.giustizia.it/PST/it/download.page",
        "verification_status": "pagina ufficiale consultata il 06/09/2026; versione XSD indicata nella prova del fascicolo",
        "source_type": "telematica",
    },
    "catalog_agid_metadati": {
        "label": "AgID: Allegato 5, metadati di identità, classificazione e aggregazione documentale",
        "official_url": "https://www.agid.gov.it/sites/default/files/repository_files/all.5_metadati.pdf",
        "verification_status": "fonte ufficiale disponibile; criteri documentali, non certificazione di conservazione",
        "source_type": "documentale",
    },
    "catalog_pec_ricevute": {
        "label": "D.P.R. 68/2005, art. 6: ricevute di accettazione e avvenuta consegna PEC",
        "official_url": "https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&articolo=Articolo+6&codiceOrdinamento=200000600000000&id=%7B28C1CCF5-2E9E-4392-99F5-DBCBD37C97C4%7D",
        "verification_status": "testo ufficiale MEF consultato il 06/09/2026",
        "source_type": "normativa",
    },
    "catalog_pec_specifiche": {
        "label": "D.M. 2 novembre 2005: regole tecniche PEC e dati di certificazione",
        "official_url": "https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloDefault/originario?atto.codiceRedazionale=05A10742&atto.dataPubblicazioneGazzetta=2005-11-15&atto.tipoProvvedimento=DECRETO",
        "verification_status": "pubblicazione ufficiale consultata il 06/09/2026",
        "source_type": "telematica",
    },
    "catalog_fatturapa": {
        "label": "FatturaPA: struttura del documento fiscale, numero, data e totale distinti",
        "official_url": "https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf",
        "verification_status": "riferimento ufficiale indicizzato; recupero PDF diretto non riuscito il 06/09/2026, nessuna validazione XSD attestata",
        "source_type": "telematica",
    },
    "catalog_fattura_emissione": {
        "label": "Agenzia delle Entrate: fattura elettronica e trasmissione al Sistema di Interscambio",
        "official_url": "https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html",
        "verification_status": "guida ufficiale consultata; la classificazione non verifica emissione, consegna SdI o pagamento",
        "source_type": "documentale",
    },
    "normattiva_dpr_445_2000_documentazione_amministrativa": {
        "label": "D.P.R. 445/2000: documenti di identità (art. 35), certificati (art. 40), dichiarazioni sostitutive (artt. 46 e 47)",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:2000-12-28;445~art46",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    "normattiva_dpr_605_1973_codice_fiscale": {
        "label": "D.P.R. 605/1973, art. 2: codice fiscale e sua composizione",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1973-09-29;605~art2",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    "normattiva_cpc_esecuzione_forzata": {
        "label": "c.p.c., artt. 480 (precetto), 492 e 543 (pignoramento): atti dell'esecuzione forzata",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art480",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    "normattiva_cpc_consulenza_tecnica": {
        "label": "c.p.c., artt. 191-201: consulente tecnico d'ufficio, relazione e consulenti di parte",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art191",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    "normattiva_cpc_art_189_precisazione_conclusioni": {
        "label": "c.p.c., art. 189: precisazione delle conclusioni e rimessione al collegio",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art189",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    "normattiva_d_lgs_175_2024_tu_giustizia_tributaria": {
        "label": "D.Lgs. 175/2024, Testo unico della giustizia tributaria: ricorso (art. 64), termine di sessanta giorni (art. 67), costituzione del ricorrente (art. 68) e del resistente (art. 69); gli artt. 18-23 del D.Lgs. 546/1992 sono abrogati",
        "official_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2024-11-14;175~art64",
        "verification_status": "testo vigente consultato su Normattiva il 14/09/2026",
        "source_type": "normativa",
    },
    # Fonti delle regole d'identità dal titolo, per area (verificate su Normattiva).
    **FONTI_TITOLI,
}


def catalog_source_row(source_id: str) -> dict[str, Any] | None:
    source = CATALOG_SOURCES.get(source_id)
    if not source:
        return None
    verificata = "2026-09-14" if "14/09/2026" in str(source.get("verification_status") or "") else "2026-09-06"
    return {"id": source_id, "last_verified_at": verificata, "snapshot_sha256": "", **source}


def document_source_ids(nature: str, section: str, profile_id: str | None) -> tuple[str, ...]:
    common = ("catalog_agid_metadati",)
    # Nature riconosciute dal titolo dell'atto (catalog_titoli): ognuna porta la
    # norma che definisce quel documento.
    if nature in {"dichiarazione_sostitutiva", "documento_identita", "certificato_anagrafico"}:
        return common + ("normattiva_dpr_445_2000_documentazione_amministrativa",)
    if nature == "atto_esecutivo":
        return common + ("normattiva_cpc_esecuzione_forzata",)
    if nature in {"relazione_peritale_ctu", "perizia_di_parte"}:
        return common + ("normattiva_cpc_consulenza_tecnica",)
    if nature == "ricevuta_deposito":
        return common + ("catalog_pec_ricevute", "catalog_pec_specifiche")
    if nature in {"fattura", "fattura_xml", "proforma"}:
        return common + ("catalog_fatturapa", "catalog_fattura_emissione")
    if nature in {"verbale_mediazione", "modulo_mediazione", "accordo_mediazione", "modulo_procura_mediazione", "procura_mediazione"}:
        return common + ("normattiva_d_lgs_28_2010_mediazione",)
    if (section == "comunicazioni" and nature != "corrispondenza_stragiudiziale") or nature.startswith("ricevuta_pec"):
        return common + ("catalog_pec_ricevute", "catalog_pec_specifiche")
    if section in {"procure", "provvedimenti", "atti"}:
        procedural = {"PEN": "normattiva_cpp", "PAT": "normattiva_cpa", "TRIB": "normattiva_d_lgs_175_2024_tu_giustizia_tributaria"}.get(profile_id or "")
        if not procedural and profile_id and (profile_id.startswith("CIV-") or profile_id in {"LAV", "FAM", "VGS", "LOC", "RCD", "SOC", "BAN", "CONC"}):
            procedural = "normattiva_cpc"
        return common + ((procedural,) if procedural else ())
    if section == "contratti":
        return common + ("normattiva_codice_civile",)
    return common
