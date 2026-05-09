"""Gateway strutturato per l'accesso ai dati dello studio da parte di Lex.

Lex usa questo modulo come layer di accesso ai dati interni:
clienti, fascicoli, agenda, scadenziario, fatturazione.

Non sostituisce i gestori pct/* — li wrappa fornendo output
leggibili da Lex (dict strutturati, errori espliciti, nessuna eccezione raw).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from flask import current_app, g


# ---------------------------------------------------------------------------
# Helpers per tenant e accesso gestori
# ---------------------------------------------------------------------------

def _get_tenant_id() -> str:
    try:
        tenant = getattr(g, "tenant", None)
    except RuntimeError:
        tenant = None
    if tenant:
        return str(getattr(tenant, "id", "") or getattr(tenant, "slug", "") or "default")
    return "default"


def _get_clienti():
    from web.helpers import get_clienti
    return get_clienti()


def _get_fascicoli():
    from web.helpers import get_fascicoli
    return get_fascicoli()


def _get_agenda():
    from web.helpers import get_agenda
    return get_agenda()


def _get_scadenziario():
    from web.helpers import get_scadenziario
    return get_scadenziario()


def _get_fatturazione():
    from web.helpers import get_fatturazione
    return get_fatturazione()


# ---------------------------------------------------------------------------
# Dataclass risultati
# ---------------------------------------------------------------------------

@dataclass
class ClienteResult:
    id: str
    nome_completo: str
    tipo: str
    stato: str
    codice_fiscale: str
    partita_iva: str
    email: str
    pec: str
    telefono: str
    indirizzo: str
    avvocato_referente: str
    data_prima_acquisizione: str
    note: str
    tag: list[str] = field(default_factory=list)
    n_fascicoli: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome_completo": self.nome_completo,
            "tipo": self.tipo,
            "stato": self.stato,
            "codice_fiscale": self.codice_fiscale,
            "partita_iva": self.partita_iva,
            "email": self.email,
            "pec": self.pec,
            "telefono": self.telefono,
            "indirizzo": self.indirizzo,
            "avvocato_referente": self.avvocato_referente,
            "data_prima_acquisizione": self.data_prima_acquisizione,
            "note": self.note[:200] if self.note else "",
            "tag": self.tag,
            "n_fascicoli": self.n_fascicoli,
        }

    def to_text(self) -> str:
        parts = [f"Cliente: {self.nome_completo}"]
        if self.tipo:
            parts.append(f"Tipo: {self.tipo}")
        if self.stato:
            parts.append(f"Stato: {self.stato}")
        if self.codice_fiscale:
            parts.append(f"CF: {self.codice_fiscale}")
        if self.partita_iva:
            parts.append(f"P.IVA: {self.partita_iva}")
        if self.email:
            parts.append(f"Email: {self.email}")
        if self.pec:
            parts.append(f"PEC: {self.pec}")
        if self.telefono:
            parts.append(f"Tel: {self.telefono}")
        if self.indirizzo:
            parts.append(f"Indirizzo: {self.indirizzo}")
        if self.avvocato_referente:
            parts.append(f"Referente: {self.avvocato_referente}")
        if self.n_fascicoli:
            parts.append(f"Fascicoli: {self.n_fascicoli}")
        return ". ".join(parts) + "."


@dataclass
class StudioLookupResult:
    lookup_type: str
    query: str
    cleaned_query: str
    matches: list[ClienteResult] = field(default_factory=list)
    selected: ClienteResult | None = None
    status: str = "not_found"
    source: str = "Clienti"
    warnings: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.matches)

    def __len__(self) -> int:
        return len(self.matches)

    def __getitem__(self, index):
        return self.matches[index]

    def __bool__(self) -> bool:
        return bool(self.matches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lookup_type": self.lookup_type,
            "query": self.query,
            "cleaned_query": self.cleaned_query,
            "matches": [m.to_dict() for m in self.matches],
            "selected": self.selected.to_dict() if self.selected else None,
            "status": self.status,
            "source": self.source,
            "warnings": list(self.warnings),
            "debug": dict(self.debug),
        }


@dataclass
class FascicoloResult:
    id: str
    titolo: str
    numero_rg: str
    anno_rg: str
    stato: str
    tribunale: str
    sezione: str
    oggetto: str
    tipo: str
    valore_causa: float
    avvocato_referente: str
    data_apertura: str
    data_chiusura: str
    cliente_nome: str
    cliente_id: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titolo": self.titolo,
            "numero_rg": self.numero_rg,
            "anno_rg": self.anno_rg,
            "stato": self.stato,
            "tribunale": self.tribunale,
            "sezione": self.sezione,
            "oggetto": self.oggetto,
            "tipo": self.tipo,
            "valore_causa": self.valore_causa,
            "avvocato_referente": self.avvocato_referente,
            "data_apertura": self.data_apertura,
            "data_chiusura": self.data_chiusura,
            "cliente_nome": self.cliente_nome,
            "cliente_id": self.cliente_id,
            "note": self.note[:200] if self.note else "",
        }

    def to_text(self) -> str:
        rg = f"RG {self.numero_rg}/{self.anno_rg}" if self.numero_rg and self.anno_rg else self.numero_rg or "senza RG"
        parts = [f"Fascicolo: {self.titolo} ({rg})"]
        if self.stato:
            parts.append(f"Stato: {self.stato}")
        if self.tribunale:
            parts.append(f"Tribunale: {self.tribunale}")
        if self.oggetto:
            parts.append(f"Oggetto: {self.oggetto}")
        if self.cliente_nome:
            parts.append(f"Cliente: {self.cliente_nome}")
        if self.valore_causa:
            parts.append(f"Valore causa: €{self.valore_causa:,.2f}")
        return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Entity extraction dalla query
# ---------------------------------------------------------------------------

_CF_RE = re.compile(r"\b([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z]{1}[0-9LMNPQRSTUV]{2}[A-Z]{1}[0-9LMNPQRSTUV]{3}[A-Z]{1})\b", re.IGNORECASE)
_PIVA_RE = re.compile(r"\b(IT)?(\d{11})\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")


def extract_entity_hint(query: str) -> dict[str, str]:
    """Estrae CF, PIVA, email dalla query per ricerca mirata."""
    text = query or ""
    cf = _CF_RE.search(text)
    piva = _PIVA_RE.search(text)
    email = _EMAIL_RE.search(text)
    return {
        "codice_fiscale": cf.group(0).upper() if cf else "",
        "partita_iva": piva.group(2) if piva else "",
        "email": email.group(0).lower() if email else "",
    }


_CLIENTE_QUERY_PREFIXES = (
    r"^\s*(?:dati|scheda|recapiti|contatti|pec|email|telefono|indirizzo|codice\s+fiscale|cf|partita\s+iva|p\.?\s*iva)\s+(?:del|della|di|dell[o']|per\s+il)?\s*cliente\s+",
    r"^\s*(?:trova|cerca|mostra|apri)\s+(?:il\s+)?cliente\s+",
    r"^\s*cliente\s+",
    r"^\s*che\s+fascicoli\s+ha\s+",
    r"^\s*(?:dati|scheda|recapiti|contatti)\s+(?:di|del|della|dell[o'])\s+",
)


def clean_cliente_query(query: str) -> str:
    text = " ".join(str(query or "").replace("?", " ").split()).strip()
    cleaned = text
    for pattern in _CLIENTE_QUERY_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\b(?:per favore|grazie)\b", "", cleaned, flags=re.IGNORECASE).strip()
    return " ".join(cleaned.split()) or text


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _score_cliente(row: Any, cleaned_query: str, hints: dict[str, str], gestore_matches: set[str]) -> int:
    rec = getattr(row, "recapiti", None)
    nome = _norm(getattr(row, "nome_completo", ""))
    cf = _norm(getattr(row, "codice_fiscale", ""))
    piva = _norm(getattr(row, "partita_iva", ""))
    email = _norm(getattr(rec, "email", ""))
    pec = _norm(getattr(rec, "pec", ""))
    haystack = " ".join([nome, cf, piva, email, pec])
    query = _norm(cleaned_query)
    if not query:
        return 0
    if hints.get("codice_fiscale") and cf == _norm(hints["codice_fiscale"]):
        return 120
    if hints.get("partita_iva") and piva == _norm(hints["partita_iva"]):
        return 120
    if hints.get("email") and (_norm(hints["email"]) == email or _norm(hints["email"]) == pec):
        return 120
    score = 0
    query_tokens = [token for token in re.split(r"[^a-z0-9àèéìòù]+", query) if len(token) > 1]
    name_tokens = [token for token in re.split(r"[^a-z0-9àèéìòù]+", nome) if token]
    if query == nome:
        score = max(score, 110)
    if query_tokens and set(query_tokens) == set(name_tokens):
        score = max(score, 104)
    if query_tokens and all(token in nome for token in query_tokens):
        score = max(score, 92)
    if query_tokens and all(token in haystack for token in query_tokens):
        score = max(score, 80)
    if query and query in haystack:
        score = max(score, 76)
    if str(getattr(row, "id", "")) in gestore_matches:
        score += 20
    return score


# ---------------------------------------------------------------------------
# Tool: find_cliente
# ---------------------------------------------------------------------------

def find_cliente(query: str, tenant_id: str | None = None, *, limit: int = 20) -> StudioLookupResult:
    """Cerca clienti per nome, CF, PIVA, email o testo libero.

    Ritorna un risultato strutturato e list-like, ordinato per pertinenza.
    """
    cleaned_query = clean_cliente_query(query)
    try:
        gestore = _get_clienti()
        hints = extract_entity_hint(cleaned_query)
        all_rows = list(gestore.tutti())
        gestore_matches = {
            str(getattr(row, "id", ""))
            for row in (gestore.cerca(cleaned_query) if cleaned_query.strip() else [])
        }
        ranked: list[tuple[int, Any]] = []
        for row in all_rows:
            score = _score_cliente(row, cleaned_query, hints, gestore_matches)
            if score > 0:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], _norm(getattr(item[1], "nome_completo", ""))))
        matches = [_cliente_to_result(row, gestore) for score, row in ranked[:limit]]
        status = "not_found"
        selected = None
        if matches:
            top_score = ranked[0][0]
            second_score = ranked[1][0] if len(ranked) > 1 else 0
            if top_score >= 100 or top_score - second_score >= 18:
                status = "found"
                selected = matches[0]
            else:
                status = "multiple_matches"
        return StudioLookupResult(
            lookup_type="cliente",
            query=str(query or ""),
            cleaned_query=cleaned_query,
            matches=matches,
            selected=selected,
            status=status,
            source="Clienti",
            debug={
                "tenant_id": tenant_id or _get_tenant_id(),
                "candidate_count": len(all_rows),
                "ranked_count": len(ranked),
                "top_score": ranked[0][0] if ranked else 0,
            },
        )
    except Exception as exc:
        _log_error("find_cliente", exc)
        return StudioLookupResult(
            lookup_type="cliente",
            query=str(query or ""),
            cleaned_query=cleaned_query,
            status="error",
            source="Clienti",
            warnings=[str(exc)],
            debug={"tenant_id": tenant_id or "default"},
        )


# ---------------------------------------------------------------------------
# Tool: get_cliente_details
# ---------------------------------------------------------------------------

def get_cliente_details(cliente_id: str, tenant_id: str | None = None) -> dict[str, Any]:
    """Ritorna i dettagli completi di un cliente per ID."""
    try:
        gestore = _get_clienti()
        row = gestore.ottieni(cliente_id)
        if row is None:
            return {}
        return _cliente_to_result(row, gestore).to_dict()
    except Exception as exc:
        _log_error("get_cliente_details", exc)
        return {}


# ---------------------------------------------------------------------------
# Tool: get_cliente_contacts
# ---------------------------------------------------------------------------

def get_cliente_contacts(cliente_id: str, tenant_id: str | None = None) -> dict[str, str]:
    """Ritorna solo i recapiti di un cliente (email, PEC, telefono, indirizzo)."""
    try:
        gestore = _get_clienti()
        row = gestore.ottieni(cliente_id)
        if row is None:
            return {}
        rec = getattr(row, "recapiti", None)
        ind_res = getattr(row, "indirizzo_residenza", None)
        ind_sede = getattr(row, "indirizzo_sede_legale", None)
        indirizzo = _format_indirizzo(ind_sede or ind_res)
        return {
            "email": getattr(rec, "email", "") or "",
            "pec": getattr(rec, "pec", "") or "",
            "telefono": getattr(rec, "telefono", "") or "",
            "indirizzo": indirizzo,
        }
    except Exception as exc:
        _log_error("get_cliente_contacts", exc)
        return {}


# ---------------------------------------------------------------------------
# Tool: find_fascicoli_by_cliente
# ---------------------------------------------------------------------------

def find_fascicoli_by_cliente(cliente_id: str, tenant_id: str | None = None, *, limit: int = 10) -> list[FascicoloResult]:
    """Ritorna i fascicoli collegati a un cliente."""
    try:
        gestore = _get_fascicoli()
        rows = [f for f in gestore.tutti() if getattr(f, "id_cliente", "") == cliente_id]
        return [_fascicolo_to_result(r) for r in rows[:limit]]
    except Exception as exc:
        _log_error("find_fascicoli_by_cliente", exc)
        return []


# ---------------------------------------------------------------------------
# Tool: find_fascicolo
# ---------------------------------------------------------------------------

def find_fascicolo(query: str, *, limit: int = 8) -> list[FascicoloResult]:
    """Cerca fascicoli per titolo, RG, oggetto o testo libero."""
    try:
        gestore = _get_fascicoli()
        matches = gestore.cerca(query) if query.strip() else gestore.tutti()
        return [_fascicolo_to_result(r) for r in matches[:limit]]
    except Exception as exc:
        _log_error("find_fascicolo", exc)
        return []


# ---------------------------------------------------------------------------
# Tool: get_fascicolo_details
# ---------------------------------------------------------------------------

def get_fascicolo_details(fascicolo_id: str) -> FascicoloResult | None:
    """Ritorna i dettagli completi di un fascicolo per ID."""
    try:
        gestore = _get_fascicoli()
        row = gestore.ottieni(fascicolo_id)
        if row is None:
            return None
        return _fascicolo_to_result(row)
    except Exception as exc:
        _log_error("get_fascicolo_details", exc)
        return None


# ---------------------------------------------------------------------------
# Tool: get_cliente_timeline
# ---------------------------------------------------------------------------

def get_cliente_timeline(cliente_id: str, *, limit: int = 10) -> list[dict[str, str]]:
    """Ritorna la timeline eventi recenti per un cliente (agenda + scadenze)."""
    events: list[dict[str, str]] = []
    try:
        agenda = _get_agenda()
        for row in agenda.tutti():
            if getattr(row, "id_cliente", "") == cliente_id or getattr(row, "cliente", "") == cliente_id:
                events.append({
                    "tipo": "appuntamento",
                    "data": str(getattr(row, "data_ora", "") or ""),
                    "descrizione": str(getattr(row, "titolo", "") or ""),
                    "note": str(getattr(row, "note", "") or ""),
                })
    except Exception as exc:
        _log_error("get_cliente_timeline/agenda", exc)

    try:
        scadenziario = _get_scadenziario()
        for row in scadenziario.tutti():
            if getattr(row, "id_cliente", "") == cliente_id:
                events.append({
                    "tipo": "scadenza",
                    "data": str(getattr(row, "data_scadenza", "") or ""),
                    "descrizione": str(getattr(row, "descrizione", "") or ""),
                    "note": str(getattr(row, "note", "") or ""),
                })
    except Exception as exc:
        _log_error("get_cliente_timeline/scadenziario", exc)

    events.sort(key=lambda e: e.get("data", ""), reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# Tool: get_cliente_economic_summary
# ---------------------------------------------------------------------------

def get_cliente_economic_summary(cliente_id: str, tenant_id: str | None = None) -> dict[str, Any]:
    """Ritorna un sommario economico del cliente (parcelle, fatture, pagamenti)."""
    try:
        fatturazione = _get_fatturazione()
        rows = [f for f in fatturazione.tutti() if getattr(f, "id_cliente", "") == cliente_id]
        totale_fatturato = sum(float(getattr(r, "importo_totale", 0) or 0) for r in rows)
        n_fatture = len(rows)
        da_pagare = sum(
            float(getattr(r, "importo_totale", 0) or 0)
            for r in rows
            if str(getattr(getattr(r, "stato", None), "value", "") or "").lower() in ("emessa", "inviata", "scaduta")
        )
        return {
            "n_fatture": n_fatture,
            "totale_fatturato": round(totale_fatturato, 2),
            "da_pagare": round(da_pagare, 2),
        }
    except Exception as exc:
        _log_error("get_cliente_economic_summary", exc)
        return {"n_fatture": 0, "totale_fatturato": 0.0, "da_pagare": 0.0}


# ---------------------------------------------------------------------------
# Tool: get_cliente_documents
# ---------------------------------------------------------------------------

def get_cliente_documents(cliente_id: str, *, limit: int = 10) -> list[dict[str, str]]:
    """Ritorna i documenti collegati al cliente (da fascicoli)."""
    docs: list[dict[str, str]] = []
    try:
        gestore = _get_fascicoli()
        fascicoli = [f for f in gestore.tutti() if getattr(f, "id_cliente", "") == cliente_id]
        for fascicolo in fascicoli:
            for doc in list(getattr(fascicolo, "documenti", []) or [])[:3]:
                docs.append({
                    "fascicolo": str(getattr(fascicolo, "titolo", "") or ""),
                    "nome": str(getattr(doc, "nome", "") or ""),
                    "tipo": str(getattr(doc, "tipo", "") or ""),
                    "data": str(getattr(doc, "data_caricamento", "") or ""),
                })
                if len(docs) >= limit:
                    return docs
    except Exception as exc:
        _log_error("get_cliente_documents", exc)
    return docs


def _field_or_missing(value: str, label: str, missing: list[str]) -> str:
    clean = str(value or "").strip()
    if clean:
        return clean
    missing.append(label)
    return "non disponibile"


def build_cliente_answer(result: StudioLookupResult) -> str:
    """Costruisce una risposta utente professionale per il lookup cliente."""
    cleaned = result.cleaned_query or result.query
    if result.status == "error":
        return (
            "Non riesco a completare la ricerca nell'anagrafica interna dello studio.\n\n"
            "Ho cercato in:\n"
            "- Clienti\n"
            "- eventuali soggetti/anagrafiche collegate\n\n"
            "Prossima azione:\n"
            "verifica il gestionale clienti e riprova la ricerca."
        )
    if result.status == "not_found" or not result.matches:
        return (
            f"Non ho trovato un cliente corrispondente a '{cleaned}' nell'anagrafica dello studio.\n\n"
            "Ho cercato in:\n"
            "- Clienti\n"
            "- eventuali soggetti/anagrafiche collegate\n\n"
            "Prossima azione:\n"
            "verifica se il nominativo e' scritto diversamente oppure crea/aggiorna l'anagrafica cliente."
        )
    if result.status == "multiple_matches" or result.selected is None:
        lines = [
            "Ho trovato piu' clienti compatibili con la ricerca.",
            "",
            "Clienti da distinguere:",
        ]
        for item in result.matches[:8]:
            details = []
            if item.codice_fiscale:
                details.append(f"CF {item.codice_fiscale}")
            if item.email:
                details.append(item.email)
            suffix = f" ({', '.join(details)})" if details else ""
            lines.append(f"- {item.nome_completo}{suffix}")
        lines.extend([
            "",
            "Prossima azione:",
            "indica un dato ulteriore, ad esempio codice fiscale, PEC, email o fascicolo collegato.",
        ])
        return "\n".join(lines)

    cliente = result.selected
    missing: list[str] = []
    cf_piva = cliente.codice_fiscale or cliente.partita_iva
    fascicoli = find_fascicoli_by_cliente(cliente.id, limit=20)
    lines = [
        f"Ho trovato il cliente {cliente.nome_completo}.",
        "",
        "Dati anagrafici:",
        f"- Nome: {cliente.nome_completo}",
        f"- Tipo: {_field_or_missing(cliente.tipo, 'tipo', missing)}",
        f"- Codice fiscale/P.IVA: {_field_or_missing(cf_piva, 'codice fiscale/P.IVA', missing)}",
        f"- Indirizzo: {_field_or_missing(cliente.indirizzo, 'indirizzo', missing)}",
        "",
        "Recapiti:",
        f"- Email: {_field_or_missing(cliente.email, 'email', missing)}",
        f"- PEC: {_field_or_missing(cliente.pec, 'PEC', missing)}",
        f"- Telefono: {_field_or_missing(cliente.telefono, 'telefono', missing)}",
        "",
        "Fascicoli collegati:",
    ]
    if fascicoli:
        for fascicolo in fascicoli:
            rg = f"RG {fascicolo.numero_rg}/{fascicolo.anno_rg}" if fascicolo.numero_rg and fascicolo.anno_rg else "senza RG"
            title = fascicolo.titolo or fascicolo.oggetto or fascicolo.id
            lines.append(f"- {title} ({rg})")
    else:
        missing.append("fascicoli collegati")
        lines.append("- nessun fascicolo collegato disponibile")
    lines.extend([
        "",
        "Dati mancanti:",
    ])
    if missing:
        for item in list(dict.fromkeys(missing)):
            lines.append(f"- {item}")
    else:
        lines.append("- nessuno tra i campi principali")
    lines.extend([
        "",
        "Prossima azione:",
        "Puoi aprire la scheda cliente oppure aggiornare i dati mancanti.",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers privati
# ---------------------------------------------------------------------------

def _cliente_to_result(row: Any, gestore: Any) -> ClienteResult:
    rec = getattr(row, "recapiti", None)
    email = getattr(rec, "email", "") or ""
    pec = getattr(rec, "pec", "") or ""
    telefono = getattr(rec, "telefono", "") or ""
    ind_sede = getattr(row, "indirizzo_sede_legale", None)
    ind_res = getattr(row, "indirizzo_residenza", None)
    indirizzo = _format_indirizzo(ind_sede or ind_res)

    # Conta fascicoli collegati
    n_fascicoli = 0
    try:
        gestore_fasc = _get_fascicoli()
        n_fascicoli = sum(1 for f in gestore_fasc.tutti() if getattr(f, "id_cliente", "") == row.id)
    except Exception:
        pass

    return ClienteResult(
        id=str(row.id),
        nome_completo=str(row.nome_completo),
        tipo=str(getattr(getattr(row, "tipo", None), "value", "") or ""),
        stato=str(getattr(getattr(row, "stato", None), "value", "") or ""),
        codice_fiscale=str(getattr(row, "codice_fiscale", "") or ""),
        partita_iva=str(getattr(row, "partita_iva", "") or ""),
        email=email,
        pec=pec,
        telefono=telefono,
        indirizzo=indirizzo,
        avvocato_referente=str(getattr(row, "avvocato_referente", "") or ""),
        data_prima_acquisizione=str(getattr(row, "data_prima_acquisizione", "") or ""),
        note=str(getattr(row, "note", "") or ""),
        tag=list(getattr(row, "tag", []) or []),
        n_fascicoli=n_fascicoli,
    )


def _fascicolo_to_result(row: Any) -> FascicoloResult:
    return FascicoloResult(
        id=str(row.id),
        titolo=str(getattr(row, "titolo", "") or ""),
        numero_rg=str(getattr(row, "numero_rg", "") or ""),
        anno_rg=str(getattr(row, "anno_rg", "") or ""),
        stato=str(getattr(getattr(row, "stato", None), "value", "") or ""),
        tribunale=str(getattr(row, "tribunale", "") or ""),
        sezione=str(getattr(row, "sezione", "") or ""),
        oggetto=str(getattr(row, "oggetto", "") or ""),
        tipo=str(getattr(getattr(row, "tipo", None), "value", "") or ""),
        valore_causa=float(getattr(row, "valore_causa", 0) or 0),
        avvocato_referente=str(getattr(row, "avvocato_referente", "") or ""),
        data_apertura=str(getattr(row, "data_apertura", "") or ""),
        data_chiusura=str(getattr(row, "data_chiusura", "") or ""),
        cliente_nome=str(getattr(row, "nome_cliente", "") or getattr(row, "cliente", "") or ""),
        cliente_id=str(getattr(row, "id_cliente", "") or ""),
        note=str(getattr(row, "note", "") or ""),
    )


def _format_indirizzo(ind: Any) -> str:
    if ind is None:
        return ""
    via = str(getattr(ind, "via", "") or "")
    civico = str(getattr(ind, "civico", "") or "")
    cap = str(getattr(ind, "cap", "") or "")
    comune = str(getattr(ind, "comune", "") or "")
    provincia = str(getattr(ind, "provincia", "") or "")
    parts = [f"{via} {civico}".strip(), f"{cap} {comune}".strip(), provincia]
    return ", ".join(p for p in parts if p)


def _log_error(fn: str, exc: Exception) -> None:
    try:
        current_app.logger.warning("studio_data_gateway.%s: %s", fn, exc)
    except RuntimeError:
        pass
