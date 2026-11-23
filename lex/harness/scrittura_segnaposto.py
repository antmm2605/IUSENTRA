"""Scrittura con segnaposto: lo scrittore scrive solo la prosa, i dati li mette l'harness.

Lo schema da riscrivere arriva al modello con ogni riferimento normativo, data, importo e altro numero sostituito da un
segnaposto ({{NORMA_1}}, {{DATA_2}}, {{IMPORTO_1}}, {{NUMERO_3}}). Il modello scrive la prosa usando i segnaposto; poi
l'harness li sostituisce con i valori certi. Il controllore scarta la stesura se compaiono cifre o riferimenti normativi
fuori dai segnaposto, se compare un segnaposto inesistente o se ne manca uno: l'invenzione di un dato è impossibile per
costruzione.
"""
from __future__ import annotations

import re
import time

from .controllo import _CITAZIONE
from .scrittura import Stesura, _chiama, _pulisci, _sezioni, elementi_persi

_DATA = re.compile(r"\b(?:(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+)?\d{1,2}/\d{1,2}/\d{4}\b")
_IMPORTO = re.compile(r"€\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
_NUMERO = re.compile(r"\b\d[\d.,]*(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies|"
                     r"terdecies))?(?:\.\d+)?\b")
_SEGNAPOSTO = re.compile(r"\{\{([A-Z]+_\d+)\}\}")

ISTRUZIONI = (
    "Sei l'assistente di uno studio legale italiano. Riscrivi in italiano forense, chiaro e professionale, il PARERE che "
    "segue, in paragrafi discorsivi (niente elenchi puntati). Nel testo ogni norma, data, importo e numero è sostituito "
    "da un segnaposto fra doppie graffe, per esempio {{NORMA_1}} o {{DATA_2}}. Regole vincolanti: usa TUTTI i "
    "segnaposto, scritti esattamente così, nel punto in cui servono; non scrivere mai cifre, date, importi o articoli di "
    "legge fuori dai segnaposto; non aggiungere norme, sentenze o fatti; non cambiare le conclusioni. Rispondi solo con "
    "il testo riscritto. In fondo al testo trovi l'elenco dei segnaposto: usali tutti e non usarne altri."
)


def con_segnaposto(blocco: str) -> tuple[str, dict[str, str]]:
    """Il blocco con i segnaposto e la mappa segnaposto → valore. Lo stesso valore ha sempre lo stesso segnaposto."""
    mappa: dict[str, str] = {}
    inversa: dict[str, str] = {}
    contatori: dict[str, int] = {}

    def segnaposto(tipo: str, valore: str) -> str:
        if valore not in inversa:
            contatori[tipo] = contatori.get(tipo, 0) + 1
            nome = f"{tipo}_{contatori[tipo]}"
            inversa[valore], mappa[nome] = nome, valore
        return "{{" + inversa[valore] + "}}"

    testo = blocco
    normalizzato = testo.replace("D.P.R.", "d.p.r.").replace("d.P.R.", "d.p.r.")
    pezzi, ultimo = [], 0
    for m in _CITAZIONE.finditer(normalizzato):
        pezzi += [testo[ultimo:m.start()], segnaposto("NORMA", testo[m.start():m.end()])]
        ultimo = m.end()
    testo = "".join(pezzi) + testo[ultimo:]
    for tipo, espr in (("DATA", _DATA), ("IMPORTO", _IMPORTO)):
        testo = espr.sub(lambda m, t=tipo: segnaposto(t, m.group(0)), testo)
    # Gli altri numeri (commi, «n. 3-bis», giorni) fuori dai segnaposto già messi.
    parti = re.split(r"(\{\{[A-Z]+_\d+\}\})", testo)
    testo = "".join(p if _SEGNAPOSTO.fullmatch(p) else _NUMERO.sub(lambda m: segnaposto("NUMERO", m.group(0)), p)
                    for p in parti)
    return testo, mappa


_VARIANTI = re.compile(r"\{\{\s*([A-Z]+)[ _]?(\d+)\s*\}\}|\{\s*([A-Z]+)_(\d+)\s*\}|\[\[?\s*([A-Z]+)_(\d+)\s*\]?\]")


def normalizza(stesura: str) -> str:
    """Le grafie vicine del segnaposto («{{ DATA_1 }}», «{DATA_1}», «[DATA_1]», «{{DATA 1}}») tornano «{{DATA_1}}»:
    la misura riguarda lo scrittore, non la grafia delle graffe."""
    def una(m: re.Match) -> str:
        tipo = m.group(1) or m.group(3) or m.group(5)
        num = m.group(2) or m.group(4) or m.group(6)
        return "{{" + f"{tipo}_{num}" + "}}"
    testo = _VARIANTI.sub(una, stesura)
    # «l'art. {{NORMA_1}}»: la norma è già completa nel segnaposto, il prefisso ripetuto si toglie.
    return re.sub(r"(?i)\b(?:l')?artt?\.\s*(?=\{\{NORMA_)", "", testo)


def controlla(stesura: str, mappa: dict[str, str], schema: str = "") -> str:
    """Vuoto se la stesura usa i segnaposto obbligatori, nessuno inesistente, e non scrive cifre fuori da essi.
    Obbligatori: norme, date e importi; i NUMERO (commi, giorni) possono mancare se la frase li rende superflui."""
    usati = set(_SEGNAPOSTO.findall(stesura))
    estranei = sorted(usati - set(mappa))
    if estranei:
        return "segnaposto inesistenti: " + ", ".join(estranei)
    mancanti = sorted(k for k in set(mappa) - usati if not k.startswith("NUMERO_"))
    if mancanti:
        return "segnaposto mancanti: " + ", ".join(mancanti[:6]) + ("…" if len(mancanti) > 6 else "")
    fuori = _SEGNAPOSTO.sub("", stesura)
    if re.search(r"\d", fuori):
        return "cifre fuori dai segnaposto: " + ", ".join(sorted(set(re.findall(r"\S*\d\S*", fuori)))[:5])
    persi = elementi_persi(schema, stesura) if schema else []
    if persi:
        return "elementi decisivi persi: " + ", ".join(persi)
    if len(fuori.strip()) < 80:
        return "stesura vuota o troppo breve"
    return ""


def sostituisci(stesura: str, mappa: dict[str, str]) -> str:
    testo = _SEGNAPOSTO.sub(lambda m: mappa[m.group(1)], stesura)
    # «euro € 98», «€ € 98»: la valuta è già nell'importo
    return __import__("re").sub(r"(?i)(?:\beuro|€)\s+(?=€)", "", testo)


def _registra(scrittore: str, schema: str, grezza: str) -> None:
    import json
    import os

    percorso = os.environ.get("LEX_BANCO_GREZZI") or "/home/antmm2605/iusentra-controlli/lex/confronto-scrittori/grezzi_segnaposto.jsonl"
    if percorso:
        with open(percorso, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"scrittore": scrittore, "schema": schema, "grezza": grezza}, ensure_ascii=False) + "\n")


def scrivi_con_segnaposto(testo_deterministico: str, scrittore: str, timeout: float = 300.0) -> Stesura:
    prima, blocco, dopo = _sezioni(testo_deterministico)
    if not blocco or not scrittore:
        return Stesura(testo_deterministico, "deterministico", True, "nessuna sezione da riscrivere", 0.0)
    schema, mappa = con_segnaposto(blocco)
    obbligatori = [k for k in mappa if not k.startswith("NUMERO_")]
    schema += ("\n\nSegnaposto da usare, tutti e solo questi: " + ", ".join("{{" + k + "}}" for k in mappa)
               + (". Obbligatori: " + ", ".join("{{" + k + "}}" for k in obbligatori) if obbligatori else "") + ".")
    t0 = time.monotonic()
    motivo = ""
    for _ in range(2):
        try:
            grezza = _pulisci(_chiama(scrittore, schema, timeout, istruzioni=ISTRUZIONI))
            stesura = normalizza(grezza)
            _registra(scrittore, schema, grezza)
        except Exception as exc:
            return Stesura(testo_deterministico, scrittore, False, f"servizio non disponibile: {type(exc).__name__}",
                           time.monotonic() - t0)
        motivo = controlla(stesura, mappa, blocco)
        if not motivo:
            testo = "\n".join(x for x in (prima, "**Parere**", sostituisci(stesura, mappa), dopo) if x)
            return Stesura(testo, scrittore, True, "", time.monotonic() - t0)
    return Stesura(testo_deterministico, scrittore, False, motivo, time.monotonic() - t0)


# ---------------------------------------------------------------- scrittura per punto (modalità finale con segnaposto)
_RIF_FINALI = re.compile(r"\s*\((?:artt?\.|art\.)[^()]*(?:\([^()]*\)[^()]*)*\)\s*\.?\s*$")
_ETICHETTA = re.compile(r"^([^:.;]{3,70}):\s+")
_RIGA_NUMERATA = re.compile(r"(?m)^\s*\[(\d+)\]\s*(.+)$")

ISTRUZIONI_PUNTI = (
    "Sei l'assistente di uno studio legale italiano. Ricevi un elenco numerato di frasi di un parere ([1], [2], …). "
    "Riscrivi OGNI frase in italiano forense chiaro e scorrevole, una per riga, conservando il numero fra parentesi quadre "
    "all'inizio della riga. Regole vincolanti: ogni dato è un segnaposto fra doppie graffe ({{DATA_1}}, {{IMPORTO_2}}, "
    "{{NORMA_1}}, {{NUMERO_3}}): usa nella stessa frase tutti i segnaposto che contiene, scritti esattamente così; non "
    "scrivere cifre, date, importi o articoli di legge fuori dai segnaposto; conserva il senso, le negazioni e gli obblighi "
    "(«non è obbligatoria», «a pena di decadenza»); non aggiungere fatti, norme o sentenze; non unire né dividere le frasi. "
    "Rispondi solo con le righe numerate."
)


def prepara_punti(testo_deterministico: str):
    """(prima, righe, dopo, punti, richiesta, mappe) per la scrittura per punto; None se non c'è nulla da riscrivere."""
    prima, blocco, dopo = _sezioni(testo_deterministico)
    if not blocco:
        return None
    righe = blocco.split("\n")
    punti: list[tuple[int, str, str, str, dict[str, str]]] = []
    for i, riga in enumerate(righe):
        if not riga.startswith("- "):
            continue
        corpo = riga[2:]
        m_rif = _RIF_FINALI.search(corpo)
        suffisso = corpo[m_rif.start():].strip() if m_rif else ""
        corpo = corpo[:m_rif.start()] if m_rif else corpo
        m_et = _ETICHETTA.match(corpo)
        etichetta = m_et.group(1) if m_et else ""
        corpo = corpo[m_et.end():] if m_et else corpo
        con, mappa = con_segnaposto(corpo)
        punti.append((i, etichetta, con, suffisso, mappa))
    if not punti:
        return None
    richiesta, mappe = [], []
    for n, (_, _, con, _, mappa) in enumerate(punti, 1):
        rinomina = {k: f"{k.split('_')[0]}_{n}{k.split('_')[1]}" for k in mappa}
        for vecchio, nuovo in rinomina.items():
            con = con.replace("{{" + vecchio + "}}", "{{" + nuovo + "}}")
        mappe.append({rinomina[k]: v for k, v in mappa.items()})
        richiesta.append(f"[{n}] {con}")
    return prima, righe, dopo, punti, richiesta, mappe


def scrivi_per_punto(testo_deterministico: str, scrittore: str, timeout: float = 300.0) -> Stesura:
    """Ogni punto dell'argomentazione è riscritto da solo: l'etichetta iniziale («Negoziazione assistita obbligatoria:»)
    e le norme finali fra parentesi restano dell'harness, nella loro posizione; dati come segnaposto. Un punto che non
    supera il controllo resta quello deterministico: la stesura non può spostare una norma su un'altra affermazione né
    togliere un punto."""
    pronto = prepara_punti(testo_deterministico) if scrittore else None
    if pronto is None:
        return Stesura(testo_deterministico, "deterministico", True, "nessuna sezione da riscrivere", 0.0)
    prima, righe, dopo, punti, richiesta, mappe = pronto
    t0 = time.monotonic()
    try:
        risposta = _pulisci(_chiama(scrittore, "\n".join(richiesta), timeout, istruzioni=ISTRUZIONI_PUNTI))
    except Exception as exc:
        return Stesura(testo_deterministico, scrittore, False, f"servizio non disponibile: {type(exc).__name__}",
                       time.monotonic() - t0)
    _registra(scrittore, "\n".join(richiesta), risposta)
    nuove = {int(m.group(1)): normalizza(m.group(2).strip()) for m in _RIGA_NUMERATA.finditer(risposta)}
    riscritti, motivi = 0, []
    for n, (i, etichetta, con, suffisso, _) in enumerate(punti, 1):
        frase = nuove.get(n, "")
        motivo = "punto mancante" if not frase else _controlla_punto(frase, mappe[n - 1], con)
        if motivo:
            motivi.append(f"[{n}] {motivo}")
            continue
        testo = sostituisci(frase, mappe[n - 1]).rstrip(" .")
        if etichetta and testo[:1].isupper() and not testo[:2].isupper():
            testo = testo[:1].lower() + testo[1:]
        righe[i] = "- " + (f"{etichetta}: " if etichetta else "") + testo + "." + (f" {suffisso}" if suffisso else "")
        riscritti += 1
    testo = "\n".join(x for x in (prima, "\n".join(righe), dopo) if x)
    accettata = riscritti > 0
    return Stesura(testo, scrittore, accettata, f"punti riscritti {riscritti}/{len(punti)}" + (
        "; scartati: " + "; ".join(motivi[:4]) if motivi else ""), time.monotonic() - t0)


def _controlla_punto(frase: str, mappa: dict[str, str], originale: str) -> str:
    usati = set(_SEGNAPOSTO.findall(frase))
    if usati - set(mappa):
        return "segnaposto inesistenti"
    if set(k for k in mappa if not k.startswith("NUMERO_")) - usati:
        return "segnaposto mancanti"
    fuori = _SEGNAPOSTO.sub("", frase)
    if re.search(r"\d", fuori):
        return "cifre fuori dai segnaposto"
    # Riferimenti normativi fuori dai segnaposto: ammessi solo quanti ne ha già la frase di partenza («l'art.
    # {{NUMERO_1}} dell'ordinamento giudiziario» resta), mai uno in più.
    _rif = re.compile(r"(?i)\bartt?\.\s|\bc\.p\.c\.|\bc\.c\.|\bd\.lgs\.|\bd\.l\.|\bl\.\s")
    if len(_rif.findall(fuori)) > len(_rif.findall(_SEGNAPOSTO.sub("", originale))):
        return "riferimento normativo fuori dai segnaposto"
    persi = elementi_persi(originale, frase)
    if persi:
        return "elementi decisivi persi: " + ", ".join(persi)
    if len(fuori.strip()) < 20:
        return "frase troppo breve"
    return ""
