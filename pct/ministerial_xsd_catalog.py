"""Inventario governato degli XSD DatiAtto ministeriali in esercizio.

Le directory ministeriali contengono anche versioni storiche e anticipazioni. Il
runtime non deve quindi ricavare lo schema corrente con una scansione ricorsiva:
questa tabella elenca esplicitamente i soli entry point in esercizio.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from lxml import etree

from pct.pst_catalog import PST_CASSAZIONE_XSD_ACTIVE_VERSION

_ROOT = Path(__file__).resolve().parents[1]
_XSD_NS = "http://www.w3.org/2001/XMLSchema"
_SICI_PACKAGE = "XSD_SICI_20260508.zip"
_SICI_BASE = (
    "docs/specs/ministero/xsd/2026-05-12-sici/"
    "XSD_SICI_20260508/XSD_SICI_20260508/Atti/sici"
)

ROLE_AVVOCATO = "avvocato"
ROLE_CURATORE = "curatore"
ROLE_CUSTODE = "custode"
ROLE_DELEGATO = "delegato"
ROLE_CTU = "ctu"


@dataclass(frozen=True)
class ActiveMinisterialSchema:
    generator_class: str
    relative_path: str
    package_name: str
    production_since: str
    allowed_professional_roles: tuple[str, ...]
    system_only: bool = False

    @property
    def path(self) -> Path:
        return _ROOT / self.relative_path


def _sici(
    generator_class: str,
    relative_path: str,
    *roles: str,
    system_only: bool = False,
) -> ActiveMinisterialSchema:
    return ActiveMinisterialSchema(
        generator_class=generator_class,
        relative_path=f"{_SICI_BASE}/{relative_path}",
        package_name=_SICI_PACKAGE,
        production_since="14/05/2026",
        allowed_professional_roles=tuple(roles),
        system_only=system_only,
    )


ACTIVE_MINISTERIAL_SCHEMAS: tuple[ActiveMinisterialSchema, ...] = (
    _sici("IntroduttiviSicid", "sicid_v7/Introduttivi.xsd", ROLE_AVVOCATO),
    _sici("Parte", "sicid_v7/Parte.xsd", ROLE_AVVOCATO),
    _sici("Professionista", "sicid_v2/Professionista.xsd", ROLE_CTU),
    _sici("AttoSistemaSicid", "base_v3/Sistema-pubbl-sicid.xsd", system_only=True),
    _sici("IntroduttiviSiecicConcorsuali", "siecic_v7/Introduttivi-siecic-concorsuali.xsd", ROLE_AVVOCATO),
    _sici("IntroduttiviSiecicEsecuzioni", "siecic_v8/Introduttivi-siecic-esecuzioni.xsd", ROLE_AVVOCATO),
    _sici("ParteSiecicConcorsuali", "siecic_v8/Parte-siecic-concorsuali.xsd", ROLE_AVVOCATO),
    _sici("ParteSiecicEsecuzioni", "siecic_v8/Parte-siecic-esecuzioni.xsd", ROLE_AVVOCATO),
    _sici("CurSiecicConcorsuali", "siecic_v11/Cur-siecic-concorsuali.xsd", ROLE_CURATORE),
    _sici("CusSiecicEsecuzioni", "siecic_v4/Cus-siecic-esecuzioni.xsd", ROLE_CUSTODE),
    _sici("DelSiecicEsecuzioni", "siecic_v7/Del-siecic-esecuzioni.xsd", ROLE_DELEGATO),
    _sici("ProfSiecicConcorsuali", "siecic_v6/Prof-siecic-concorsuali.xsd", ROLE_CTU),
    _sici("ProfSiecicEsecuzioni", "siecic_v6/Prof-siecic-esecuzioni.xsd", ROLE_CTU),
    _sici("AttoSistemaSiecic", "base_v3/Sistema-pubbl-siecic.xsd", system_only=True),
    ActiveMinisterialSchema(
        "Introduttivi_SIGP",
        "docs/specs/ministero/schema/sigp_v3/Introduttivi.xsd",
        "XSD_SIGP_20241128.zip",
        "in esercizio",
        (ROLE_AVVOCATO,),
    ),
    ActiveMinisterialSchema(
        "CorsoCausa_SIGP",
        "docs/specs/ministero/schema/sigp_v3/CorsoCausa.xsd",
        "XSD_SIGP_20241128.zip",
        "in esercizio",
        (ROLE_AVVOCATO,),
    ),
    ActiveMinisterialSchema(
        "Professionista_SIGP",
        "docs/specs/ministero/schema/sigp_v3/Professionista.xsd",
        "XSD_SIGP_20241128.zip",
        "in esercizio",
        (ROLE_CTU,),
    ),
    ActiveMinisterialSchema(
        "AttoSistema_SIGP",
        "docs/specs/ministero/schema/sigp_v3/Sistema-pubbl-sigp.xsd",
        "XSD_SIGP_20241128.zip",
        "in esercizio",
        (),
        True,
    ),
    ActiveMinisterialSchema(
        "ParteCassazione",
        f"docs/specs/ministero/parte/parte_{PST_CASSAZIONE_XSD_ACTIVE_VERSION}/Parte-cassazione.xsd",
        "XSD_Cassazione_20260227.zip",
        "04/03/2026",
        (ROLE_AVVOCATO,),
    ),
    ActiveMinisterialSchema(
        "UNEP",
        "docs/specs/ministero/XSD PLO118 FASE2 per SW House/schema/atti-unep.xsd",
        "XSD_PLO118_FASE2_per_SW_House_20241106.zip",
        "in esercizio",
        (ROLE_AVVOCATO,),
    ),
)


def active_schema_paths() -> tuple[Path, ...]:
    """Restituisce solo gli entry point correnti; versioni storiche/preview restano escluse."""
    return tuple(schema.path for schema in ACTIVE_MINISTERIAL_SCHEMAS)


@lru_cache(maxsize=1)
def active_ministerial_root_index() -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for schema in ACTIVE_MINISTERIAL_SCHEMAS:
        root = etree.parse(str(schema.path)).getroot()
        namespace = str(root.get("targetNamespace") or "")
        for element in root.findall(f"{{{_XSD_NS}}}element"):
            root_name = str(element.get("name") or "").strip()
            if not root_name:
                continue
            index[(schema.generator_class, root_name)] = {
                "active": True,
                "generatorClass": schema.generator_class,
                "ministerialRoot": root_name,
                "namespace": namespace,
                "schemaPath": schema.relative_path,
                "packageName": schema.package_name,
                "productionSince": schema.production_since,
                "allowedProfessionalRoles": list(schema.allowed_professional_roles),
                "systemOnly": schema.system_only,
                "selectableByProfessional": bool(schema.allowed_professional_roles) and not schema.system_only,
            }
    return index


def active_xsd_association(generator_class: str, root_name: str) -> dict[str, Any]:
    generator_class = str(generator_class or "").strip()
    root_name = str(root_name or "").strip()
    association = active_ministerial_root_index().get((generator_class, root_name))
    if association:
        return dict(association)
    return {
        "active": False,
        "generatorClass": generator_class,
        "ministerialRoot": root_name,
        "namespace": "",
        "schemaPath": "",
        "packageName": "",
        "productionSince": "",
        "allowedProfessionalRoles": [],
        "systemOnly": False,
        "selectableByProfessional": False,
        "reason": (
            "La radice non appartiene agli XSD ministeriali in esercizio oppure non ha ancora "
            "un generatore IUSENTRA completo; resta censita ma non è esponibile per un deposito reale."
        ),
    }


def normalize_professional_role(value: Any) -> str:
    normalized = str(value or "").strip().upper().replace(" ", "")
    if normalized in {"CUR", "CURATORE"}:
        return ROLE_CURATORE
    if normalized in {"CUS", "CUSTODE"}:
        return ROLE_CUSTODE
    if normalized in {"DEL", "DELEGATO", "DELEGATOALLEVENDITE"}:
        return ROLE_DELEGATO
    if normalized in {"CTU", "CONSULENTE", "PERITO"}:
        return ROLE_CTU
    return ROLE_AVVOCATO


def association_visible_for_role(association: dict[str, Any], professional_role: Any) -> bool:
    if not association.get("active") or association.get("systemOnly"):
        return False
    return normalize_professional_role(professional_role) in set(association.get("allowedProfessionalRoles") or [])


def filter_entries_for_professional_role(
    entries: Iterable[dict[str, Any]], professional_role: Any
) -> tuple[dict[str, Any], ...]:
    role = normalize_professional_role(professional_role)
    return tuple(
        entry
        for entry in entries
        if role in set((entry.get("access") or {}).get("allowedProfessionalRoles") or [])
        and not bool((entry.get("access") or {}).get("systemOnly"))
    )


def active_catalog_summary(operational_entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    index = active_ministerial_root_index()
    linked = {
        (
            str((entry.get("schema") or {}).get("generatorClass") or ""),
            str((entry.get("schema") or {}).get("ministerialRoot") or ""),
        )
        for entry in operational_entries
        if (entry.get("schema") or {}).get("activeXsd", {}).get("active")
    }
    by_generator: dict[str, dict[str, int]] = {}
    for generator_class, _root_name in index:
        by_generator.setdefault(generator_class, {"activeRoots": 0, "operationalRoots": 0})[
            "activeRoots"
        ] += 1
    for generator_class, root_name in linked:
        if (generator_class, root_name) in index:
            by_generator.setdefault(generator_class, {"activeRoots": 0, "operationalRoots": 0})[
                "operationalRoots"
            ] += 1
    return {
        "policy": "explicit-active-entry-points",
        "activeSchemas": len(ACTIVE_MINISTERIAL_SCHEMAS),
        "activeRoots": len(index),
        "operationalRoots": len(linked),
        "uncataloguedRoots": len(set(index) - linked),
        "byGeneratorClass": by_generator,
        "historicalAndPreviewSchemasSelectable": False,
        "uncataloguedActsPolicy": "censiti_non_esponibili_senza_generatore_completo",
    }


__all__ = [
    "ACTIVE_MINISTERIAL_SCHEMAS",
    "ROLE_AVVOCATO",
    "ROLE_CTU",
    "ROLE_CURATORE",
    "ROLE_CUSTODE",
    "ROLE_DELEGATO",
    "active_catalog_summary",
    "active_ministerial_root_index",
    "active_schema_paths",
    "active_xsd_association",
    "association_visible_for_role",
    "filter_entries_for_professional_role",
    "normalize_professional_role",
]
