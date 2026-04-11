"""
pct/pst_catalog.py - Catalogo versionato delle fonti ufficiali PST.

Questo modulo centralizza la documentazione software house, il vademecum
utente e le specifiche tecniche del Portale Servizi Telematici usate dai
resolver e dai validatori deterministici.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PST_WEB_SERVICES_DOC_VERSION = "1.69"
PST_WEB_SERVICES_DOC_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Documentazione_servizi_web_v1.69.pdf"
)
PST_WEB_SERVICES_DOC_PAGE_URL = "https://pst.giustizia.it/PST/it/documentation.page"
PST_WEB_SERVICES_DOC_DETAIL_URL = (
    "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571"
)
PST_WEB_SERVICES_WSDL_CATALOG_VERSION = "1.52"
PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_NAME = "A1_WSDL_CATALOG_v1.52.zip"
PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/A1_WSDL_CATALOG_v1.52.zip"
)
PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_VERSION = "1.52b"
PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME = "A1_WSDL_CATALOG_v1.52b.zip"
PST_WEB_SERVICES_WSDL_CATALOG_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/A1_WSDL_CATALOG_v1.52b.zip"
)
PST_WEB_SERVICES_UPDATE_PAGE_URL = PST_WEB_SERVICES_DOC_DETAIL_URL
PST_PDP_SPECIFICHE_DETAIL_URL = (
    "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC2786"
)
PST_PDP_SPECIFICHE_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf"
)
PST_USER_VADEMECUM_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Manuale_utente_PSTVademecum.pdf"
)
PST_DM44_SPECIFICHE_REVISION = "04.01.24"
PST_DM44_SPECIFICHE_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "SPECIFICHE_TECNICHE_DM_44_2011REV_04.01.24.pdf"
)
PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE = (
    "http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt"
)
PST_XSD_DOWNLOAD_PAGE_URL = "https://pst.giustizia.it/PST/it/download.page"
PST_CATALOG_VERSION = "PST-CATALOGO-SERVIZI-v1.69-2026.04.12.1"
PST_SCHEMA_VERSION = "PST-SCHEMI-v1.69-2026.04.12.1"
PST_MAX_BUSTA_MB = 60
PST_MAX_BUSTA_BYTES = PST_MAX_BUSTA_MB * 1024 * 1024
PST_FORMAL_ERROR_CODES = {
    "T001": "Indirizzo del mittente non censito in ReGIndE.",
    "T002": "Formato del messaggio non aderente alle specifiche.",
    "T003": "Dimensione del messaggio eccede la dimensione massima consentita.",
}


@dataclass(frozen=True)
class PSTOfficialMethod:
    name: str
    label: str
    category: str
    page: int
    current_support: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PSTWSDLModule:
    key: str
    label: str
    category: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PSTXSDChannel:
    key: str
    label: str
    area: str
    download_page_url: str
    package_name: str
    package_url: str
    package_date: str
    changelog_name: str
    changelog_url: str
    status: str
    status_source_news_date: str
    status_source_news_url: str
    notes: str
    applies_to: str = ""

    @property
    def production_ready(self) -> bool:
        return self.status == "production"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["production_ready"] = self.production_ready
        return payload


def get_official_methods() -> list[PSTOfficialMethod]:
    return [
        PSTOfficialMethod(
            name="getListaUfficiGiudiziari",
            label="Lista uffici giudiziari civili",
            category="catalogo_uffici",
            page=43,
            current_support="parziale",
            notes=(
                "HACS dispone ora di un adapter WSDL/cache per questo metodo; "
                "la sincronizzazione live si attiva quando e configurato l'endpoint SOAP ufficiale."
            ),
        ),
        PSTOfficialMethod(
            name="getListaUfficiPenali",
            label="Lista uffici giudiziari penali",
            category="catalogo_uffici",
            page=44,
            current_support="parziale",
            notes=(
                "Il metodo e tracciato dal catalogo WSDL e puo usare cache/endpoint ufficiale; "
                "resta il fallback interno finche il binding live non e configurato."
            ),
        ),
        PSTOfficialMethod(
            name="getRegistriFromUfficio",
            label="Registri disponibili per ufficio",
            category="catalogo_registri",
            page=45,
            current_support="parziale",
            notes=(
                "Resolver e validator possono ora leggere registri da cache/servizio ufficiale; "
                "la copertura live dipende dall'endpoint SOAP configurato."
            ),
        ),
        PSTOfficialMethod(
            name="getNormativa",
            label="Normativa atti depositabili penali",
            category="catalogo_penale",
            page=45,
            current_support="parziale",
            notes=(
                "Il metodo e supportato dall'adapter ufficiale con cache; "
                "la normativa live viene letta quando il servizio ministeriale e disponibile."
            ),
        ),
        PSTOfficialMethod(
            name="getTipiUfficio",
            label="Tipi ufficio con gruppi C/P",
            category="catalogo_uffici",
            page=46,
            current_support="parziale",
            notes=(
                "I tipi ufficio sono ancora modellati internamente come fallback, "
                "ma l'adapter WSDL puo sincronizzarli dal catalogo ufficiale."
            ),
        ),
        PSTOfficialMethod(
            name="getRito",
            label="Riti per registro",
            category="catalogo_riti",
            page=46,
            current_support="parziale",
            notes=(
                "Il rito continua ad avere un fallback procedurale interno, "
                "ma resolver e validator possono leggere i riti dal catalogo ministeriale ufficiale."
            ),
        ),
        PSTOfficialMethod(
            name="interrogazioniExt",
            label="Namespace ReGIndE esteso",
            category="reginde",
            page=48,
            current_support="parziale",
            notes=(
                "Il namespace ufficiale vigente e tracciato nel catalogo "
                "e il software usa ora un adapter SOAP configurabile per il catalogo PST."
            ),
        ),
        PSTOfficialMethod(
            name="QC_Uffici",
            label="Query Cassazione per catalogo uffici",
            category="cassazione",
            page=24,
            current_support="parziale",
            notes=(
                "La consultazione Cassazione usa risoluzione interna/proxy; "
                "non e ancora esposta una query versionata dedicata QC_Uffici."
            ),
        ),
    ]


def get_wsdl_catalog_modules() -> list[PSTWSDLModule]:
    return [
        PSTWSDLModule(
            key="catalogo_ug",
            label="Catalogo Uffici Giudiziari",
            category="catalogo",
            notes="Espone WSDL per il catalogo uffici, registri e servizi di supporto ai resolver.",
        ),
        PSTWSDLModule(
            key="sicid_consultazione",
            label="Consultazione registri SICID",
            category="consultazione_registri",
            notes="Comprende cataloghi e WSDL per SICC, SIL, VG, Minorenni e CDA.",
        ),
        PSTWSDLModule(
            key="siecic_consultazione",
            label="Consultazione registri SIECIC",
            category="consultazione_registri",
            notes="Cataloghi/WSDL per consultazione procedure esecutive e concorsuali.",
        ),
        PSTWSDLModule(
            key="sigp_consultazione",
            label="Consultazione registri SIGP",
            category="consultazione_registri",
            notes="Consultazione registri e fascicolo informatico dei Giudici di Pace.",
        ),
        PSTWSDLModule(
            key="cassazione_consultazione",
            label="Consultazione registri Cassazione civile e penale",
            category="consultazione_registri",
            notes="Cataloghi e WSDL separati per CASSCI e CASSPE.",
        ),
        PSTWSDLModule(
            key="fascicolo_informatico",
            label="Accesso ai documenti del fascicolo informatico",
            category="fascicolo",
            notes="Famiglie WSDL per fascicolo informatico SICID, SIECIC, SIGP e Cassazione.",
        ),
        PSTWSDLModule(
            key="reginde",
            label="ReGIndE",
            category="servizi_accessori",
            notes="Servizi di interrogazione soggetto/ente con namespace interrogazioniExt.",
        ),
        PSTWSDLModule(
            key="pagamenti_telematici",
            label="Pagamenti telematici",
            category="servizi_accessori",
            notes="Invio e consultazione pagamenti telematici del PST.",
        ),
        PSTWSDLModule(
            key="richieste_copie",
            label="Richieste copie",
            category="servizi_accessori",
            notes="WSDL dedicati per richieste copie su SICID/SIECIC.",
        ),
        PSTWSDLModule(
            key="download_notifiche",
            label="Download notifiche",
            category="servizi_accessori",
            notes="Servizio WSDL per download notifiche dal portale.",
        ),
        PSTWSDLModule(
            key="verifica_pdf",
            label="API Verifica PDF",
            category="servizi_accessori",
            notes="Specifica YAML presente nel catalogo WSDL ufficiale A1 pubblicato dal PST.",
        ),
    ]


def get_xsd_channels() -> list[PSTXSDChannel]:
    return [
        PSTXSDChannel(
            key="SICI",
            label="XSD SICI",
            area="Civile ordinario / redattori area civile",
            download_page_url="https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4588",
            package_name="XSD_SICI_20260116.zip",
            package_url="https://pst.giustizia.it/PST/resources/cms/documents/XSD_SICI_20260116.zip",
            package_date="2026-01-26",
            changelog_name="Nota modifiche XSD SICI - 26/01/2026",
            changelog_url="https://pst.giustizia.it/PST/resources/cms/documents/modifiche_XSD_SICI_20260116.pdf",
            status="production",
            status_source_news_date="2026-01-29",
            status_source_news_url=(
                "https://pst.giustizia.it/PST/page/it/"
                "interruzione_dei_servizi_informatici_del_settore_civile_del_portale_dei_servizi_telematici_"
                "e_del_portale_dei_depositi_penali_dalle_ore_1600_alle_ore_1800_del_29012026?contentId=NWS4596&modelId=4"
            ),
            notes=(
                "Pacchetto pubblicato il 26/01/2026; la news del 29/01/2026 conferma la messa in produzione "
                "degli XSD aggiornati per i redattori atti dell'area civile."
            ),
            applies_to="Redattore civile SICI / SICID-SIECIC",
        ),
        PSTXSDChannel(
            key="SIGP",
            label="XSD per i Giudici di Pace",
            area="Giudici di Pace / SIGP",
            download_page_url="https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3199",
            package_name="XSD_SIGP_20241128.zip",
            package_url="https://pst.giustizia.it/PST/resources/cms/documents/XSD_SIGP_20241128.zip",
            package_date="2024-11-29",
            changelog_name="Nota modifiche XSD SICI SIGP - 19/11/2024",
            changelog_url="https://pst.giustizia.it/PST/resources/cms/documents/modifiche_XSD_SICI_SIGP_20241119_v2.pdf",
            status="production",
            status_source_news_date="2024-11-29",
            status_source_news_url=(
                "https://pst.giustizia.it/PST/page/it/"
                "processo_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_"
                "deposito_atti_sici_e_sigp_it_1?contentId=NWS3744"
            ),
            notes=(
                "La news del 29/11/2024 chiarisce che la versione corretta degli schemi aggiornati "
                "e utilizzabile in ambiente di produzione."
            ),
            applies_to="Redattore Giudice di Pace / SIGP",
        ),
        PSTXSDChannel(
            key="UNEP",
            label="XSD per UNEP",
            area="Uffici NEP",
            download_page_url="https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3136",
            package_name="XSD_PLO118_FASE2_per_SW_House_20241106.zip",
            package_url="https://pst.giustizia.it/PST/resources/cms/documents/XSD_PLO118_FASE2_per_SW_House_20241106.zip",
            package_date="2024-11-06",
            changelog_name="Nota modifiche XSD UNEP 06/11/2024",
            changelog_url="https://pst.giustizia.it/PST/resources/cms/documents/XSD_UNEP_04_11_2024_per_SW_House_note_informative.pdf",
            status="production",
            status_source_news_date="2024-11-18",
            status_source_news_url=(
                "https://pst.giustizia.it/PST/page/it/"
                "processo_telematico__comunicazione_per_le_software_house__entrata_in_esercizio_dei_nuovi_"
                "schemi_xsd_per_i_depositi_telematici_presso_gli_uffici_unep?contentId=NWS3654"
            ),
            notes=(
                "Gli schemi pubblicati il 06/11/2024 sono dichiarati utilizzabili in ambiente "
                "di esercizio dalla news del 18/11/2024."
            ),
            applies_to="Depositi telematici presso gli Uffici UNEP",
        ),
        PSTXSDChannel(
            key="CASSAZIONE",
            label="XSD per la Corte Suprema di Cassazione",
            area="Corte Suprema di Cassazione",
            download_page_url="https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4671",
            package_name="XSD_Cassazione_20260227.zip",
            package_url="https://pst.giustizia.it/PST/resources/cms/documents/XSD_Cassazione_20260227.zip",
            package_date="2026-02-27",
            changelog_name="Processo Telematico di legittimita - Schemi XSD v.21",
            changelog_url="https://pst.giustizia.it/PST/resources/cms/documents/Processo_Telematico_di_legittimit__Schemi_XSD_v.21.pdf",
            status="production",
            status_source_news_date="2026-03-04",
            status_source_news_url=(
                "https://pst.giustizia.it/PST/page/it/"
                "processo_telematico__comunicazione_per_le_software_house_applicazione_in_esercizio_dei_"
                "nuovi_schemi_xsd_per_i_depositi_telematici_presso_la_corte_suprema_di_cassazione_it_2?"
                "contentId=NWS4683&modelId=4"
            ),
            notes=(
                "Il pacchetto del 27/02/2026 e applicato in esercizio dal 04/03/2026, come da news "
                "software house dedicata."
            ),
            applies_to="Redattore Cassazione / processo telematico di legittimita",
        ),
    ]


def get_xsd_channel(key: str) -> PSTXSDChannel:
    lookup = {item.key: item for item in get_xsd_channels()}
    return lookup[key]


def get_catalog_sources() -> list[dict[str, str]]:
    return [
        {
            "label": "PST - documentazione servizi web software house v1.69",
            "url": PST_WEB_SERVICES_DOC_URL,
        },
        {
            "label": "PST - pagina documentazione ufficiale",
            "url": PST_WEB_SERVICES_DOC_PAGE_URL,
        },
        {
            "label": "PST - dettaglio documentazione servizi web v1.69",
            "url": PST_WEB_SERVICES_DOC_DETAIL_URL,
        },
        {
            "label": "PST - catalogo WSDL ufficiale A1 pubblicato in pagina",
            "url": PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_URL,
        },
        {
            "label": "PST - pagina download ufficiale XSD",
            "url": PST_XSD_DOWNLOAD_PAGE_URL,
        },
        {
            "label": f"PST - specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
            "url": PST_DM44_SPECIFICHE_URL,
        },
        {
            "label": "PST - manuale utente / vademecum",
            "url": PST_USER_VADEMECUM_URL,
        },
        {
            "label": "PST - namespace ReGIndE interrogazioniExt",
            "url": PST_WEB_SERVICES_DOC_URL,
        },
    ] + [
        {
            "label": f"{channel.label} - pagina download",
            "url": channel.download_page_url,
        }
        for channel in get_xsd_channels()
    ] + [
        {
            "label": f"{channel.label} - news stato esercizio",
            "url": channel.status_source_news_url,
        }
        for channel in get_xsd_channels()
    ]


def get_catalog_snapshot() -> dict[str, Any]:
    methods = [item.to_dict() for item in get_official_methods()]
    wsdl_modules = [item.to_dict() for item in get_wsdl_catalog_modules()]
    xsd_channels = [item.to_dict() for item in get_xsd_channels()]
    summary = {"coperto": 0, "parziale": 0, "mancante": 0}
    for item in methods:
        status = str(item.get("current_support") or "").strip().lower()
        if status == "coperto":
            summary["coperto"] += 1
        elif status == "parziale":
            summary["parziale"] += 1
        else:
            summary["mancante"] += 1
    return {
        "pst_webservices_doc_version": PST_WEB_SERVICES_DOC_VERSION,
        "pst_webservices_doc_url": PST_WEB_SERVICES_DOC_URL,
        "pst_webservices_doc_page_url": PST_WEB_SERVICES_DOC_PAGE_URL,
        "pst_webservices_doc_detail_url": PST_WEB_SERVICES_DOC_DETAIL_URL,
        "pst_webservices_update_page_url": PST_WEB_SERVICES_UPDATE_PAGE_URL,
        "pst_webservices_wsdl_catalog_version": PST_WEB_SERVICES_WSDL_CATALOG_VERSION,
        "pst_webservices_wsdl_catalog_published_name": PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_NAME,
        "pst_webservices_wsdl_catalog_published_url": PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_URL,
        "pst_webservices_wsdl_catalog_package_version": PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_VERSION,
        "pst_webservices_wsdl_catalog_package_name": PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME,
        "pst_webservices_wsdl_catalog_url": PST_WEB_SERVICES_WSDL_CATALOG_URL,
        "pst_xsd_download_page_url": PST_XSD_DOWNLOAD_PAGE_URL,
        "pst_pdp_specifiche_detail_url": PST_PDP_SPECIFICHE_DETAIL_URL,
        "pst_pdp_specifiche_url": PST_PDP_SPECIFICHE_URL,
        "pst_user_vademecum_url": PST_USER_VADEMECUM_URL,
        "pst_dm44_specifiche_revision": PST_DM44_SPECIFICHE_REVISION,
        "pst_dm44_specifiche_url": PST_DM44_SPECIFICHE_URL,
        "reginde_namespace": PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
        "catalog_version": PST_CATALOG_VERSION,
        "schema_version": PST_SCHEMA_VERSION,
        "wsdl_modules": wsdl_modules,
        "xsd_channels": xsd_channels,
        "xsd_summary": {
            "production_ready": sum(1 for item in xsd_channels if item["production_ready"]),
            "preview": sum(1 for item in xsd_channels if item["status"] == "preview"),
            "channels": len(xsd_channels),
        },
        "busta_max_bytes": PST_MAX_BUSTA_BYTES,
        "busta_max_mb": PST_MAX_BUSTA_MB,
        "formal_error_codes": dict(PST_FORMAL_ERROR_CODES),
        "methods": methods,
        "summary": summary,
    }
