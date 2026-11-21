"""Confronto fra un articolo della biblioteca di consultazione e il testo vigente ufficiale (Akoma Ntoso di Normattiva).

Serve a sapere se la biblioteca mostra all'avvocato un testo non vigente. Ogni articolo finisce in una categoria:

- ``uguale``: stesso testo, a meno degli spazi;
- ``solo_grafia``: differenze senza valore normativo — spazi, punteggiatura, accenti scritti con l'apostrofo,
  richiami di nota «(12)», segni delle modifiche «(( ))», intestazione «Art. 6» / «Articolo 6», note redazionali
  della Gazzetta («Note all'art. 6: …»), avvisi aggiunti dalla biblioteca, intestazioni di titolo o capo;
- ``abrogato_ma_vigente``: la biblioteca dice «abrogato» ma il testo ufficiale vigente alla data è in vigore
  (per esempio gli articoli toccati dai testi unici del 2024-2026, la cui applicazione è stata rinviata);
- ``sostanza``: parole del testo normativo diverse (lettere, commi o periodi presenti in uno solo dei due testi).

Il confronto non modifica nulla: l'aggiornamento passa da ``lex.normativa.biblioteca.acquisizione.acquisisci``.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_NOTE = re.compile(r"-{5,}.*$", re.S)
_RIFERIMENTI = re.compile(r"\(\(|\)\)|\(\d{1,4}[a-z]?\)")
_INIZI_NOTE = (["note", "all", "art"], ["nota", "all", "art"], ["note", "all", "articolo"], ["avvertenza"],
               ["note", "alle", "premesse"], ["note", "al", "titolo"])
_APPARATI = ("avviso", "note", "nota", "avvertenza", "titolo", "capo", "sezione", "libro", "parte")
_ABROGATO = re.compile(r"\b(provvedimento abrogato|articolo abrogato|abrogato dal|abrogato\b)", re.I)


def _ascii(testo: str) -> str:
    return unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode().lower()


def parole(testo: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _ascii(_RIFERIMENTI.sub(" ", _NOTE.sub("", testo or ""))))


def senza_note_redazionali(w: list[str]) -> list[str]:
    for i in range(len(w)):
        if any(w[i:i + len(inizio)] == inizio for inizio in _INIZI_NOTE):
            return w[:i]
    return w


def senza_avviso_iniziale(w: list[str]) -> list[str]:
    if w[:1] == ["avviso"]:
        for i, x in enumerate(w):
            if x in ("art", "articolo") and i > 3:
                return w[i:]
    return w


def _apparato(x: list[str], y: list[str]) -> bool:
    insieme = set(x) | set(y)
    if not insieme or insieme <= {"art", "articolo"} | {str(i) for i in range(1000)}:
        return True
    return bool((x and not y and x[0] in _APPARATI) or (y and not x and y[0] in _APPARATI))


def classifica(biblioteca: str, vigente: str) -> tuple[str, list[tuple[str, str, str]]]:
    """(categoria, differenze sostanziali come (operazione, testo biblioteca, testo vigente))."""
    sb, sv = re.sub(r"\s+", "", _NOTE.sub("", biblioteca or "")), re.sub(r"\s+", "", _NOTE.sub("", vigente or ""))
    if sb == sv or (sv and sv in sb and len(sb) - len(sv) < 40):
        return "uguale", []
    piano = " ".join(re.sub(r"\s+", " ", biblioteca or "").split())
    if (_ABROGATO.search(piano[:300]) and len(piano) < 400 and len(vigente or "") > 400
            and not re.search(r"abrogat|soppress", (vigente or "")[:250], re.I)):
        return "abrogato_ma_vigente", [("replace", piano[:160], (vigente or "")[:160])]
    pb, pv = senza_avviso_iniziale(parole(biblioteca)), senza_note_redazionali(parole(vigente))
    if pb == pv:
        return "solo_grafia", []
    confronto = difflib.SequenceMatcher(None, pb, pv, autojunk=False)
    diverse = [(op, " ".join(pb[i1:i2]), " ".join(pv[j1:j2])) for op, i1, i2, j1, j2 in confronto.get_opcodes()
               if op != "equal" and not _apparato(pb[i1:i2], pv[j1:j2])]
    return ("sostanza" if diverse else "solo_grafia"), diverse


__all__ = ["classifica", "parole"]
