"""Compatibilità tecnica dei lettori dichiarata dal pacchetto dati verificato.

La politica arriva da configurazione di distribuzione con SHA atteso, mai dal
caso, dai fatti o dalla risposta del modello. Non approva norme o vigenze.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re


_SOURCES = frozenset(("versioni_akn.py", "normattiva_akn_importer.py", "struttura.py",
                      "qualita_testo.py", "biblioteca/fabbisogno.py", "testi_archiviati.py"))


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class PoliticaLettori:
    lettori: frozenset[str]
    manifest_sha256: str | None = None
    rapporto_sha256: str | None = None


def politica_lettori(lettore_runtime: str) -> PoliticaLettori:
    if not _sha(lettore_runtime):
        raise ValueError("Impronta del lettore runtime non valida")
    name = os.environ.get("PCT_NORMATTIVA_LETTORI_MANIFEST")
    expected = os.environ.get("PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256")
    if not name and not expected:
        return PoliticaLettori(frozenset((lettore_runtime,)))
    if not name or not _sha(expected):
        raise ValueError("Politica lettori priva di percorso o SHA atteso")
    path = Path(name).resolve(strict=True)
    if path.stat().st_size > 256 * 1024:
        raise ValueError("Politica lettori oltre il limite")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Politica lettori alterata")
    policy = json.loads(raw)
    if not isinstance(policy, dict) or policy.get("schema") != 1 or policy.get("lettore_runtime") != lettore_runtime:
        raise ValueError("Politica lettori riferita a un altro runtime")
    records = policy.get("lettori")
    if not isinstance(records, list) or not records:
        raise ValueError("Elenco dei lettori attestati assente")
    accepted = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Dichiarazione del lettore non strutturata")
        digest = record.get("sha256")
        sources = record.get("sorgenti")
        if (not _sha(digest) or not isinstance(sources, dict) or set(sources) != _SOURCES
                or not all(_sha(v) for v in sources.values())):
            raise ValueError("Prova delle sorgenti del lettore incompleta")
        actual = hashlib.sha256(json.dumps(sources, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        if actual != digest or digest in accepted:
            raise ValueError("Impronta o unicità del lettore attestato discordante")
        accepted.add(digest)
    if lettore_runtime not in accepted:
        raise ValueError("Lettore runtime non compreso nella politica")
    if accepted == {lettore_runtime}:
        return PoliticaLettori(frozenset(accepted), expected)
    proof = policy.get("verifica_compatibilita")
    if not isinstance(proof, dict) or not _sha(proof.get("sha256")):
        raise ValueError("Rapporto di compatibilità assente")
    filename = proof.get("file")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Percorso rapporto di compatibilità assente")
    relative = Path(filename)
    if relative.is_absolute() or ".." in relative.parts or not str(relative):
        raise ValueError("Percorso rapporto di compatibilità non ammesso")
    report_path = (path.parent / relative).resolve(strict=True)
    if not report_path.is_relative_to(path.parent) or report_path.stat().st_size > 8 * 1024**2:
        raise ValueError("Rapporto fuori dal pacchetto o oltre il limite")
    report_raw = report_path.read_bytes()
    if hashlib.sha256(report_raw).hexdigest() != proof["sha256"]:
        raise ValueError("Rapporto di compatibilità alterato")
    report = json.loads(report_raw)
    if not isinstance(report, dict):
        raise ValueError("Rapporto di compatibilità non strutturato")
    cases = report.get("confronti")
    if (not isinstance(report, dict) or report.get("esito") != "verificato" or report.get("lettore_runtime") != lettore_runtime
            or set(report.get("lettori_origine", [])) != accepted - {lettore_runtime}
            or not isinstance(cases, list) or not cases):
        raise ValueError("Rapporto di compatibilità non conclusivo")
    checked_origins = set()
    for case in cases:
        if (not isinstance(case, dict) or case.get("lettore_origine") not in accepted - {lettore_runtime}
                or not _sha(case.get("xml_sha256")) or case.get("riscontro") != "identico"
                or not _sha(case.get("sha256_campi_origine"))
                or case["sha256_campi_origine"] != case.get("sha256_campi_runtime")):
            raise ValueError("Confronto del lettore precedente non riscontrato")
        checked_origins.add(case["lettore_origine"])
    if checked_origins != accepted - {lettore_runtime}:
        raise ValueError("Uno dei lettori precedenti non ha confronti verificati")
    return PoliticaLettori(frozenset(accepted), expected, proof["sha256"])
