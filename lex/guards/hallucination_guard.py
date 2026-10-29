"""Guardia anti allucinazione per Lex."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from lex.contracts import GuardVerdict


_STRICT_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


@dataclass(frozen=True, slots=True)
class _LegalReference:
    kind: str
    key: str
    label: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


# «Corte cost.», «C. cost.», «Corte Cost.» → «corte costituzionale»; «sent.»/«ord.» → sentenza/ordinanza.
_CORTE_COST_BREVE = re.compile(r"\b(?:corte|c\.)\s*cost\.(?!\w)")
_SENT_ORD_BREVE = re.compile(r"\b(sent|ord)\.(?=\s*(?:n\.|numero))")
_CONS_STATO_BREVE = re.compile(r"\bcons\.\s*(?:di\s+)?st(?:ato|\.)(?!\w)")
_TAR_BREVE = re.compile(r"\bt\.\s*a\.\s*r\.?(?!\w)")


def _normalize(value: Any) -> str:
    text = _clean(value).lower()
    text = _CORTE_COST_BREVE.sub("corte costituzionale", text)
    text = _SENT_ORD_BREVE.sub(lambda m: "sentenza" if m.group(1) == "sent" else "ordinanza", text)
    text = _CONS_STATO_BREVE.sub("consiglio di stato", text)
    text = _TAR_BREVE.sub("tar", text)
    return (
        text.replace("codice civile", "c.c.")
        .replace("codice di procedura civile", "c.p.c.")
        .replace("codice procedura civile", "c.p.c.")
        .replace("codice penale", "c.p.")
        .replace("codice di procedura penale", "c.p.p.")
        .replace("decreto legislativo", "d.lgs.")
        .replace("decreto ministeriale", "d.m.")
        .replace("decreto del presidente della repubblica", "d.p.r.")
        .replace("decreto-legge", "d.l.")
        .replace("decreto legge", "d.l.")
        .replace("corte di cassazione", "cassazione")
    )


# Le forme con cui un modello scrive gli stessi estremi: «articolo 2043», «artt. 1218
# e 1223», «Cass. n. 123/2020», «L. 689/1981», «d.P.R. 115/2002», «D.L. 179/2012».
_ARTICOLO = re.compile(r"\b(?:artt?\.|articol[oi])\s*(\d+[a-z]*(?:[-/]\w+)?)(?:\s*(?:,|e)\s*(\d+[a-z]*))?(?:\s*(?:,|del|della|del\s+codice)?\s*)(c\.c\.|c\.p\.c\.|c\.p\.p\.|c\.p\.|cost\.)?")
# Fra autorita' e numero il modello scrive sezione, data e abbreviazioni puntate («Cass. civ., sez. III,
# 12 marzo 2021, n. 9999»): i punti delle abbreviazioni non chiudono la citazione, gli altri si'.
_ABBREVIAZIONI = ("sez", "civ", "pen", "lav", "un", "unite", "trib", "sent", "ord", "s", "u", "sc", "amm", "pres",
                  "rel", "ud", "dep", "pubbl", "giur", "sect", "cass", "c", "st", "reg", "sic", "camp", "lomb")
_PUNTO_ABBREVIAZIONE = "(?:" + "|".join(rf"(?<=\b{a})" for a in _ABBREVIAZIONI) + r")\."
_TRATTO_CITAZIONE = rf"(?:[^.\n;]|{_PUNTO_ABBREVIAZIONE})"
_CASSAZIONE_BREVE = re.compile(
    rf"\bcass\b\.?{_TRATTO_CITAZIONE}{{0,80}}?(?:n\.|numero)\s*(\d{{1,7}})(?:\s*/\s*(\d{{4}})|\s+del\s+(?:\d{{1,2}}\s+[a-z]+\s+)?(\d{{4}}))?"
)
_AUTORITA = re.compile(
    rf"\b(cassazione|corte costituzionale|consiglio di stato|tar(?:\s+(?!n\.)[a-z]+)?)\b{_TRATTO_CITAZIONE}{{0,80}}?"
    r"(?:sentenza|ordinanza|pronuncia|decreto)?\s*(?:n\.|numero)\s*(\d{1,7})(?:\s*/\s*(\d{4})|\s+del\s+(?:\d{1,2}\s+[a-z]+\s+)?(\d{4}))?"
)
_ANNO = re.compile(r"\b(?:19|20)\d{2}\b")
_ECLI_CORTI = {"cass": "cassazione", "cost": "corte costituzionale", "cds": "consiglio di stato", "cga": "consiglio di stato"}


def _anno_nel_tratto(tratto: str) -> str:
    """Anno della data scritta fra autorita' e numero («Sez. Un., 12 marzo 2021, n. 9999»)."""
    anni = _ANNO.findall(tratto)
    return anni[-1] if anni else ""


def _classe_autorita(autorita: str) -> str:
    """Classe dell'organo: «sentenza»/«ordinanza» senza organo restano generiche (stringa vuota)."""
    a = _clean(autorita).lower()
    if a in {"sentenza", "ordinanza", "pronuncia", "decreto", ""}:
        return ""
    if a == "tar" or a.startswith("tar "):
        return "tar"
    return a


def _add_reference(refs: list[_LegalReference], kind: str, key: str, label: str) -> None:
    clean_key = _normalize(key)
    if not clean_key:
        return
    ref = _LegalReference(kind=kind, key=clean_key, label=_clean(label) or clean_key)
    if ref not in refs:
        refs.append(ref)


def extract_legal_references(text: Any) -> list[_LegalReference]:
    """Estrae riferimenti giuridici specifici senza dipendere da stringhe identiche."""

    normalized = _normalize(text)
    if not normalized:
        return []

    refs: list[_LegalReference] = []
    for match in _AUTORITA.finditer(normalized):
        authority, number, year_slash, year_del = match.groups()
        year = year_slash or year_del or _anno_nel_tratto(normalized[match.end(1):match.start(2)])
        key = f"{authority}:{number}:{year or ''}"
        _add_reference(refs, "case_law", key, match.group(0))

    for match in re.finditer(r"\b(sentenza|ordinanza)\s+(?:n\.|numero)\s*(\d{1,7})(?:\s*/\s*|\s+del\s+)(\d{4})", normalized):
        kind, number, year = match.groups()
        _add_reference(refs, "case_law", f"{kind}:{number}:{year}", match.group(0))

    for match in re.finditer(r"\becli:[a-z0-9:.]+", normalized):
        ecli = match.group(0).rstrip(".:")
        _add_reference(refs, "ecli", ecli, ecli)
        parti = ecli.split(":")
        if len(parti) >= 5 and parti[1] == "it":
            corte = _ECLI_CORTI.get(parti[2]) or ("tar" if parti[2].startswith("tar") else "")
            numero = re.match(r"0*(\d{1,7})", parti[4])
            if corte and numero and re.fullmatch(r"\d{4}", parti[3]):
                _add_reference(refs, "case_law", f"{corte}:{numero.group(1)}:{parti[3]}", ecli)

    for match in _CASSAZIONE_BREVE.finditer(normalized):
        number, year_slash, year_del = match.groups()
        year = year_slash or year_del or _anno_nel_tratto(normalized[match.start():match.start(1)])
        _add_reference(refs, "case_law", f"cassazione:{number}:{year}", match.group(0))

    for match in _ARTICOLO.finditer(normalized):
        article, second, code = match.groups()
        code_key = code or ""
        _add_reference(refs, "article", f"art:{article}:{code_key}", match.group(0))
        if second:
            _add_reference(refs, "article", f"art:{second}:{code_key}", match.group(0))

    normative_patterns = (
        ("legge", r"(?<!\.)\b(?:legge|l\.)\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_lgs", r"\bd\.\s*lgs\.?\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_m", r"\bd\.\s*m\.?\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_p_r", r"\bd\.\s*p\.\s*r\.?\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_l", r"\bd\.\s*l\.\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
    )
    for kind, pattern in normative_patterns:
        for match in re.finditer(pattern, normalized):
            number, year = match.groups()
            _add_reference(refs, kind, f"{kind}:{number}:{year}", match.group(0))

    return refs


def _text_from_row(row: Any) -> str:
    if isinstance(row, dict):
        metadata = dict(row.get("metadata") or {})
        return " ".join(
            _clean(value)
            for value in (
                row.get("title"),
                row.get("content"),
                row.get("excerpt"),
                row.get("text"),
                row.get("citation"),
                row.get("official_url"),
                row.get("url"),
                metadata.get("ecli"),
                metadata.get("numero_sentenza"),
                metadata.get("anno_sentenza"),
                metadata.get("numero_provvedimento"),
                metadata.get("anno"),
            )
            if _clean(value)
        )
    metadata = dict(getattr(row, "metadata", {}) or {})
    return " ".join(
        _clean(value)
        for value in (
            getattr(row, "title", ""),
            getattr(row, "content", ""),
            getattr(row, "excerpt", ""),
            getattr(row, "official_url", ""),
            metadata.get("ecli"),
            metadata.get("numero_sentenza"),
            metadata.get("anno_sentenza"),
            metadata.get("numero_provvedimento"),
            metadata.get("anno"),
        )
        if _clean(value)
    )


def _evidence_rows(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return [*list(evidence.get("items") or []), *list(evidence.get("citations") or [])]
    return [*list(getattr(evidence, "items", []) or []), *list(getattr(evidence, "citations", []) or [])]


def _supported_by_evidence(ref: _LegalReference, evidence_refs: Iterable[_LegalReference]) -> bool:
    refs = list(evidence_refs or [])
    if ref in refs:
        return True
    for candidate in refs:
        if candidate.kind == ref.kind and candidate.key == ref.key:
            return True
        if ref.kind == "article" and candidate.kind == "article":
            ref_parts = ref.key.split(":")
            candidate_parts = candidate.key.split(":")
            if len(ref_parts) >= 2 and len(candidate_parts) >= 2 and ref_parts[1] == candidate_parts[1]:
                ref_code = ref_parts[2] if len(ref_parts) > 2 else ""
                candidate_code = candidate_parts[2] if len(candidate_parts) > 2 else ""
                if not ref_code or not candidate_code or ref_code == candidate_code:
                    return True
        if ref.kind == "case_law" and candidate.kind == "case_law" and _stessa_pronuncia(ref.key, candidate.key):
            return True
    return False


def _parti_pronuncia(key: str) -> tuple[str, str, str] | None:
    parti = key.rsplit(":", 2)
    if len(parti) != 3 or not parti[1].isdigit():
        return None
    return _classe_autorita(parti[0]), parti[1], parti[2]


def _stessa_pronuncia(ref_key: str, candidate_key: str) -> bool:
    """Stesso numero e anno e stesso organo: «Cass. n. 1234/2020» non e' «Cons. Stato n. 1234/2020».

    Un riferimento che nomina l'organo esige un'evidenza dello stesso organo; un riferimento generico
    («sentenza n. 1234/2020») e' coperto da qualunque evidenza con stesso numero e anno.
    """
    ref, candidate = _parti_pronuncia(ref_key), _parti_pronuncia(candidate_key)
    if ref is None or candidate is None or ref[1] != candidate[1]:
        return False
    if ref[2] and ref[2] != candidate[2]:
        return False
    return not ref[0] or ref[0] == candidate[0]


_AUTORITA_DA_HOST = (("cortedicassazione.it", "cassazione"), ("italgiure.giustizia.it", "cassazione"),
                     ("cortecostituzionale.it", "corte costituzionale"))


def _autorita_della_riga(row: Any) -> str:
    """Organo dichiarato dalla riga di evidenza (campo autorita'/organo o dominio ufficiale), se univoco."""
    get = (lambda k: row.get(k)) if isinstance(row, dict) else (lambda k: getattr(row, k, None))
    metadata = dict(get("metadata") or {})
    for value in (get("organo_giudicante"), metadata.get("organo_giudicante"), metadata.get("autorita"),
                  metadata.get("court"), get("authority")):
        for match in _AUTORITA.finditer(_normalize(f"{value or ''} n. 1/2000")):
            return _classe_autorita(match.group(1))
    url = _clean(get("official_url") or get("url") or metadata.get("official_url")).lower()
    return next((corte for host, corte in _AUTORITA_DA_HOST if host in url), "")


def _riferimenti_della_riga(row: Any) -> list[_LegalReference]:
    refs = extract_legal_references(_text_from_row(row))
    autorita = _autorita_della_riga(row)
    if autorita:
        for ref in list(refs):
            parti = _parti_pronuncia(ref.key) if ref.kind == "case_law" else None
            if parti is not None and not parti[0]:
                _add_reference(refs, "case_law", f"{autorita}:{parti[1]}:{parti[2]}", ref.label)
    return refs


def _abrogazione_della_riga(row: Any) -> dict | None:
    from lex.retrieval.abrogazione import abrogazione

    get = (lambda k: row.get(k)) if isinstance(row, dict) else (lambda k: getattr(row, k, None))
    metadata = dict(get("metadata") or {})
    if get("abrogato") is True or metadata.get("abrogato") is True:
        return {"abrogato": True, "abrogato_da": _clean(get("abrogato_da") or metadata.get("abrogato_da"))}
    for field in ("content", "text", "excerpt", "testo", "normative_full_text"):
        esito = abrogazione(get(field))
        if esito:
            return esito
    return None


def _numero_articolo(ref: _LegalReference) -> str:
    parti = ref.key.split(":")
    return parti[1] if len(parti) >= 2 else ""


def _citato_come_abrogato(draft_text: str, numero: str) -> bool:
    """Ogni citazione dell'articolo nella bozza dichiara nelle vicinanze che e' abrogato."""
    testo = _normalize(draft_text)
    occorrenze = list(re.finditer(rf"\b(?:artt?\.|articol[oi])\s*{re.escape(numero)}(?![\w])", testo))
    if not occorrenze:
        return False
    return all(re.search(r"abrogat|abrogazione|non (?:piu|più) (?:vigente|in vigore)",
                         testo[max(0, m.start() - 150): m.end() + 200]) for m in occorrenze)


class HallucinationGuard:
    def check(self, **kwargs):
        workflow = str(kwargs.get("workflow") or "")
        evidence = kwargs.get("evidence") or {}
        draft = kwargs.get("draft")
        draft_text = str(getattr(draft, "text", "") or "").strip()
        if not draft_text:
            return GuardVerdict(allowed=False, reasons=["Empty provider draft"], risk_level="high")

        draft_refs = extract_legal_references(draft_text)
        if not draft_refs:
            return GuardVerdict(allowed=True)

        rows = _evidence_rows(evidence)
        evidence_refs: list[_LegalReference] = []
        abrogati: list[tuple[_LegalReference, str]] = []
        for row in rows:
            refs_riga = _riferimenti_della_riga(row)
            evidence_refs.extend(refs_riga)
            esito_abrogazione = _abrogazione_della_riga(row)
            if esito_abrogazione:
                abrogati.extend((ref, esito_abrogazione.get("abrogato_da", "")) for ref in refs_riga if ref.kind == "article")

        # Un articolo che nelle evidenze e' solo un avviso di abrogazione non si cita come norma operativa.
        operativi_abrogati = []
        for ref in draft_refs:
            if ref.kind != "article":
                continue
            for abrogato, da in abrogati:
                if _supported_by_evidence(ref, [abrogato]) and not _citato_come_abrogato(draft_text, _numero_articolo(ref)):
                    operativi_abrogati.append(f"{ref.label} (abrogato{' da ' + da if da else ''})")
                    break
        if operativi_abrogati:
            return GuardVerdict(
                allowed=False,
                warnings=["Articoli citati come vigenti ma abrogati secondo le evidenze: " + ", ".join(operativi_abrogati[:4]) + "."],
                reasons=["La bozza presenta come operativa una norma il cui testo archiviato e' un avviso di abrogazione."],
                risk_level="high",
            )

        strict = workflow in _STRICT_WORKFLOWS
        if strict and not rows:
            return GuardVerdict(
                allowed=False,
                warnings=["La bozza contiene riferimenti giuridici specifici senza evidenze."],
                reasons=["Workflow strict con riferimenti normativi/giurisprudenziali non fondati."],
                risk_level="high",
            )

        missing = [ref for ref in draft_refs if not _supported_by_evidence(ref, evidence_refs)]
        if strict and missing:
            labels = ", ".join(ref.label for ref in missing[:4])
            return GuardVerdict(
                allowed=False,
                warnings=[f"Riferimenti giuridici non presenti nelle evidenze: {labels}."],
                reasons=["La bozza contiene estremi normativi o giurisprudenziali non supportati dal pacchetto evidenze."],
                risk_level="high",
            )

        if missing:
            labels = ", ".join(ref.label for ref in missing[:6])
            # Nei workflow di redazione la bozza non si blocca, ma l'avvocato deve
            # leggere nel testo stesso quali estremi non vengono dalle fonti:
            # un riferimento non verificato non si presenta mai come certo.
            avviso = (
                "\n\n**Da verificare prima dell'uso** — questi riferimenti non si ritrovano nelle fonti consultate "
                f"e vanno controllati sulla fonte ufficiale: {labels}."
            )
            return GuardVerdict(
                allowed=True,
                warnings=[f"Riferimenti giuridici da verificare prima dell'uso: {labels}."],
                reasons=["Riferimenti rilevati nella bozza non allineati alle evidenze disponibili."],
                risk_level="medium",
                rewritten_draft=None if "Da verificare prima dell'uso" in draft_text else draft_text + avviso,
            )
        return GuardVerdict(allowed=True)


__all__ = ["HallucinationGuard", "extract_legal_references"]
