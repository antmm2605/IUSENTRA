"""Estremi del procedimento dalla relata e dagli atti allegati alla PEC di notificazione.

La relata di notifica in proprio indica per legge l'ufficio giudiziario, le parti e il numero di ruolo
(art. 3-bis, comma 5, L. 53/1994): qui se ne legge il testo (PDF allegato, anche firmato .p7m, compreso
il messaggio originale dentro la ricevuta completa) e si costruisce la lettura da sottoporre ai tre controlli
di ``pct.pec_collegamento_certo``, con l'ufficio della relata e non quello del mittente (che è lo studio).

Nessun ``from __future__``: il file si concatena allo script di sola lettura del server.
"""

import io
import re
from email import message_from_bytes, policy

LIMITE_PDF = 8 * 1024 * 1024
MASSIMO_PDF = 6
_UFFICIO = re.compile(
    r"\b(Tribunale(?:\s+per\s+i\s+Minorenni|\s+di\s+Sorveglianza)?|Corte\s+d['’]\s?Appello|Giudice\s+di\s+Pace|Ufficio\s+del\s+Giudice\s+di\s+Pace|"
    r"Corte\s+d['’]\s?Assise|T\.?A\.?R\.?|Tribunale\s+Amministrativo\s+Regionale)\s+(?:di|del|della|per\s+il|per\s+la|dell['’])?\s*"
    r"((?:[A-ZÀ-Ý][\w'’À-ÿ-]+\s?){1,4})"
)


def _testo_pdf(dati):
    try:
        from pypdf import PdfReader

        return "\n".join((pagina.extract_text() or "") for pagina in PdfReader(io.BytesIO(dati)).pages[:20])
    except Exception:  # noqa: BLE001 - PDF illeggibile: nessun testo
        return ""


def _sbusta(dati, nome):
    if not nome.endswith((".p7m", ".pm7")):
        return dati
    try:
        from pct.firme_cades import der_da_base64, extract_signed_payload

        return extract_signed_payload(der_da_base64(dati)) or b""
    except Exception:  # noqa: BLE001 - busta firmata illeggibile
        return b""


def testi_dal_messaggio(mime):
    """I testi della relata (per prima) e degli atti PDF allegati, compresi quelli del messaggio originale nella ricevuta."""
    try:
        messaggio = message_from_bytes(bytes(mime or b""), policy=policy.compat32)
    except Exception:  # noqa: BLE001
        return []
    parti = []
    for parte in messaggio.walk():
        nome = str(parte.get_filename() or "").casefold()
        if ".pdf" not in nome:
            continue
        dati = parte.get_payload(decode=True) or b""
        if not dati or len(dati) > LIMITE_PDF:
            continue
        parti.append((0 if "relata" in nome else 1, nome, dati))
    testi = []
    for _ordine, nome, dati in sorted(parti, key=lambda p: p[0])[:MASSIMO_PDF]:
        testo = _testo_pdf(_sbusta(dati, nome))
        if testo.strip():
            testi.append(testo)
    return testi


def ufficio_dal_testo(testi, note, chiave_ufficio):
    """L'ufficio giudiziario nominato nei testi, se è uno solo del bundle; altrimenti stringa vuota."""
    trovati = {}
    for testo in testi:
        for m in _UFFICIO.finditer(re.sub(r"\s+", " ", testo or "")):
            parole = m.group(2).split()
            for n in range(len(parole), 0, -1):
                candidato = f"{m.group(1)} di {' '.join(parole[:n])}"
                chiave = chiave_ufficio(candidato)
                if chiave and chiave in note:
                    trovati.setdefault(chiave, candidato)
                    break
    return next(iter(trovati.values())) if len(trovati) == 1 else ""


def lettura_con_relata(parsed, testi, ufficio):
    """La lettura della PEC con il testo della relata e l'ufficio della relata (mittente e destinatari tolti)."""
    intest = dict(parsed.get("headers") or {})
    for campo in ("from", "to", "cc"):
        intest[campo] = []
    corpo = dict(parsed.get("body") or {})
    corpo["text"] = "\n".join([str(corpo.get("text") or ""), *testi])[:200000]
    profilo = dict(parsed.get("procedural_profile") or {})
    profilo["ufficio"] = ufficio
    return {**parsed, "headers": intest, "body": corpo, "procedural_profile": profilo, "rg_candidates": list(parsed.get("rg_candidates") or [])}
