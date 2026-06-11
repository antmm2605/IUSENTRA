"""Conflitto di interessi: ricerca cliente/controparte/gruppo.

Base deontologica: l'avvocato non può assistere parti con interessi confliggenti
(art. 24 Codice Deontologico Forense; artt. 37 e 68). Qui rileviamo conflitti
DIRETTI (il soggetto è già controparte in un altro fascicolo, o la controparte
proposta è già nostro cliente) e POTENZIALI (stesso gruppo, match solo per nome
senza codice fiscale), lasciando la decisione finale all'avvocato con waiver
tracciato.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Party:
    name: str
    codice_fiscale: str = ""
    group: str = ""
    role: str = "cliente"  # "cliente" | "controparte"


@dataclass(frozen=True)
class ExistingParty:
    name: str
    codice_fiscale: str = ""
    group: str = ""
    role: str = "cliente"
    matter_id: str = ""


@dataclass(frozen=True)
class ConflictFinding:
    severity: str  # "diretto" | "potenziale"
    reason: str
    matter_id: str = ""
    matched_name: str = ""

    def to_public(self) -> dict[str, Any]:
        return {"severity": self.severity, "reason": self.reason, "matterId": self.matter_id, "matchedName": self.matched_name}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def _norm_cf(cf: str) -> str:
    return str(cf or "").strip().upper()


def _same_subject(a_name: str, a_cf: str, b_name: str, b_cf: str) -> tuple[bool, bool]:
    """Ritorna (match, only_by_name). match True se stesso soggetto."""

    a_cf, b_cf = _norm_cf(a_cf), _norm_cf(b_cf)
    if a_cf and b_cf:
        return (a_cf == b_cf, False)
    return (normalize_name(a_name) == normalize_name(b_name) and bool(normalize_name(a_name)), True)


def check_conflict(candidate_client: Party, candidate_counterparty: Party | None, existing: list[ExistingParty]) -> list[ConflictFinding]:
    """Verifica i conflitti per un nuovo incarico.

    - Il nostro nuovo cliente è già controparte altrove → conflitto DIRETTO.
    - La controparte proposta è già nostro cliente altrove → conflitto DIRETTO.
    - Stesso gruppo della controparte esistente / match solo per nome → POTENZIALE.
    """

    findings: list[ConflictFinding] = []
    cand_group = normalize_name(candidate_client.group)

    for party in existing:
        match_client, by_name_c = _same_subject(candidate_client.name, candidate_client.codice_fiscale, party.name, party.codice_fiscale)
        if match_client and party.role == "controparte":
            sev = "potenziale" if by_name_c else "diretto"
            findings.append(ConflictFinding(sev, "Il nuovo cliente risulta già controparte in un fascicolo esistente.", party.matter_id, party.name))

        if candidate_counterparty is not None:
            match_cp, by_name_cp = _same_subject(candidate_counterparty.name, candidate_counterparty.codice_fiscale, party.name, party.codice_fiscale)
            if match_cp and party.role == "cliente":
                sev = "potenziale" if by_name_cp else "diretto"
                findings.append(ConflictFinding(sev, "La controparte proposta è già assistita come cliente dello studio.", party.matter_id, party.name))
            if match_cp and party.role == "controparte" and by_name_cp:
                findings.append(ConflictFinding("potenziale", "La controparte proposta compare in un altro fascicolo (match solo per nome).", party.matter_id, party.name))

        if cand_group and normalize_name(party.group) == cand_group and party.role == "controparte":
            findings.append(ConflictFinding("potenziale", "Il nuovo cliente appartiene allo stesso gruppo di una controparte esistente.", party.matter_id, party.name))

    return _dedupe(findings)


def _dedupe(findings: list[ConflictFinding]) -> list[ConflictFinding]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[ConflictFinding] = []
    for f in findings:
        key = (f.severity, f.reason, f.matter_id, f.matched_name)
        if key not in seen:
            seen.add(key)
            out.append(f)
    # Conflitti diretti per primi.
    return sorted(out, key=lambda x: 0 if x.severity == "diretto" else 1)


@dataclass
class ConflictReport:
    findings: list[ConflictFinding] = field(default_factory=list)

    @property
    def has_direct(self) -> bool:
        return any(f.severity == "diretto" for f in self.findings)

    @property
    def has_potential(self) -> bool:
        return any(f.severity == "potenziale" for f in self.findings)

    @property
    def clear(self) -> bool:
        return not self.findings

    def to_public(self) -> dict[str, Any]:
        return {
            "clear": self.clear,
            "hasDirect": self.has_direct,
            "hasPotential": self.has_potential,
            "findings": [f.to_public() for f in self.findings],
        }


def build_conflict_report(candidate_client: Party, candidate_counterparty: Party | None, existing: list[ExistingParty]) -> ConflictReport:
    return ConflictReport(check_conflict(candidate_client, candidate_counterparty, existing))


__all__ = [
    "Party",
    "ExistingParty",
    "ConflictFinding",
    "ConflictReport",
    "normalize_name",
    "check_conflict",
    "build_conflict_report",
]
