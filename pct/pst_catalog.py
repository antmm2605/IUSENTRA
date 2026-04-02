"""
pct/pst_catalog.py - Catalogo versionato delle fonti ufficiali PST.

Questo modulo centralizza la documentazione software house, il vademecum
utente e le specifiche tecniche del Portale Servizi Telematici usate dai
resolver e dai validatori deterministici.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PST_WEB_SERVICES_DOC_VERSION = "1.65"
PST_WEB_SERVICES_DOC_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Documentazione_servizi_web_v1.65.pdf"
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
PST_CATALOG_VERSION = "PST-CATALOGO-SERVIZI-v1.65-2026.04.02.1"
PST_SCHEMA_VERSION = "PST-SCHEMI-v1.65-2026.04.02.1"
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


def get_official_methods() -> list[PSTOfficialMethod]:
    return [
        PSTOfficialMethod(
            name="getListaUfficiGiudiziari",
            label="Lista uffici giudiziari civili",
            category="catalogo_uffici",
            page=43,
            current_support="parziale",
            notes=(
                "HACS usa bundle/versioning interno e REST pubblico PST per gli uffici, "
                "ma non interroga ancora direttamente questo metodo SOAP in produzione."
            ),
        ),
        PSTOfficialMethod(
            name="getListaUfficiPenali",
            label="Lista uffici giudiziari penali",
            category="catalogo_uffici",
            page=44,
            current_support="parziale",
            notes=(
                "Il catalogo penale e coperto da bundle e mapping interni; "
                "manca ancora il binding live al metodo ufficiale."
            ),
        ),
        PSTOfficialMethod(
            name="getRegistriFromUfficio",
            label="Registri disponibili per ufficio",
            category="catalogo_registri",
            page=45,
            current_support="parziale",
            notes=(
                "Il resolver usa registri consentiti per profilo procedurale; "
                "non sincronizza ancora i registri direttamente dal servizio ministeriale."
            ),
        ),
        PSTOfficialMethod(
            name="getNormativa",
            label="Normativa atti depositabili penali",
            category="catalogo_penale",
            page=45,
            current_support="parziale",
            notes=(
                "Il motore penale usa regole interne versionate; "
                "non scarica ancora la normativa depositabile dal metodo ufficiale."
            ),
        ),
        PSTOfficialMethod(
            name="getTipiUfficio",
            label="Tipi ufficio con gruppi C/P",
            category="catalogo_uffici",
            page=46,
            current_support="parziale",
            notes=(
                "I tipi ufficio sono modellati internamente, ma non ancora "
                "risolti con il gruppo civile/penale del servizio v1.65."
            ),
        ),
        PSTOfficialMethod(
            name="getRito",
            label="Riti per registro",
            category="catalogo_riti",
            page=46,
            current_support="parziale",
            notes=(
                "Il rito e determinato da profili procedurali/versionati; "
                "manca ancora la sincronizzazione diretta dal catalogo ministeriale."
            ),
        ),
        PSTOfficialMethod(
            name="interrogazioniExt",
            label="Namespace ReGIndE esteso",
            category="reginde",
            page=48,
            current_support="parziale",
            notes=(
                "Il namespace ufficiale vigente e tracciato nel catalogo, "
                "ma il modulo ReGIndE locale non usa ancora un adapter SOAP esplicito."
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


def get_catalog_sources() -> list[dict[str, str]]:
    return [
        {
            "label": "PST - documentazione servizi web software house v1.65",
            "url": PST_WEB_SERVICES_DOC_URL,
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
    ]


def get_catalog_snapshot() -> dict[str, Any]:
    methods = [item.to_dict() for item in get_official_methods()]
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
        "pst_user_vademecum_url": PST_USER_VADEMECUM_URL,
        "pst_dm44_specifiche_revision": PST_DM44_SPECIFICHE_REVISION,
        "pst_dm44_specifiche_url": PST_DM44_SPECIFICHE_URL,
        "reginde_namespace": PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
        "catalog_version": PST_CATALOG_VERSION,
        "schema_version": PST_SCHEMA_VERSION,
        "busta_max_bytes": PST_MAX_BUSTA_BYTES,
        "busta_max_mb": PST_MAX_BUSTA_MB,
        "formal_error_codes": dict(PST_FORMAL_ERROR_CODES),
        "methods": methods,
        "summary": summary,
    }
