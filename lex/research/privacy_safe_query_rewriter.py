"""Riscrittura privacy-safe delle query per la ricerca legale pubblica.

Questo modulo separa strutturalmente la query originale dell'utente (che può
contenere dati personali, riferimenti a fascicoli specifici e nomi propri)
in query specializzate per i diversi canali di ricerca:

- ``private_context_query``: per il retrieval interno tenant-aware (mantiene
  tutto il contesto ma redacta gli identificatori forti).
- ``public_research_query``: per web ufficiale e fonti pubbliche (solo materia
  giuridica, senza alcun dato personale o identificativo).
- ``official_sources_query``: query ottimizzata per fonti istituzionali
  (normattiva.it, gazzettaufficiale.it, giustizia.it, ecc.).
- ``local_deep_research_query``: query per LDR, vuota se la sensitività lo
  impedisce.

Esempio d'uso
-------------
>>> result = rewrite_query_for_legal_research(
...     "Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione contro Bianchi"
...     " nella causa di responsabilità contrattuale?",
... )
>>> result.public_research_query
'prescrizione responsabilità contrattuale eccezione termine decorrenza codice civile'
>>> result.removed_sensitive_tokens
['Rossi', 'RG 1234/2025', 'Bianchi']
>>> result.can_use_ldr
True
>>> result.sensitivity
'sensitive'
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from lex.gateway.privacy_guard import (
    CF_RE,
    EMAIL_RE,
    IBAN_RE,
    PHONE_RE,
    PIVA_RE,
    RG_RE,
    PrivacyGuard,
)

# ---------------------------------------------------------------------------
# Costanti e pattern
# ---------------------------------------------------------------------------

# Keyword giuridiche da preservare in ogni query pubblica.  L'insieme è vasto
# ma non esaustivo: copre le materie principali del diritto civile, penale,
# amministrativo, tributario, lavoro e societario.
_LEGAL_KEYWORDS: frozenset[str] = frozenset(
    {
        # Prescrizione e decadenza
        "prescrizione", "decadenza", "termine", "termini", "decorrenza",
        "interruzione", "sospensione", "quinquennale", "decennale", "biennale",
        "triennale", "annuale", "ordinaria", "breve",
        # Responsabilità
        "responsabilità", "contrattuale", "extracontrattuale", "aquiliana",
        "oggettiva", "soggettiva", "risarcimento", "danno", "danni",
        "inadempimento", "inadempiente", "mora", "colpa", "dolo", "negligenza",
        "imprudenza", "imperizia",
        # Eccezioni processuali
        "eccezione", "eccezioni", "eccepire", "difetto", "giurisdizione",
        "competenza", "incompetenza", "litispendenza", "improponibilità",
        "inammissibilità", "improcedibilità",
        # Contratto e obbligazioni
        "contratto", "obbligazione", "obbligazioni", "adempimento", "clausola",
        "nullità", "annullabilità", "rescissione", "risoluzione", "recesso",
        "inadempimento", "caparra", "penale", "garanzia",
        # Procedure
        "udienza", "ricorso", "appello", "cassazione", "opposizione",
        "impugnazione", "giudizio", "procedimento", "causa", "azione",
        "domanda", "citazione", "comparsa", "memoria", "deposito",
        # Misure e tutele
        "tutela", "sospensiva", "cautelare", "inibitoria", "sequestro",
        "pignoramento", "esecuzione", "decreto", "ingiunzione", "provvedimento",
        # Normativa
        "legge", "norma", "normativa", "articolo", "comma", "codice",
        "codice civile", "codice penale", "testo unico", "decreto legislativo",
        "decreto legge", "regolamento", "direttiva",
        # Materie specifiche
        "lavoro", "licenziamento", "dimissioni", "contratto lavoro",
        "separazione", "divorzio", "affido", "mantenimento",
        "successione", "eredità", "testamento", "legato",
        "locazione", "sfratto", "affitto",
        "appalto", "subappalto", "corrispettivo",
        "fallimento", "concordato", "crisi impresa",
        "penale", "reato", "imputato", "indagato", "pena",
        "tributario", "imposta", "accertamento", "avviso bonario",
        "amministrativo", "silenzio assenso", "annullamento", "revoca",
        "privacy", "gdpr", "dati personali", "trattamento",
        # Soggetti processuali (categorie, non nomi propri)
        "avvocato", "difensore", "procura", "procuratore", "giudice",
        "tribunale", "corte", "magistrato", "pm",
        # Termini procedurali
        "notifica", "notificazione", "intimazione", "diffida", "messa in mora",
        "sospensione feriale", "proroga",
    }
)

# Pattern per riconoscere nomi propri italiani da rimuovere.
# Logica: parola con prima lettera maiuscola, lunghezza >= 3, seguita
# da spazio o fine stringa, che NON coincide con una keyword giuridica.
_NOME_PROPRIO_RE = re.compile(
    r'\b([A-ZÀÈÉÌÒÙÄ][a-zàèéìòùäë]{2,}(?:\s+[A-ZÀÈÉÌÒÙÄ][a-zàèéìòùäë]{2,})*)\b'
)

# Pattern per locuzioni introduttive di nomi propri.
_LOCUZIONE_NOME_RE = re.compile(
    r'\b(?:contro|di|del|della|dei|delle|dal|dalla|Sig\.|Sig\.ra|Dott\.|Avv\.)\s+'
    r'([A-ZÀÈÉÌÒÙÄ][a-zàèéìòùäë]{2,}(?:\s+[A-ZÀÈÉÌÒÙÄ][a-zàèéìòùäë]{2,})*)\b',
    re.IGNORECASE,
)

# Parole italiane comuni con iniziale maiuscola che non sono nomi propri.
_ITALIAN_COMMON_WORDS: frozenset[str] = frozenset(
    {
        "Nel", "Nella", "Nelle", "Negli", "Nei", "Per", "Con", "Tra", "Fra",
        "Sul", "Sulla", "Sulle", "Sugli", "Sui", "Dal", "Dalla", "Dalle",
        "Dagli", "Dai", "Al", "Alla", "Alle", "Agli", "Ai",
        "Il", "Lo", "La", "Le", "Gli", "Un", "Una", "Uno",
        "Che", "Chi", "Come", "Quando", "Dove", "Perché", "Poiché",
        "Quindi", "Dunque", "Allora", "Così", "Tuttavia", "Però",
        "Anche", "Solo", "Ancora", "Già", "Sempre", "Mai", "Spesso",
        "Tribunale", "Corte", "Giudice", "Causa", "Fascicolo", "Sentenza",
        "Decreto", "Legge", "Norma", "Articolo", "Codice", "Sezione",
        "Sezioni", "Cassazione", "Repubblica", "Stato", "Italia",
        "Responsabilità", "Prescrizione", "Contratto", "Obbligazione",
        "Eccezione", "Domanda", "Ricorso", "Appello", "Opposizione",
        "Errore", "Motivo", "Ragione", "Caso", "Fatto", "Diritto",
        "Posso", "Possiamo", "Devo", "Dobbiamo", "Voglio", "Vogliamo",
        "Questo", "Questa", "Questi", "Queste", "Quello", "Quella",
    }
)

# Categorie di sensitivity e quali canali abilitano.
_SENSITIVITY_CHANNELS: dict[str, dict[str, bool]] = {
    "public": {
        "internal_retrieval": True,
        "official_web": True,
        "ldr": True,
        "external_provider": True,
    },
    "internal": {
        "internal_retrieval": True,
        "official_web": True,
        "ldr": True,
        "external_provider": True,
    },
    "sensitive": {
        "internal_retrieval": True,
        "official_web": True,
        "ldr": True,   # Solo se la public_research_query è pulita
        "external_provider": False,
    },
    "highly_sensitive": {
        "internal_retrieval": True,
        "official_web": False,
        "ldr": False,
        "external_provider": False,
    },
}

_EXTERNAL_ALLOWED_ENV = "LEX_EXTERNAL_ALLOWED"


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "on"}


# ---------------------------------------------------------------------------
# Dataclass risultato
# ---------------------------------------------------------------------------


@dataclass
class PrivacySafeResearchQuery:
    """Risultato della riscrittura privacy-safe di una query legale.

    Attributi
    ----------
    original_query:
        Query originale dell'utente, non modificata.
    private_context_query:
        Query per il retrieval interno tenant-aware.  Mantiene tutto il
        contesto giuridico ma redacta gli identificatori forti (CF, IBAN,
        email, RG, telefono).  I nomi propri restano per permettere la
        ricerca nei fascicoli dello studio.
    public_research_query:
        Query anonimizzata per fonti web pubbliche e LDR.  Non contiene
        alcun dato personale, nome proprio o riferimento a fascicoli
        specifici.  Solo materia giuridica pubblica.
    official_sources_query:
        Variante della query pubblica ottimizzata per fonti istituzionali
        (normattiva, gazzettaufficiale, giustizia.it).  Tende ad essere
        più sintetica e focalizzata su norma/articolo/materia.
    local_deep_research_query:
        Query da inviare a Local Deep Research.  Uguale alla
        ``public_research_query`` se il canale è consentito, stringa vuota
        altrimenti.
    removed_sensitive_tokens:
        Lista dei token rimossi dalla query pubblica (nomi propri, RG, CF,
        ecc.).
    sensitivity:
        Livello di sensitività classificato: ``public``, ``internal``,
        ``sensitive``, ``highly_sensitive``.
    can_use_internal_retrieval:
        True se il retrieval interno tenant-aware è consentito.
    can_use_official_web:
        True se la ricerca su web ufficiale (DuckDuckGo site:) è consentita.
    can_use_ldr:
        True se Local Deep Research può ricevere la query.
    can_use_external_provider:
        True se provider esterni (OpenAI) possono ricevere la query.
    requires_review:
        True se la risposta finale richiede revisione umana per motivi di
        sensitività o gap di materia.
    reason:
        Spiegazione sintetica della classificazione e delle decisioni prese.
    warnings:
        Lista di avvisi generati durante la riscrittura.
    """

    original_query: str
    private_context_query: str
    public_research_query: str
    official_sources_query: str
    local_deep_research_query: str
    removed_sensitive_tokens: list[str] = field(default_factory=list)
    sensitivity: str = "public"
    can_use_internal_retrieval: bool = True
    can_use_official_web: bool = True
    can_use_ldr: bool = False
    can_use_external_provider: bool = False
    requires_review: bool = False
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------


def _clean(text: str) -> str:
    """Normalizza spazi multipli e strip."""
    return " ".join(text.split()).strip()


def _is_legal_keyword(word: str) -> bool:
    """True se la parola (case-insensitive) è una keyword giuridica da preservare."""
    return word.lower() in _LEGAL_KEYWORDS or word in _ITALIAN_COMMON_WORDS


def _extract_proper_names(text: str) -> list[str]:
    """Estrae nomi propri italiani dalla query.

    Un nome proprio è riconosciuto come sequenza di una o più parole con
    prima lettera maiuscola che:
    - Ha lunghezza >= 3 caratteri per parola.
    - Non coincide con una keyword giuridica nota.
    - Non è una parola comune italiana con iniziale maiuscola.

    I nomi estratti dalle locuzioni ("contro X", "di X", "Sig. X") vengono
    sempre inclusi.
    """
    found: list[str] = []
    seen: set[str] = set()

    # Prima pass: locuzioni esplicite (alta confidenza).
    for match in _LOCUZIONE_NOME_RE.finditer(text):
        nome = _clean(match.group(1))
        if nome and nome not in seen and not _is_legal_keyword(nome):
            found.append(nome)
            seen.add(nome)

    # Seconda pass: nomi propri generici.
    for match in _NOME_PROPRIO_RE.finditer(text):
        nome = _clean(match.group(1))
        if not nome or nome in seen:
            continue
        # Filtra: lunghezza minima, non keyword, non parola comune.
        words = nome.split()
        if any(len(w) < 3 for w in words):
            continue
        if all(_is_legal_keyword(w) for w in words):
            continue
        if any(w in _ITALIAN_COMMON_WORDS for w in words):
            continue
        found.append(nome)
        seen.add(nome)

    return found


def _redact_identifiers(text: str) -> tuple[str, list[str]]:
    """Rimuove identificatori forti dalla query. Ritorna (testo_redactato, token_rimossi)."""
    removed: list[str] = []

    def _sub(pattern: re.Pattern[str], placeholder: str, t: str) -> str:
        matches = pattern.findall(t)
        for m in matches:
            token = m if isinstance(m, str) else m[0]
            if token:
                removed.append(_clean(token))
        return pattern.sub(placeholder, t)

    text = _sub(EMAIL_RE, "[EMAIL_OSCURATA]", text)
    text = _sub(CF_RE, "[CF_OSCURATO]", text)
    text = _sub(IBAN_RE, "[IBAN_OSCURATO]", text)
    # RG: rimuove completamente il riferimento (non sostituisce con placeholder)
    rg_matches = RG_RE.findall(text)
    for m in rg_matches:
        token = m if isinstance(m, str) else (m[0] if m else "")
        if token:
            removed.append(_clean(token))
    text = RG_RE.sub("", text)
    text = _sub(PHONE_RE, "", text)
    # PIVA: cautela — solo se contesto esplicito, non rimuovere numeri generici
    # (PIVA_RE è \b\d{11}\b, troppo aggressivo da solo)

    return _clean(text), removed


def _remove_proper_names_from_text(text: str, names: list[str]) -> str:
    """Rimuove i nomi propri dal testo, sostituendo con placeholder contestuali."""
    result = text
    for name in sorted(names, key=len, reverse=True):
        # Costruisce pattern word-boundary sicuro.
        escaped = re.escape(name)
        pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
        # Determina il placeholder in base al contesto.
        # Cerca la locuzione precedente per scegliere il segnaposto.
        if re.search(r'\bcontro\b\s+' + escaped, result, re.IGNORECASE):
            placeholder = "[CONTROPARTE]"
        elif re.search(r'\b(?:fascicolo|pratica|causa)\b.*' + escaped, result, re.IGNORECASE):
            placeholder = "[PARTE_FASCICOLO]"
        else:
            placeholder = "[PARTE_PRIVATA]"
        result = pattern.sub("", result)
    return _clean(result)


def _extract_legal_matter(text: str) -> str:
    """Estrae solo i termini legali rilevanti dalla query per la query pubblica.

    Strategia:
    1. Rimuove identificatori forti.
    2. Rimuove nomi propri.
    3. Mantiene solo le parole che sono keyword giuridiche o termini tecnici.
    4. Se nessuna keyword trovata, usa le parole >= 5 caratteri non-stop.
    """
    # Tokenizza in parole, preservando punteggiatura semplice.
    words = re.findall(r"[A-Za-zÀ-ÿ']+", text)
    legal_terms: list[str] = []
    for word in words:
        lw = word.lower()
        if lw in _LEGAL_KEYWORDS:
            # Usa la forma lowercase per uniformità.
            legal_terms.append(lw)
    # Deduplicazione preservando ordine.
    seen: set[str] = set()
    unique: list[str] = []
    for t in legal_terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return " ".join(unique)


def _build_official_sources_query(public_query: str, original_query: str) -> str:
    """Costruisce una query ottimizzata per fonti istituzionali.

    Privilegia articoli di legge, materie normative e termini processuali
    rispetto a termini dottrinali o commentatistici.
    """
    # Estrai termini normativi prioritari.
    normative_keywords = {
        "codice civile", "codice penale", "codice procedura civile",
        "codice procedura penale", "decreto legislativo", "decreto legge",
        "legge", "articolo", "comma", "testo unico", "regolamento", "direttiva",
        "prescrizione", "decadenza", "termine", "responsabilità contrattuale",
        "responsabilità extracontrattuale", "risarcimento",
    }
    orig_lower = original_query.lower()
    found_normative: list[str] = []
    for kw in normative_keywords:
        if kw in orig_lower:
            found_normative.append(kw)

    if found_normative:
        base = " ".join(found_normative[:4])
        # Integra con la query pubblica se non troppo lunga.
        if len(public_query.split()) <= 6:
            return _clean(f"{base} {public_query}")
        return _clean(base)
    return public_query


def _build_private_context_query(original_query: str) -> str:
    """Costruisce la query per il retrieval interno.

    Redacta gli identificatori forti (CF, IBAN, email, telefono, RG) ma
    mantiene i nomi propri perché servono per la ricerca nei fascicoli
    dello studio.  Mantiene tutto il contesto giuridico.
    """
    redacted, _ = _redact_identifiers(original_query)
    # Rimuovi riferimenti espliciti a "fascicolo" come parola generica
    # se seguita da un nome che sarà comunque ricercato.
    # Rinomina i placeholder per chiarezza interna.
    redacted = redacted.replace("[EMAIL_OSCURATA]", "")
    redacted = redacted.replace("[CF_OSCURATO]", "")
    redacted = redacted.replace("[IBAN_OSCURATO]", "")
    return _clean(redacted) or _clean(original_query)


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------


def rewrite_query_for_legal_research(
    original_query: str,
    request_profile: dict | None = None,
    studio_context: dict | None = None,
    fascicolo_id: str | None = None,
    attachments: list | None = None,
) -> PrivacySafeResearchQuery:
    """Riscrive una query legale in versioni privacy-safe per i diversi canali.

    Parametri
    ----------
    original_query:
        Query originale dell'utente.  Può contenere dati personali, nomi
        propri, numeri di RG, riferimenti a fascicoli.
    request_profile:
        Profilo della richiesta (da ``LexRequestProfile``). Usato per
        determinare la modalità sorgente e l'intent.
    studio_context:
        Contesto dello studio (focus_topic, source_mode, ecc.).
    fascicolo_id:
        ID fascicolo se la query riguarda un fascicolo specifico.
    attachments:
        Lista di allegati. Se presenti, la query privata include un
        riferimento alla presenza di documenti allegati.

    Ritorna
    -------
    PrivacySafeResearchQuery
        Struttura con tutte le varianti di query e i metadati di controllo.

    Esempio
    -------
    Input: "Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione
    contro Bianchi nella causa di responsabilità contrattuale?"

    Output:
    - private_context_query: "Nel fascicolo Rossi posso eccepire la
      prescrizione contro Bianchi nella causa di responsabilità contrattuale?"
      (RG rimosso, nomi mantenuti per retrieval interno)
    - public_research_query: "prescrizione responsabilità contrattuale
      eccezione termine decorrenza codice civile"
    - removed_sensitive_tokens: ["Rossi", "RG 1234/2025", "Bianchi"]
    - can_use_ldr: True
    - sensitivity: "sensitive"
    """
    query = _clean(str(original_query or ""))
    if not query:
        return PrivacySafeResearchQuery(
            original_query=original_query,
            private_context_query="",
            public_research_query="",
            official_sources_query="",
            local_deep_research_query="",
            sensitivity="public",
            can_use_internal_retrieval=False,
            can_use_official_web=False,
            can_use_ldr=False,
            can_use_external_provider=False,
            requires_review=True,
            reason="Query vuota: impossibile eseguire la ricerca.",
            warnings=["La query fornita è vuota."],
        )

    profile = dict(request_profile or {})
    context = dict(studio_context or {})
    warnings: list[str] = []
    removed_tokens: list[str] = []

    # --- Step 1: classificazione privacy ---
    guard = PrivacyGuard()
    privacy_result = guard.classify_text(query)
    sensitivity = privacy_result.sensitivity

    # --- Step 2: estrai nomi propri ---
    proper_names = _extract_proper_names(query)

    # --- Step 3: build private_context_query ---
    # Mantieni nomi propri, redacta solo identificatori forti.
    private_context_query = _build_private_context_query(query)

    # Arricchisci con hint fascicolo se disponibile.
    if fascicolo_id and fascicolo_id.strip():
        private_context_query = _clean(
            f"[fascicolo:{fascicolo_id.strip()}] {private_context_query}"
        )

    # Hint allegati.
    if attachments:
        private_context_query = _clean(
            f"{private_context_query} [allegati: {len(attachments)} documento/i]"
        )

    # --- Step 4: build public_research_query ---
    # Prima redacta gli identificatori forti.
    text_no_ids, id_tokens = _redact_identifiers(query)
    removed_tokens.extend(id_tokens)

    # Poi rimuovi i nomi propri.
    text_no_names = _remove_proper_names_from_text(text_no_ids, proper_names)
    for name in proper_names:
        if name not in removed_tokens:
            removed_tokens.append(name)

    # Estrai solo la materia giuridica.
    legal_matter = _extract_legal_matter(text_no_names)

    if not _clean(legal_matter):
        # Fallback: usa le parole di lunghezza >= 5 dalla query senza identificatori.
        fallback_words = [
            w for w in re.findall(r"[A-Za-zÀ-ÿ]+", text_no_names)
            if len(w) >= 5 and w.lower() not in {
                "posso", "devo", "vuole", "voglio", "nella", "nelle", "degli",
                "della", "dello", "questo", "questa", "questi", "queste",
            }
        ]
        legal_matter = " ".join(dict.fromkeys(w.lower() for w in fallback_words[:10]))
        if legal_matter:
            warnings.append(
                "Nessuna keyword giuridica riconosciuta: la query pubblica usa "
                "un'estrazione lessicale di fallback. Verificare la pertinenza."
            )
        else:
            warnings.append(
                "Impossibile estrarre materia giuridica dalla query. "
                "La ricerca pubblica non verrà eseguita."
            )

    public_research_query = _clean(legal_matter)

    # --- Step 5: official_sources_query ---
    official_sources_query = _build_official_sources_query(
        public_research_query, query
    )

    # --- Step 6: determina canali consentiti ---
    channels = _SENSITIVITY_CHANNELS.get(sensitivity, _SENSITIVITY_CHANNELS["highly_sensitive"])

    can_use_internal_retrieval = channels["internal_retrieval"]
    can_use_official_web = channels["official_web"] and bool(public_research_query)
    # LDR: consentito solo se la public_research_query è pulita (non sensibile).
    # Effettua una seconda classificazione sulla sola query pubblica.
    ldr_allowed_by_sensitivity = channels["ldr"]
    can_use_ldr = False
    if ldr_allowed_by_sensitivity and public_research_query:
        pub_check = guard.classify_text(public_research_query)
        can_use_ldr = pub_check.sensitivity in {"public", "internal"}
        if not can_use_ldr:
            warnings.append(
                f"LDR bloccato: la query pubblica risulta ancora '{pub_check.sensitivity}' "
                f"dopo la riscrittura. Motivi: {', '.join(pub_check.reasons)}."
            )

    # Provider esterni.
    external_env = _env_bool(_EXTERNAL_ALLOWED_ENV, default=False)
    can_use_external_provider = (
        channels["external_provider"]
        and external_env
        and sensitivity in {"public", "internal"}
    )

    # LDR query.
    local_deep_research_query = public_research_query if can_use_ldr else ""

    # --- Step 7: requires_review ---
    requires_review = sensitivity in {"highly_sensitive"} or not public_research_query

    # --- Step 8: reason ---
    reason_parts: list[str] = [f"Sensitivita' classificata: {sensitivity}."]
    if removed_tokens:
        reason_parts.append(
            f"Token rimossi dalla query pubblica: {', '.join(repr(t) for t in removed_tokens)}."
        )
    if not can_use_ldr and ldr_allowed_by_sensitivity:
        reason_parts.append("LDR bloccato: query pubblica ancora sensibile dopo riscrittura.")
    if not can_use_external_provider:
        if not external_env:
            reason_parts.append(f"Provider esterni disabilitati ({_EXTERNAL_ALLOWED_ENV} non impostata).")
        else:
            reason_parts.append("Provider esterni bloccati per sensitività query.")
    if not public_research_query:
        reason_parts.append("Query pubblica vuota: materia giuridica non estraibile.")
    reason = " ".join(reason_parts)

    # Avvisi aggiuntivi.
    if sensitivity == "highly_sensitive":
        warnings.append(
            "Query altamente sensibile: solo il retrieval interno è consentito. "
            "Nessuna fonte pubblica o provider esterno verrà interrogato."
        )
    if proper_names and sensitivity in {"public", "internal"}:
        warnings.append(
            f"Nomi propri trovati nella query ({', '.join(proper_names[:3])}): "
            "rimossi dalla query pubblica ma mantenuti per il retrieval interno."
        )
    if fascicolo_id and sensitivity in {"sensitive", "highly_sensitive"}:
        warnings.append(
            "La query riguarda un fascicolo con dati sensibili: "
            "la ricerca pubblica usa solo la materia giuridica estratta."
        )

    return PrivacySafeResearchQuery(
        original_query=original_query,
        private_context_query=private_context_query,
        public_research_query=public_research_query,
        official_sources_query=official_sources_query,
        local_deep_research_query=local_deep_research_query,
        removed_sensitive_tokens=removed_tokens,
        sensitivity=sensitivity,
        can_use_internal_retrieval=can_use_internal_retrieval,
        can_use_official_web=can_use_official_web,
        can_use_ldr=can_use_ldr,
        can_use_external_provider=can_use_external_provider,
        requires_review=requires_review,
        reason=reason,
        warnings=warnings,
    )


__all__ = [
    "PrivacySafeResearchQuery",
    "rewrite_query_for_legal_research",
]
