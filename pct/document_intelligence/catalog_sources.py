"""Fonti trasversali del catalogo: identità, provenienza e ricevute.

I riferimenti sono prove della regola, non aumenti del punteggio del file.
La revisione giuridica di ogni atto resta distinta dalla sua classificazione.
"""
from __future__ import annotations

from typing import Any

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
}


def catalog_source_row(source_id: str) -> dict[str, Any] | None:
    source = CATALOG_SOURCES.get(source_id)
    return {"id": source_id, "last_verified_at": "2026-09-06", "snapshot_sha256": "", **source} if source else None


def document_source_ids(nature: str, section: str, profile_id: str | None) -> tuple[str, ...]:
    common = ("catalog_agid_metadati",)
    if nature in {"fattura", "fattura_xml", "proforma"}:
        return common + ("catalog_fatturapa", "catalog_fattura_emissione")
    if nature in {"verbale_mediazione", "modulo_mediazione", "accordo_mediazione", "modulo_procura_mediazione", "procura_mediazione"}:
        return common + ("normattiva_d_lgs_28_2010_mediazione",)
    if (section == "comunicazioni" and nature != "corrispondenza_stragiudiziale") or nature.startswith("ricevuta_pec"):
        return common + ("catalog_pec_ricevute", "catalog_pec_specifiche")
    if section in {"procure", "provvedimenti", "atti"}:
        procedural = {"PEN": "normattiva_cpp", "PAT": "normattiva_cpa", "TRIB": "normattiva_d_lgs_546_1992_tributario"}.get(profile_id or "")
        if not procedural and profile_id and (profile_id.startswith("CIV-") or profile_id in {"LAV", "FAM", "VGS", "LOC", "RCD", "SOC", "BAN", "CONC"}):
            procedural = "normattiva_cpc"
        return common + ((procedural,) if procedural else ())
    if section == "contratti":
        return common + ("normattiva_codice_civile",)
    return common
