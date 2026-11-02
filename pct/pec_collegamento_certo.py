"""Collegamento certo PEC → fascicolo: ruolo, cliente e ufficio coincidenti (regola dell'avvocato, 02/11/2026).

Una PEC si collega con certezza a un fascicolo quando coincidono **tutti e tre**:

1. il numero di ruolo con l'anno (RG n/anno, senza zeri iniziali né differenze di separatore) letto nella PEC
   è quello del fascicolo;
2. nome e cognome del cliente del fascicolo compaiono nella PEC (oggetto, corpo, parti lette dal presidio
   anche dalla Comunicazione.xml): maiuscole e accenti non contano, l'ordine nome/cognome nemmeno, ma devono
   esserci tutte le parole del nome, una accanto all'altra;
3. l'ufficio giudiziario della comunicazione è quello del fascicolo: l'ufficio mittente su dominio ministeriale
   (``giustiziacert.it``/``giustizia.it``) o, se l'indirizzo non lo identifica, l'ufficio letto nella
   comunicazione; entrambi riportati al bundle degli uffici (``pct/uffici_giudiziari.py``).

Fail-closed: se i tre controlli valgono per più di un fascicolo, se ne manca uno o se la PEC contraddice il
fascicolo (ruolo certificato, cliente certificato o codice fiscale discordanti, ``pct/pec_case_identity``), il
collegamento non è certo e resta la decisione ordinaria del linker (proposta da confermare).

Base normativa: art. 16 D.L. 179/2012 (comunicazioni e notificazioni di cancelleria per via telematica
all'indirizzo PEC del difensore); D.M. 44/2011 (regole tecniche del processo telematico: la comunicazione
porta l'ufficio mittente e il procedimento a cui si riferisce).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

#: Esito del linker per il collegamento certo: entra in ``LINK_STATI_CERTIFICATI`` (pct/pec_pipeline.py).
STATO_CERTO = "ruolo_cliente_ufficio_verificati"

#: Esiti ordinari del linker che il collegamento certo può superare. Restano fuori le ricevute (hanno la
#: loro prova), l'identità discordante (la PEC contraddice ogni candidato) e i collegamenti già certificati.
ESITI_SUPERABILI = frozenset({"proposte", "rg_non_sufficiente", "identita_incompleta", "nessun_candidato",
                              "identita_ambigua", "automatico"})

# ------------------------------------------------------------------ 1. numero di ruolo


def chiave_ruolo(valore: Any) -> tuple[str, str] | None:
    """«RG n. 0523/2026», «523-2026», «523/2026/LAV» → ("523", "2026"); senza anno → None."""
    cifre = re.findall(r"\d+", str(valore or ""))
    if len(cifre) < 2:
        return None
    numero, anno = cifre[0].lstrip("0") or "0", cifre[1]
    if len(anno) == 2:
        anno = f"20{anno}"
    return (numero, anno) if len(anno) == 4 else None


def ruolo_fascicolo(fascicolo: Any) -> tuple[str, str] | None:
    numero = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    if not numero:
        return None
    if re.search(r"\d\s*[/-]\s*\d", numero):
        return chiave_ruolo(numero)
    return chiave_ruolo(f"{numero}/{anno}") if anno not in {"", "0"} else None


# Forme del numero di ruolo usate dai sistemi ministeriali e dai depositi, oltre a «RG 123/2025»: oggetto delle
# comunicazioni di cancelleria SICID/SIECIC «COMUNICAZIONE 2539/2025/LAV», oggetto dei depositi «RG: 2539 - 2025»,
# «procedimento n. 1165/2023». Il registro finale (LAV, CC, VG…) resta fuori dalla chiave: l'ufficio lo verifica
# il terzo controllo. Fonte: art. 16 D.L. 179/2012; Specifiche tecniche DGSIA (Comunicazione.xml, oggetto PEC).
_RUOLO_MINISTERIALE = (
    re.compile(r"\bCOMUNICAZIONE\s+(\d{1,7})\s*/\s*(\d{4})\s*/\s*[A-Z]{2,6}\b", re.I),
    re.compile(r"\bR\.?\s*G\.?\s*(?:n\.?|nr\.?|numero)?\s*[:.]?\s*(\d{1,7})\s*[-/]\s*(\d{4})\b", re.I),
    re.compile(r"\bprocedimento\s+(?:n\.?|nr\.?|numero)\s*(\d{1,7})\s*/\s*(\d{4})\b", re.I),
)


def _ruoli_nel_testo(testo: str) -> list[str]:
    return [f"{m.group(1)}/{m.group(2)}" for pattern in _RUOLO_MINISTERIALE for m in pattern.finditer(testo or "")]


def ruoli_della_pec(parsed: dict[str, Any], profilo: dict[str, Any]) -> set[tuple[str, str]]:
    from pct.pec_pipeline import extract_rg_candidates

    testo = " ".join(_testi(parsed))
    valori: list[Any] = list(parsed.get("rg_candidates") or [])
    valori += [profilo.get(k) for k in ("numero_ruolo_certificato", "numero_rg", "rg", "numero_ruolo")]
    valori += extract_rg_candidates(testo) + _ruoli_nel_testo(testo)
    return {chiave for chiave in map(chiave_ruolo, valori) if chiave}


# ------------------------------------------------------------------ 2. nome e cognome del cliente


def parole(valore: Any) -> list[str]:
    """Parole minuscole senza accenti; le sigle puntate si ricompongono («S.r.l.» → «srl»)."""
    testo = "".join(c for c in unicodedata.normalize("NFKD", str(valore or "").casefold()) if not unicodedata.combining(c))
    grezze = re.findall(r"[a-z0-9]+", testo)
    out: list[str] = []
    sigla: list[str] = []
    for parola in [*grezze, ""]:
        if len(parola) == 1 and parola.isalpha():
            sigla.append(parola)
            continue
        out.extend(["".join(sigla)] if len(sigla) > 1 else sigla)
        sigla = []
        if parola:
            out.append(parola)
    return out


def _testi(parsed: dict[str, Any]) -> list[str]:
    from pct.pec_pipeline import _profile_party_values

    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
    profilo = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    return [str(headers.get("subject") or ""), str(body.get("text") or ""), str(body.get("html_text") or ""),
            *_profile_party_values(profilo)]


def nome_presente(nome_cliente: Any, testi: Iterable[str]) -> bool:
    """Tutte le parole del nome (almeno nome e cognome), contigue, in qualunque ordine, in uno dei testi."""
    attese = sorted(parole(nome_cliente))
    if len(attese) < 2:
        return False
    k = len(attese)
    for testo in testi:
        lette = parole(testo)
        if any(sorted(lette[i:i + k]) == attese for i in range(len(lette) - k + 1)):
            return True
    return False


# ------------------------------------------------------------------ 3. ufficio giudiziario

_VUOTE = {"di", "del", "della", "dei", "d", "per", "i", "il", "la", "presso", "ufficio", "ordinario", "ordinaria",
          "repubblica"}
# Sequenze di parole che nominano il tipo di ufficio, dalla più lunga; chiave breve come nel bundle.
_TIPI = (
    (("tribunale", "minorenni"), "tribmin"), (("tribunale", "sorveglianza"), "tsor"),
    (("corte", "appello"), "ca"), (("corte", "assise"), "assise"), (("corte", "cassazione"), "cassazione"),
    (("giudice", "pace"), "gdp"), (("procura", "generale"), "pg"),
    (("tribunale",), "tribunale"), (("tribmin",), "tribmin"), (("tm",), "tribmin"), (("tsor",), "tsor"),
    (("ca",), "ca"), (("corteappello",), "ca"), (("assise",), "assise"), (("gdp",), "gdp"),
    (("giudicedipace",), "gdp"), (("procura",), "procura"), (("pg",), "pg"), (("unep",), "unep"),
    (("cassazione",), "cassazione"),
)


def chiave_ufficio(valore: Any) -> str:
    """«Tribunale di Reggio Calabria», «tribunale.reggiocalabria», «Tribunale Ordinario - Reggio Calabria»
    → «tribunale.reggiocalabria»; «Ufficio del Giudice di Pace di Palmi» e «gdp.palmi» → «gdp.palmi».
    Le parole prima del tipo (servizio della casella: ``depositoattipenali.``, ``cancelleria.``) non contano;
    la sezione dopo la sede nemmeno. Stringa vuota se il tipo o la sede mancano."""
    testo = re.split(r"\bsez(?:ione)?\b", str(valore or "").split("@")[0], maxsplit=1, flags=re.I)[0]
    token = [t for t in parole(testo.replace("'", " ").replace("’", " ")) if t not in _VUOTE]
    for inizio in range(len(token)):
        for sequenza, tipo in _TIPI:
            if tuple(token[inizio:inizio + len(sequenza)]) == sequenza:
                sede = token[inizio + len(sequenza):]
                if tipo == "procura" and sede[:1] == ["tribunale"]:
                    sede = sede[1:]
                return f"{tipo}.{''.join(sede)}" if sede else ""
    return ""


_INDICE: dict[int, tuple[set[str], dict[str, set[str]]]] = {}


def _indice_bundle() -> tuple[set[str], dict[str, set[str]]]:
    """Chiavi degli uffici del bundle (nomi, descrizioni ministeriali, PEC) e chiavi per codice."""
    from pct.uffici_giudiziari import get_gestore

    uffici = get_gestore().carica()
    if id(uffici) not in _INDICE:
        chiavi: set[str] = set()
        per_codice: dict[str, set[str]] = {}
        for ufficio in uffici:
            proprie = {chiave_ufficio(ufficio.get(campo)) for campo in ("nome", "descrizione_ministero", "pec", "pec_ministero")}
            proprie.discard("")
            chiavi |= proprie
            for campo in ("codice", "codice_ministero"):
                if ufficio.get(campo):
                    per_codice.setdefault(str(ufficio[campo]).strip(), set()).update(proprie)
        _INDICE.clear()
        _INDICE[id(uffici)] = (chiavi, per_codice)
    return _INDICE[id(uffici)]


def uffici_fascicolo(fascicolo: Any) -> set[str]:
    note, per_codice = _indice_bundle()
    out: set[str] = set()
    for valore in (getattr(fascicolo, "tribunale", ""), getattr(fascicolo, "codice_ufficio_portale", "")):
        valore = str(valore or "").strip()
        out |= per_codice.get(valore, set()) or ({chiave_ufficio(valore)} & note)
    return out


def uffici_della_pec(parsed: dict[str, Any], profilo: dict[str, Any]) -> tuple[set[str], str]:
    """L'ufficio della comunicazione: prima il mittente ministeriale, poi l'ufficio letto nella comunicazione."""
    from pct.pec_pipeline import DOMINI_UFFICIO_GIUDIZIARIO, _indirizzi_del_messaggio

    note, _ = _indice_bundle()
    domini = "|".join(re.escape(dominio) for dominio in DOMINI_UFFICIO_GIUDIZIARIO)
    schema = re.compile(r"([A-Za-z0-9._%%+-]+)@(?:[A-Za-z0-9-]+\.)*(?:%s)(?![A-Za-z0-9.-])" % domini, re.I)
    mittente = {chiave_ufficio(locale) for voce in _indirizzi_del_messaggio(parsed) for locale in schema.findall(voce)}
    mittente &= note
    if mittente:
        return mittente, "mittente"
    letto = {chiave_ufficio(profilo.get("ufficio"))} & note
    return letto, "comunicazione" if letto else ""


# ------------------------------------------------------------------ la regola


def cerca_collegamento_certo(parsed: dict[str, Any], fascicoli: Iterable[Any], *, profilo: dict[str, Any] | None = None,
                             clienti: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Il fascicolo unico per cui valgono i tre controlli, o il motivo per cui non c'è. Non scrive nulla.

    ``profilo`` è il profilo processuale già arricchito dal linker (codice fiscale letto dai documenti);
    ``clienti`` le anagrafiche per id con il codice fiscale, per i soli controlli di contraddizione.
    """
    from pct.pec_case_identity import case_identity_evidence

    if profilo is None:
        profilo = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    ruoli = ruoli_della_pec(parsed, profilo)
    uffici, fonte_ufficio = uffici_della_pec(parsed, profilo)
    esito: dict[str, Any] = {"fascicolo_id": "", "stato": "", "motivo": "", "ufficio_da": fonte_ufficio,
                             "ruoli_letti": len(ruoli), "corrispondenze": []}
    if not ruoli:
        return {**esito, "motivo": "ruolo_con_anno_assente"}
    testi = _testi(parsed)
    tre: list[Any] = []
    for fascicolo in fascicoli:
        if ruolo_fascicolo(fascicolo) not in ruoli:
            continue
        verifiche = {"ruolo": True,
                     "cliente": nome_presente(getattr(fascicolo, "nome_cliente", ""), testi),
                     "ufficio": bool(uffici & uffici_fascicolo(fascicolo))}
        esito["corrispondenze"].append({"fascicolo_id": str(getattr(fascicolo, "id", "")), **verifiche})
        if all(verifiche.values()):
            tre.append(fascicolo)
    if not tre:
        if not esito["corrispondenze"]:
            return {**esito, "motivo": "ruolo_di_nessun_fascicolo"}
        manca_cliente = not any(c["cliente"] for c in esito["corrispondenze"])
        manca_ufficio = not any(c["ufficio"] for c in esito["corrispondenze"])
        dettaglio = "cliente_e_ufficio" if manca_cliente and manca_ufficio else "cliente" if manca_cliente else "ufficio" if manca_ufficio else "combinazione"
        return {**esito, "motivo": "controlli_incompleti", "manca": dettaglio}
    if len(tre) > 1:
        return {**esito, "motivo": "piu_fascicoli"}
    [fascicolo] = tre
    cliente = (clienti or {}).get(str(getattr(fascicolo, "id_cliente", "") or ""))
    # L'ufficio è già deciso sopra, sul bundle: qui contano solo le contraddizioni su ruolo, cliente e codice fiscale.
    conflitti = case_identity_evidence({**profilo, "ufficio": ""}, fascicolo, cliente)["conflicts"]
    if conflitti:
        return {**esito, "motivo": "pec_discordante", "conflitti": list(conflitti)}
    return {**esito, "fascicolo_id": str(getattr(fascicolo, "id", "")), "stato": STATO_CERTO,
            "motivo": "ruolo_cliente_ufficio_coincidenti"}


def applica_collegamento_certo(decisione: dict[str, Any], certo: dict[str, Any] | None) -> dict[str, Any]:
    """La decisione del linker con il collegamento certo, se c'è e se l'esito ordinario lo consente."""
    fascicolo_id = str((certo or {}).get("fascicolo_id") or "")
    if not fascicolo_id or str(decisione.get("status") or "") not in ESITI_SUPERABILI:
        return decisione
    if decisione.get("fascicolo_id") and str(decisione["fascicolo_id"]) != fascicolo_id:
        return decisione  # il linker ordinario indica un altro fascicolo: nessuna certezza
    motivi = sorted({*list(decisione.get("reasons") or []), "Ruolo, cliente e ufficio coincidenti"})
    return {**decisione, "fascicolo_id": fascicolo_id, "status": STATO_CERTO, "score": 1.0, "reasons": motivi, "rg_only": False}


__all__ = ["ESITI_SUPERABILI", "STATO_CERTO", "applica_collegamento_certo", "cerca_collegamento_certo", "chiave_ruolo",
           "chiave_ufficio", "nome_presente"]
