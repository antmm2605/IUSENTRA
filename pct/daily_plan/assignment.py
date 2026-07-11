"""Assegnazione deterministica delle attività agli avvocati dello studio.

Nel dominio gli avvocati compaiono come etichette testuali (``Fascicolo.
avvocato_referente``, ``Appuntamento.avvocato``) mentre solo la scadenza
porta un id utente (``Scadenza.id_utente_responsabile``). Il resolver
converte le etichette in utenti reali SENZA mai indovinare: i casi ambigui
finiscono nella coda studio "Da assegnare" (``assigned_user_id = ""``), che
non scompare mai dal piano.

Catena di assegnazione (primo esito valido):
1. avvocato referente del fascicolo;
2. avvocato indicato nell'evento agenda;
3. responsabile esplicito della scadenza (id utente, verificato attivo);
4. utente che ha preso in carico la PEC (se registrato);
5. dominus del fascicolo;
6. coda generale dello studio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

_HONORIFICS = re.compile(r"\b(avv\.?|avvocato|dott\.?|dr\.?|studio)\b", re.IGNORECASE)


def _normalize_label(label: str) -> str:
    testo = _HONORIFICS.sub(" ", str(label or ""))
    return " ".join(testo.split()).strip().lower()


@dataclass
class LawyerResolver:
    """Risolve etichette avvocato → utenti attivi dello studio."""

    users: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_full_name: dict[str, str] = {}
        self._by_username: dict[str, str] = {}
        surname_hits: dict[str, list[str]] = {}
        for user in self.users:
            user_id = str(user.get("id") or "").strip()
            if not user_id:
                continue
            self._by_id[user_id] = user
            full_name = _normalize_label(str(user.get("nome_completo") or ""))
            if full_name:
                self._by_full_name[full_name] = user_id
            username = str(user.get("username") or "").strip().lower()
            if username:
                self._by_username[username] = user_id
            for token in full_name.split():
                if len(token) >= 3:
                    surname_hits.setdefault(token, []).append(user_id)
        # un cognome risolve solo se appartiene a UN solo utente
        self._by_unique_token = {
            token: ids[0] for token, ids in surname_hits.items() if len(set(ids)) == 1
        }

    def display_name(self, user_id: str) -> str:
        user = self._by_id.get(str(user_id or ""))
        if not user:
            return ""
        return str(user.get("nome_completo") or user.get("username") or "")

    def is_active_user(self, user_id: str) -> bool:
        return str(user_id or "").strip() in self._by_id

    def resolve_label(self, label: str) -> str:
        """Etichetta → user id; '' se sconosciuta o ambigua (mai indovinare)."""
        normalized = _normalize_label(label)
        if not normalized:
            return ""
        if normalized in self._by_full_name:
            return self._by_full_name[normalized]
        if normalized in self._by_username:
            return self._by_username[normalized]
        tokens = normalized.split()
        if len(tokens) == 1:
            return self._by_unique_token.get(tokens[0], "")
        # più token: prova il match completo permutato (nome cognome vs cognome nome)
        reversed_name = " ".join(reversed(tokens))
        if reversed_name in self._by_full_name:
            return self._by_full_name[reversed_name]
        # ultimo tentativo: un solo token risolvibile e non ambiguo
        resolved = {self._by_unique_token.get(t, "") for t in tokens}
        resolved.discard("")
        if len(resolved) == 1:
            return resolved.pop()
        return ""


@dataclass(frozen=True)
class AssignmentCandidates:
    """Candidati raccolti dai segnali del gruppo, in ordine di catena."""

    fascicolo_referente: str = ""
    agenda_avvocato: str = ""
    responsible_user_id: str = ""
    pec_taker_user_id: str = ""
    fascicolo_dominus: str = ""


@dataclass(frozen=True)
class AssignmentResult:
    user_id: str
    lawyer_label: str
    source: str  # referente|agenda|responsabile|pec|dominus|coda_studio


def resolve_assignment(
    candidates: AssignmentCandidates, resolver: LawyerResolver
) -> AssignmentResult:
    referente = resolver.resolve_label(candidates.fascicolo_referente)
    if referente:
        return AssignmentResult(referente, resolver.display_name(referente), "referente")

    agenda = resolver.resolve_label(candidates.agenda_avvocato)
    if agenda:
        return AssignmentResult(agenda, resolver.display_name(agenda), "agenda")

    responsabile = str(candidates.responsible_user_id or "").strip()
    if responsabile and resolver.is_active_user(responsabile):
        return AssignmentResult(
            responsabile, resolver.display_name(responsabile), "responsabile"
        )

    pec_taker = str(candidates.pec_taker_user_id or "").strip()
    if pec_taker and resolver.is_active_user(pec_taker):
        return AssignmentResult(pec_taker, resolver.display_name(pec_taker), "pec")

    dominus = resolver.resolve_label(candidates.fascicolo_dominus)
    if dominus:
        return AssignmentResult(dominus, resolver.display_name(dominus), "dominus")

    # etichetta visibile anche quando non risolta: aiuta chi smista la coda
    label = (
        candidates.fascicolo_referente
        or candidates.agenda_avvocato
        or candidates.fascicolo_dominus
        or ""
    )
    return AssignmentResult("", str(label or "").strip(), "coda_studio")


def build_resolver_from_users(users: Iterable[Any]) -> LawyerResolver:
    """Costruisce il resolver da oggetti ``Utente`` di ``pct.auth``."""
    rows: list[dict[str, Any]] = []
    for user in users:
        rows.append(
            {
                "id": getattr(user, "id", "") or "",
                "username": getattr(user, "username", "") or "",
                "nome_completo": getattr(user, "nome_completo", "") or "",
            }
        )
    return LawyerResolver(users=rows)


__all__ = [
    "AssignmentCandidates",
    "AssignmentResult",
    "LawyerResolver",
    "build_resolver_from_users",
    "resolve_assignment",
]
