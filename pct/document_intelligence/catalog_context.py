"""Profilo documentale dai dati espliciti e dal catalogo PST ufficiale.

Nessuna modifica al profilo di deposito, nessuna inferenza da prefissi numerici.
Le descrizioni sono risolte soltanto quando coincidono con una voce univoca.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any
import hashlib
import json
import re
import unicodedata

from pct.pratiche_collegate_catalog import load_codici_oggetto_pst_catalog


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


@lru_cache(maxsize=1)
def _official_index() -> tuple[dict[str, dict], dict[str, dict], str]:
    catalog = load_codici_oggetto_pst_catalog()
    records = [row for row in catalog.get("records", []) if row.get("fonte") == "PST_XSD" and row.get("fileFonte")]
    by_code = {str(row["codice"]): row for row in records}
    by_description: dict[str, list[dict]] = {}
    for row in records:
        by_description.setdefault(_key(row.get("descrizione")), []).append(row)
    unique = {name: rows[0] for name, rows in by_description.items() if name and len(rows) == 1}
    digest = hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return by_code, unique, digest


def enrich_official_context(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    # I profili compilati non vengono sostituiti dal catalogo ministeriale:
    # quello che l'avvocato ha scritto resta com'e'. Ma "compilato" vuol dire
    # completo. Finche' bastava un campo su tre per fermare l'arricchimento,
    # un fascicolo con la sola area — che e' la forma normale, perche' branca
    # e sottofamiglia stanno solo nel profilo di deposito — non arrivava mai a
    # un profilo, e ogni suo documento restava "da verificare" anche quando il
    # fascicolo portava un codice oggetto ministeriale che lo identificava.
    campi_profilo = ("area", "branca", "sottobranca")
    gia_compilati = {
        campo: str(context.get(campo) or "").strip() for campo in campi_profilo
    }
    if all(gia_compilati.values()):
        return result
    by_code, by_description, digest = _official_index()
    code = str(context.get("codice_oggetto_pst") or "").strip()
    row = by_code.get(code) if code else by_description.get(_key(context.get("oggetto")))
    if row is None:
        return result
    channel = _key(context.get("canale"))
    if channel in {"pat", "siga", "ptt", "sigit", "pdp", "ppt", "penale"} or _key(context.get("tipo_fascicolo")) in {"penale", "amministrativo", "tributario"}:
        return result
    area = str(row.get("area") or "Catalogo ministeriale PST")
    description = str(row["descrizione"])
    profile = {
        "Contenzioso civile": "CIV-PCT",
        "Controversie agrarie": "CIV-PCT",
        "Lavoro e previdenza": "LAV",
        "Esecuzioni immobiliari": "CIV-ESE",
        "Esecuzioni mobiliari / obblighi": "CIV-ESE",
        "Volontaria giurisdizione": "VGS",
        "Procedimenti speciali sommari": "CIV-MON-CAU",
    }.get(area, "PST")
    # Si riempiono solo le caselle vuote: un valore scritto dall'avvocato non
    # viene mai sovrascritto dal catalogo.
    dal_catalogo = {
        "area": area,
        "branca": str(row.get("descrizionePadre") or description),
        "sottobranca": description,
    }
    completato = {
        campo: (gia_compilati[campo] or dal_catalogo[campo]) for campo in campi_profilo
    }
    # Se il catalogo non copre quello che mancava, non si dichiara un profilo
    # ufficiale che non c'e': meglio la revisione che una catalogazione senza
    # fondamento.
    if not all(completato.values()):
        return result
    result.update({
        **completato,
        "_official_profile_id": profile,
        "_official_object_code": str(row["codice"]),
        "_official_object_file": str(row["fileFonte"]),
        "_official_catalog_sha256": digest,
        "_official_profile_reason": f"oggetto del fascicolo corrispondente alla voce ministeriale {row['codice']}: {description}",
    })
    return result


def fascicolo_catalog_context(fascicolo: Any) -> dict[str, Any]:
    profile = getattr(fascicolo, "profilo_deposito", {}) or {}
    profile = profile if isinstance(profile, dict) else {}
    practice = profile.get("pratica") if isinstance(profile.get("pratica"), dict) else {}
    code = profile.get("codice_deposito") if isinstance(profile.get("codice_deposito"), dict) else {}
    return enrich_official_context({
        "area": profile.get("area") or profile.get("area_pratica") or practice.get("area_pratica") or getattr(fascicolo, "area_pratica", ""),
        "branca": profile.get("branca") or profile.get("branch") or profile.get("materia") or "",
        "sottobranca": profile.get("sottobranca") or profile.get("subfamily") or profile.get("sottomateria") or "",
        "giurisdizione": profile.get("giurisdizione") or getattr(fascicolo, "tribunale", ""),
        "rito": profile.get("rito") or getattr(fascicolo, "tipo_procedimento", ""),
        "fase": profile.get("fase") or "",
        "canale": profile.get("canale_telematico") or getattr(fascicolo, "canale_operativo", "") or getattr(fascicolo, "source", ""),
        "source": getattr(fascicolo, "source", ""),
        "tipo_fascicolo": getattr(getattr(fascicolo, "tipo", ""), "value", getattr(fascicolo, "tipo", "")),
        "codice_oggetto_pst": getattr(fascicolo, "codice_oggetto_pst", "") or code.get("codice_oggetto_pst") or "",
        "oggetto": getattr(fascicolo, "oggetto", ""),
        "numero_rg": getattr(fascicolo, "numero_rg", ""),
        "anno_rg": getattr(fascicolo, "anno_rg", ""),
        # Il cliente del fascicolo: serve a riconoscere il suo documento d'identità dal contenuto.
        "cliente": str(getattr(fascicolo, "nome_cliente", "") or ""),
    })
