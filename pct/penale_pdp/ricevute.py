"""Lettura delle ricevute del PDP e confronto con il deposito preparato.

Testi verificati il 25/09/2026 sulle ricevute reali scaricate dal portale 6.11.10
(«Elenco depositi» → ricevuta di deposito ed esito, PDF IronPdf con font
Identity-H e mappa ToUnicode, quindi testo nativo estraibile):

- **ricevuta di accettazione del deposito**: «IDENTIFICATIVO AAAA/NNNNNNN …
  L'avvocato NOME CF ha inviato all'ufficio UFFICIO in data GG/MM/AAAA alle
  ore HH:MM:SS, in relazione al procedimento: REGISTRO … nr. N/AAAA,
  indirizzato al Magistrato …, l'atto di TIPO ATTO, nell'interesse dei
  seguenti soggetti rappresentati, in qualità di RUOLO: SOGGETTI con nr. N
  allegati». Attesta il deposito ai sensi dell'art. 87 co. 6-bis D.Lgs.
  150/2022. **Non riporta impronte hash**: il confronto con il deposito
  preparato si fa su identificativo, avvocato, ufficio, procedimento, atto,
  soggetti e numero degli allegati;
- **ricevuta di esito**: «Il deposito con IDENTIFICATIVO …, inviato
  all'ufficio … in data … alle ore …, è stato rifiutato|accettato in data …
  alle ore … con la seguente motivazione: …».

Il testo si legge, non si indovina: un campo che non si trova resta vuoto e
l'avvocato lo completa guardando la ricevuta. Le parole possono arrivare
spezzate dall'impaginazione (crenatura: «POR T ALE»), quindi le ancore
tollerano spazi dentro le parole.
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Any, Iterable

from . import stati

_CF = r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"
_DATA = r"(\d{1,2}/\d{1,2}/\d{4})"
_ORA = r"(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
_PROCURE = frozenset({"PM-U", "PM-G", "PMM-U", "PGCAP-U"})


def testo_pdf(dati: bytes) -> str:
    """Il testo della ricevuta PDF (il PDP la genera nativa, non scansionata)."""
    try:
        from pypdf import PdfReader

        return "\n".join((pagina.extract_text() or "") for pagina in PdfReader(io.BytesIO(dati)).pages)
    except Exception:
        return ""


def _normale(testo: str) -> str:
    """Legature (ﬁ, ﬃ) sciolte, apostrofi uniformi, spazi compattati."""
    testo = unicodedata.normalize("NFKC", str(testo or "")).replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", testo).strip()


def _a(frase: str) -> str:
    """Un'ancora che tollera spazi dentro le parole (testo spezzato dalla crenatura)."""
    parti = []
    for carattere in frase:
        if carattere == " ":
            parti.append(r"\s*")
        else:
            parti.append(re.escape(carattere) + r"\s?")
    return "".join(parti)


def _trova(schema: str, testo: str) -> re.Match[str] | None:
    return re.search(schema, testo, re.I)


def _iso(data: str, ora: str = "") -> str:
    giorno, mese, anno = (int(x) for x in data.split("/"))
    base = f"{anno:04d}-{mese:02d}-{giorno:02d}"
    if not ora:
        return base
    pezzi = re.split(r"[:.]", ora) + ["00"]
    return f"{base}T{int(pezzi[0]):02d}:{pezzi[1]}:{pezzi[2]}"


def _pulito(valore: str) -> str:
    return re.sub(r"\s+", " ", valore or "").strip(" ,.;:")


def _ricevuta_esito(testo: str) -> dict[str, Any] | None:
    trovata = _trova(
        _a("Il deposito con IDENTIFICATIVO") + r"\s*(\d{4}\s*/\s*\d{6,8}),?\s*" + _a("inviato all'ufficio") + r"\s*(.+?)\s*"
        + _a("in data") + r"\s*" + _DATA + r"\s*" + _a("alle ore") + r"\s*" + _ORA + r"\s*,?\s*" + _a("è stato") + r"\s*"
        + r"([a-zà ]+?)\s*" + _a("in data") + r"\s*" + _DATA + r"\s*" + _a("alle ore") + r"\s*" + _ORA, testo)
    if not trovata:
        return None
    parola = re.sub(r"\s+", "", trovata.group(5)).casefold()
    stato = stati.normalizza(parola) or ("ERRORE_TECNICO" if "errore" in parola else "")
    motivazione = _trova(_a("motivazione") + r"\s*:\s*(.+?)\s*(?:" + _a("Roma") + r"\s*,\s*" + _DATA + r"|$)", testo)
    return {
        "tipo": "esito",
        "identificativo": re.sub(r"\s+", "", trovata.group(1)),
        "ufficio": _pulito(trovata.group(2)),
        "dataInvio": _iso(trovata.group(3), trovata.group(4)),
        "stato": stato,
        "dataEsito": _iso(trovata.group(6), trovata.group(7)),
        "motivazione": _pulito(motivazione.group(1))[:1000] if motivazione else "",
    }


def _soggetti(testo: str) -> list[dict[str, str]]:
    blocco = _trova(_a("soggetti rappresentati") + r"\s*,?\s*(.+?)\s*" + _a("con nr") + r"\s*\.", testo)
    if not blocco:
        return []
    voci = []
    for ruolo in re.finditer(_a("in qualità di") + r"\s*(.+?)\s*:\s*(.+?)(?=\s*" + _a("in qualità di") + r"|$)", blocco.group(1), re.I):
        nomi = _pulito(ruolo.group(2))
        persone = re.findall(r"([A-ZÀ-Ý'][A-ZÀ-Ý' .-]*?)\s+(\d{1,2}/\d{1,2}/\d{4})", nomi) or [(nomi, "")]
        for nome, nato in persone:
            voci.append({"ruolo": re.sub(r"\s+", "", ruolo.group(1)), "nome": _pulito(nome), "dataNascita": _iso(nato) if nato else ""})
    return voci


def _ricevuta_deposito(testo: str) -> dict[str, Any]:
    identificativo = _trova(_a("IDENTIFICATIVO") + r"\s*(\d{4}\s*/\s*\d{6,8})", testo)
    avvocato = _trova(_a("L'avvocato") + r"\s*(.+?)\s*(" + _CF + r")\s*" + _a("ha inviato"), testo)
    ufficio = _trova(_a("all'ufficio") + r"\s*(.+?)\s*" + _a("in data") + r"\s*" + _DATA + r"\s*" + _a("alle ore") + r"\s*" + _ORA, testo)
    procedimento = _trova(_a("procedimento") + r"\s*:\s*(.+?)\s*" + _a("nr") + r"\s*\.\s*(\d+)\s*/\s*(\d{4})", testo)
    magistrato = _trova(_a("al Magistrato") + r"\s*(.+?)\s*,\s*" + _a("l'atto di"), testo)
    atto = _trova(_a("l'atto di") + r"\s*(.+?)\s*,\s*" + _a("nell'interesse"), testo)
    allegati = _trova(_a("con nr") + r"\s*\.\s*(\d+)\s*" + _a("allegati"), testo)
    return {
        "tipo": "deposito",
        "identificativo": re.sub(r"\s+", "", identificativo.group(1)) if identificativo else "",
        "avvocato": _pulito(avvocato.group(1)) if avvocato else "",
        "cfAvvocato": avvocato.group(2).upper() if avvocato else "",
        "ufficio": _pulito(ufficio.group(1)) if ufficio else "",
        "dataInvio": _iso(ufficio.group(2), ufficio.group(3)) if ufficio else "",
        "registro": ({"etichetta": _pulito(procedimento.group(1)), "numero": procedimento.group(2), "anno": procedimento.group(3)}
                     if procedimento else {}),
        "magistrato": _pulito(magistrato.group(1)) if magistrato else "",
        "atto": _pulito(atto.group(1)) if atto else "",
        "soggetti": _soggetti(testo),
        "allegati": int(allegati.group(1)) if allegati else None,
        "stato": "INVIATO" if identificativo else "",
        "motivazione": "",
    }


def leggi_ricevuta(testo: str) -> dict[str, Any]:
    """I dati di una ricevuta del PDP (di deposito o di esito), con i campi non trovati."""
    pulito = _normale(testo)
    dati = _ricevuta_esito(pulito) or _ricevuta_deposito(pulito)
    dati["mancanti"] = [chiave for chiave in ("identificativo", "dataInvio") if not dati.get(chiave)]
    dati["statoEtichetta"] = stati.etichetta(dati["stato"]) if dati.get("stato") else ""
    return dati


def _chiave(valore: str) -> str:
    """Confronto senza spazi, accenti, maiuscole, punteggiatura e rinvii normativi tra parentesi."""
    senza_rinvii = re.sub(r"\([^)]*\)", "", _normale(valore))
    base = unicodedata.normalize("NFKD", senza_rinvii)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in base if not unicodedata.combining(c)).casefold())


_PAROLE_VUOTE = frozenset("a al alla allo ai agli alle da dal dalla dei degli delle del della dello di e ed il i in la le lo per su".split())


def _parole(valore: str) -> set[str]:
    """Le parole significative di un nome d'atto: il catalogo scrive «Nomina difensore di fiducia», la ricevuta «Nomina a difensore di fiducia»."""
    senza_rinvii = re.sub(r"\([^)]*\)", "", _normale(valore))
    base = unicodedata.normalize("NFKD", senza_rinvii).casefold()
    parole = re.findall(r"[a-z0-9]+", "".join(c for c in base if not unicodedata.combining(c)))
    return {p for p in parole if p not in _PAROLE_VUOTE}


def confronta_ricevuta(letti: dict[str, Any], *, identificativo: str = "", cf_avvocato: str = "", ufficio_codice: str = "",
                       registri: Iterable[dict[str, Any]] = (), nome_atto: str = "", soggetti: Iterable[dict[str, Any]] = (),
                       file_preparati: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """La ricevuta dice quello che IUSENTRA ha preparato? Ogni voce: atteso, letto, esito."""
    voci: list[dict[str, Any]] = []

    def voce(campo: str, etichetta: str, atteso: str, letto: str, uguale: bool | None) -> None:
        if uguale is not None and letto:
            voci.append({"campo": campo, "etichetta": etichetta, "atteso": atteso, "letto": letto, "ok": bool(uguale)})

    if identificativo:
        voce("identificativo", "Identificativo", identificativo, letti.get("identificativo", ""), letti.get("identificativo") == identificativo)
    if cf_avvocato:
        voce("avvocato", "Codice fiscale dell'avvocato", cf_avvocato.upper(), letti.get("cfAvvocato", ""),
             letti.get("cfAvvocato", "").upper() == cf_avvocato.upper())
    if ufficio_codice and letti.get("ufficio"):
        procura_attesa = ufficio_codice.upper() in _PROCURE
        procura_letta = "procura" in _chiave(letti["ufficio"])
        voce("ufficio", "Ufficio destinatario", "Procura" if procura_attesa else "Ufficio giudicante",
             letti["ufficio"], procura_attesa == procura_letta)
    registro = letti.get("registro") or {}
    if registro.get("numero"):
        numeri = {(str(r.get("register_number", "")).lstrip("0"), str(r.get("register_year", ""))) for r in registri}
        voce("registro", "Numero di registro", ", ".join(f"{n}/{a}" for n, a in sorted(numeri)) or "—",
             f"{registro['numero']}/{registro['anno']}", (registro["numero"].lstrip("0"), registro["anno"]) in numeri if numeri else None)
    if nome_atto and letti.get("atto"):
        atteso, letto = _parole(nome_atto), _parole(letti["atto"])
        voce("atto", "Tipo di atto", nome_atto, letti["atto"], bool(letto) and (atteso <= letto or letto <= atteso))
    soggetti = [dict(s) for s in soggetti]
    if soggetti and letti.get("soggetti"):
        voce("soggetti", "Soggetti rappresentati", str(len(soggetti)), str(len(letti["soggetti"])), len(soggetti) == len(letti["soggetti"]))
    allegati_attesi = sum(1 for f in file_preparati if f.get("ruolo") == "allegato")
    if letti.get("allegati") is not None:
        voce("allegati", "Numero di allegati", str(allegati_attesi), str(letti["allegati"]), allegati_attesi == letti["allegati"])
    corrispondenti = sum(1 for v in voci if v["ok"])
    diversi = [v["etichetta"] for v in voci if not v["ok"]]
    if not voci:
        messaggio = "La ricevuta non riporta dati confrontabili: controllala a vista."
    elif not diversi:
        messaggio = f"La ricevuta corrisponde al deposito preparato ({corrispondenti} controlli su {len(voci)})."
    else:
        messaggio = "La ricevuta non corrisponde al deposito preparato su: " + ", ".join(diversi).lower() + "."
    return {"verificabile": bool(voci), "corrispondenti": corrispondenti, "totale": len(voci), "voci": voci, "messaggio": messaggio}


__all__ = ["confronta_ricevuta", "leggi_ricevuta", "testo_pdf"]
