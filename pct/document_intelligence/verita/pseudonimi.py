"""Pseudonimizzazione dei testi dei documenti prima che lascino il server per l'addestramento.

Autorizzazione dell'avvocato del 30/10/2026: i testi dei fascicoli possono essere copiati sul suo PC per
addestrare il modello di catalogazione solo dopo la pseudonimizzazione (GDPR art. 4, n. 5, e art. 32; art. 25
per la protezione fin dalla progettazione). Si sostituiscono:

- i nomi delle persone che il fascicolo conosce (cliente, controparte, giudice, avvocati, CTU, CTP…), parola per
  parola, in ogni forma maiuscola o minuscola;
- i nomi preceduti da un titolo («Avv.», «Dott.ssa», «Sig.»…) anche se il fascicolo non li conosce;
- indirizzi, luogo e data di nascita, partite IVA;
- email, codici fiscali, IBAN, numeri di ruolo e telefoni con l'oscuramento già usato dal gateway di Lex.

Resta un rischio residuo (un nome scritto senza titolo e assente dal fascicolo): per questo il file resta cifrato
nel trasferimento e si cancella dal PC a fine addestramento. La natura dell'atto, che serve al modello, resta.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from lex.gateway.privacy_guard import PrivacyGuard

# Campi del fascicolo che contengono nomi di persone (o di soggetti privati).
CAMPI_PERSONE = (
    "nome_cliente", "controparte", "giudice", "avvocato_controparte", "avvocato_referente", "avvocato_dominus",
    "attore_principale", "istruttore_pm_gip", "cancelliere", "ctu", "ctp",
)

# Parole di enti e di forma giuridica: non identificano una persona e servono a riconoscere l'atto.
_GENERICHE = {
    "ministero", "istruzione", "merito", "universita", "ricerca", "comune", "regione", "provincia", "agenzia",
    "entrate", "riscossione", "inps", "inail", "azienda", "sanitaria", "provinciale", "locale", "ufficio",
    "scolastico", "regionale", "tribunale", "corte", "appello", "procura", "repubblica", "giudice", "pace",
    "lavoro", "dello", "della", "delle", "degli", "dei", "del", "per", "con", "spa", "srl", "srls", "snc", "sas",
    "societa", "cooperativa", "banca", "credito", "italiana", "italia", "stato", "avvocatura", "dott", "avv",
    "dottssa", "prof", "sig", "sigra", "sigg", "altri", "altro", "nonche",
    # Preposizioni articolate elise («dell'Istruzione»): restano nel testo.
    "dell", "dall", "nell", "sull", "all", "coll", "dalla", "nella", "sulla", "alla",
}

_TITOLO = re.compile(
    r"\b(Avv\.?(?:ti)?|Avvocat[oa]|Dott\.?(?:ssa)?|Dr\.?|Prof\.?(?:ssa)?|Sig\.?(?:ra|ri|g\.)?|Signor[ae]?|Ing\.?|Geom\.?|Rag\.?)"
    r"[ \t]+(?:[A-ZÀ-Ý][\wÀ-ÿ'’]+[ \t]+){0,2}[A-ZÀ-Ý][\wÀ-ÿ'’]+")
_TIPO_VIA = (r"\b(?:Via|V\.le|Viale|Piazza|P\.za|Piazzale|Corso|C\.so|Largo|Vicolo|Contrada|C\.da|Località|Loc\.|Strada)"
             r"[ \t]+")
# Con il numero civico: fino al numero. Senza: fino a quattro parole con l'iniziale maiuscola.
_INDIRIZZO_CIVICO = re.compile(_TIPO_VIA + r"[A-Za-zÀ-ÿ'’. ]{2,50}?,?[ \t]*(?:n\.?|nr\.?|civ\.?)?[ \t]*\d{1,5}[A-Za-z]?\b")
_INDIRIZZO = re.compile(_TIPO_VIA + r"[A-ZÀ-Ý][\wÀ-ÿ'’.]*(?:[ \t][A-ZÀ-Ý][\wÀ-ÿ'’.]*){0,3}")
_NASCITA = re.compile(r"\b(nat[oaie])[ \t]+(?:a|in)[ \t]+[^\n,;(]{2,40}?[ \t]*(?:\([A-Z]{2}\))?[ \t]*(?:,[ \t]*)?il[ \t]+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}",
                      re.IGNORECASE)
_PIVA = re.compile(r"\b\d{11}\b")
_PAROLA_NOME = re.compile(r"[A-Za-zÀ-ÿ]{3,}")


def _normalizza(parola: str) -> str:
    return re.sub(r"[^a-z]", "", parola.casefold().translate(str.maketrans("àèéìòùáíóú", "aeeiouaiou")))


def parole_da_nascondere(valori: Iterable[str]) -> set[str]:
    """Le parole dei nomi noti, escluse quelle di enti e di forma giuridica."""
    nomi: set[str] = set()
    for valore in valori:
        for parola in _PAROLA_NOME.findall(str(valore or "")):
            chiave = _normalizza(parola)
            if len(chiave) >= 3 and chiave not in _GENERICHE:
                nomi.add(chiave)
    return nomi


def pseudonimizza(testo: str, nomi: set[str]) -> str:
    """Il testo con dati identificativi sostituiti da segnaposto; la struttura dell'atto resta."""
    # Partita IVA prima dell'oscuramento del gateway, che leggerebbe le undici cifre come un telefono.
    testo = _PIVA.sub("[PARTITA_IVA]", str(testo or ""))
    testo = PrivacyGuard().redact(testo)
    testo = _NASCITA.sub(lambda m: f"{m.group(1)} a [LUOGO] il [DATA_NASCITA]", testo)
    testo = _TITOLO.sub(lambda m: f"{m.group(1)} [NOME]", testo)
    testo = _INDIRIZZO_CIVICO.sub("[INDIRIZZO]", testo)
    testo = _INDIRIZZO.sub("[INDIRIZZO]", testo)
    if nomi:
        testo = _PAROLA_NOME.sub(lambda m: "[NOME]" if _normalizza(m.group(0)) in nomi else m.group(0), testo)
    return testo


__all__ = ["CAMPI_PERSONE", "parole_da_nascondere", "pseudonimizza"]
