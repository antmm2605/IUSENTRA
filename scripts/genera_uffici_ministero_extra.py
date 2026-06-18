"""Genera le righe PST ufficiali assenti dal bundle uffici IUSENTRA."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


TIPI_INCLUSI = {"CA", "OR", "TM", "PC", "PG", "GP", "SC", "UP"}
SERVIZI_JPW_PRIORITA = ("JPW_SIGP", "JPW_SICID", "JPW_SIECIC", "JPW_CASSCI", "JPW_CASSPE")


def _servizi(return_node: ET.Element) -> list[str]:
    out: list[str] = []
    for servizio in return_node.findall("servizi"):
        codice = (servizio.findtext("codice") or "").strip().upper()
        if codice and codice not in out:
            out.append(codice)
    return out


def _servizio_predefinito(servizi: list[str]) -> str:
    for candidato in SERVIZI_JPW_PRIORITA:
        if candidato in servizi:
            return candidato
    return ""


def _record_da_return(return_node: ET.Element) -> dict:
    servizi = _servizi(return_node)
    return {
        "codice_ministero": (return_node.findtext("codiceUfficio") or "").strip(),
        "codice_gl": (return_node.findtext("codiceGL") or "").strip(),
        "descrizione_ministero": (return_node.findtext("descrizione") or "").strip(),
        "tipo_ministero": (return_node.findtext("tipoUfficio") or "").strip(),
        "tipo_ministero_descrizione": (return_node.findtext("descTipoUfficio") or "").strip(),
        "comune_ministero": (return_node.findtext("comune") or "").strip(),
        "distretto_ministero": (return_node.findtext("distretto") or "").strip().title(),
        "distretto_gl": (return_node.findtext("descGL") or "").replace("Distretto di ", "").strip(),
        "regione_ministero": (return_node.findtext("regione") or "").strip(),
        "provincia_ministero": (return_node.findtext("provincia") or "").strip(),
        "pec_ministero": (return_node.findtext("indirizzoPec") or "").strip().lower(),
        "nome_certificato_cifra": (return_node.findtext("nomeCertificatoCifra") or "").strip(),
        "certificato_mimetype": (return_node.findtext("certificatoMimetype") or "").strip(),
        "servizi_ministero": servizi,
        "servizio_pst_predefinito": _servizio_predefinito(servizi),
    }


def genera(input_xml: Path, output_json: Path, riferimenti_json: Path) -> dict:
    riferimenti = json.loads(riferimenti_json.read_text(encoding="utf-8"))
    codici_mappati = {
        str(ref.get("codice_ministero") or "").strip()
        for ref in (riferimenti.get("uffici") or {}).values()
        if str(ref.get("codice_ministero") or "").strip()
    }

    root = ET.parse(input_xml).getroot()
    extras: list[dict] = []
    for return_node in root.iter("return"):
        tipo = (return_node.findtext("tipoUfficio") or "").strip().upper()
        codice = (return_node.findtext("codiceUfficio") or "").strip()
        descrizione = (return_node.findtext("descrizione") or "").strip()
        servizi = _servizi(return_node)
        if tipo not in TIPI_INCLUSI:
            continue
        if not codice or codice in codici_mappati:
            continue
        if not servizi:
            continue
        if codice.startswith("987654321") or "Model Office" in descrizione or "Formazione" in descrizione:
            continue
        extras.append(_record_da_return(return_node))

    extras.sort(key=lambda item: (item["tipo_ministero"], item["descrizione_ministero"], item["codice_ministero"]))
    payload = {
        "fonte": str(input_xml),
        "generato_il": datetime.now().isoformat(timespec="seconds"),
        "criterio": (
            "Righe PST ufficiali con servizi telematici, assenti dalla mappatura interna storica; "
            "sono esclusi Model Office/Formazione e tipologie non usate dal resolver PCT/SIGP/UNEP principale."
        ),
        "tipi_inclusi": sorted(TIPI_INCLUSI),
        "n_uffici": len(extras),
        "uffici": extras,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=r"C:\QuickOrganizer\ListaUfficiGiudiziari.xml")
    parser.add_argument("--output", default="pct/data/uffici_ministero_extra.json")
    parser.add_argument("--riferimenti", default="pct/data/uffici_ministero.json")
    args = parser.parse_args()
    payload = genera(Path(args.input), Path(args.output), Path(args.riferimenti))
    print(json.dumps({"ok": True, "n_uffici": payload["n_uffici"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
