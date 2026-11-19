"""Riconvalida delle definizioni automatiche: una sentenza che non è della causa non definisce il fascicolo.

Il vecchio automatismo «Sentenza indicizzata da Lex AI» (e il presidio che lo seguiva) portava il fascicolo a
«definito» appena trovava una sentenza fra i documenti. Una sentenza allegata al ricorso come precedente non è un
atto del giudizio (art. 115 c.p.c.: il giudice decide sulle prove proposte; il precedente è un argomento), non porta
il ruolo del fascicolo (art. 168 c.p.c.; art. 36 disp. att. c.p.c.) e, se è anteriore all'iscrizione a ruolo, non
può decidere questa causa (`pct/atto_della_causa.py`, G-8). Solo la sentenza che definisce il giudizio lo chiude
(art. 279, secondo comma, c.p.c.): se dopo di essa il giudice della causa fissa un'altra udienza, la causa è
pendente (la sentenza era non definitiva o non era della causa).

Regola, sul modello della causa già calcolato (`pct/ragionamento`), modulo puro:

- si riconsidera solo lo stato DEFINITO portato da un automatismo (autori in ``AUTORI_AUTOMATICI``) e non toccato
  dopo da una persona: lo stato deciso dall'avvocato non si tocca mai;
- la definizione cade se (a) nel modello non c'è nessuna sentenza della causa e la sentenza citata dalla voce è
  un atto di contorno (altro ruolo, data anteriore all'iscrizione, precedente prodotto), oppure (b) il giudice
  della causa ha fissato un'udienza successiva alla sentenza della causa (o, senza sentenza della causa, successiva
  alla definizione automatica);
- un'udienza fissata da un provvedimento di correzione dell'errore materiale (artt. 287-288 c.p.c.) non prova la
  pendenza;
- in ogni altro caso la definizione resta com'è (esito indeterminato): niente si cambia senza prova.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

VERSIONE = "definizione-riconvalida.v1"
AUTORE = "riconvalida automatica della definizione"
# Chi ha scritto la voce di avanzamento a «DEFINITO» senza una decisione dell'avvocato.
AUTORI_AUTOMATICI = frozenset({
    "lex ai backfill", "iusentra presidio automatico", "automatico dalla sentenza", "motore-sentenza-verificata", "iusentra",
})
DESCRIZIONI_AUTOMATICHE = ("sentenza indicizzata da lex ai",)
NORME = ("art. 279, secondo comma, c.p.c.", "art. 115 c.p.c.", "art. 168 c.p.c.", "art. 36 disp. att. c.p.c.")
_CORREZIONE = re.compile(r"\bcorrez+ion\w*|\berrore\s+materiale\b|\bart\.?\s*28[78]\b", re.I)
_DOCUMENTO = re.compile(r"Documento:\s*(?P<id>[^;]+?)\s*(?:;|$)", re.I)
_SHA = re.compile(r"SHA-256\s+(?P<sha>[0-9a-f]{64})", re.I)
_SENTENZA_CITATA = re.compile(r"\bSentenza\s+n\.\s*(?P<numero>\d+)\s*/\s*(?P<anno>(?:19|20)\d{2})", re.I)
_RG_CITATO = re.compile(r"\bRG\s+n\.\s*0*(?P<numero>\d+)\s*/\s*(?P<anno>(?:19|20)\d{2})", re.I)


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _campo(voce: Any, nome: str) -> str:
    return _testo(voce.get(nome) if isinstance(voce, Mapping) else getattr(voce, nome, ""))


def _data_it(iso: str) -> str:
    iso = _testo(iso)[:10]
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) == 10 else iso


def e_automatica(voce: Any) -> bool:
    autore = _campo(voce, "avvocato").casefold()
    descrizione = _campo(voce, "descrizione").casefold()
    return autore in AUTORI_AUTOMATICI or (not autore and descrizione.startswith(DESCRIZIONI_AUTOMATICHE))


def definizione_automatica(stato: Any, avanzamento: Iterable[Any]) -> Any | None:
    """La voce automatica che ha portato il fascicolo a DEFINITO, se nessuna persona ha toccato lo stato dopo."""
    if _testo(stato).upper().rsplit(".", 1)[-1] != "DEFINITO":
        return None
    voci = list(avanzamento or [])
    for indice in range(len(voci) - 1, -1, -1):
        voce = voci[indice]
        if _campo(voce, "stato_nuovo").upper() == "DEFINITO" and _campo(voce, "stato_precedente").upper() != "DEFINITO":
            successive = voci[indice + 1:]
            umane = [v for v in successive if not e_automatica(v) and (
                _campo(v, "stato_nuovo") != _campo(v, "stato_precedente") or "stato" in _campo(v, "descrizione").casefold())]
            return voce if e_automatica(voce) and not umane else None
    return None


def fonte_citata(note: str) -> dict[str, str]:
    """Il documento indicato dalla voce: «Documento: docai-…» o «…pdf», oppure l'impronta SHA-256."""
    note = _testo(note)
    trovato, sha = _DOCUMENTO.search(note), _SHA.search(note)
    return {"documento": trovato.group("id").strip() if trovato else "", "sha256": sha.group("sha").lower() if sha else ""}


@dataclass
class Verifica:
    revoca: bool
    motivo: str = ""
    prova: dict[str, Any] = field(default_factory=dict)
    norme: tuple[str, ...] = NORME


def _udienze_successive(modello: Mapping[str, Any], dopo: str, atti: dict[str, Mapping[str, Any]], *,
                        provvedimento_dopo: str = "", oggi: str = "") -> list[tuple[str, Mapping[str, Any]]]:
    """Le udienze della causa successive a ``dopo``, fissate da un provvedimento posteriore a ``provvedimento_dopo``
    (se dato) o comunque ancora future rispetto a ``oggi`` (se dato)."""
    esito = []
    for udienza in modello.get("udienze") or []:
        data = _testo(udienza.get("data"))[:10]
        fonte = (udienza.get("fonte") or {}).get("oggetto_id") or ""
        atto = atti.get(_testo(fonte)) or {}
        if not data or not dopo or data <= dopo[:10] or atto.get("appartenenza") != "causa":
            continue
        if _CORREZIONE.search(f"{_testo(atto.get('etichetta'))} {_testo(atto.get('nome'))}"):
            continue
        data_atto = _testo(atto.get("data"))[:10]
        if provvedimento_dopo and not (data_atto and data_atto > provvedimento_dopo[:10]):
            continue  # un'udienza fissata prima della sentenza è assorbita dalla decisione
        if oggi and data <= oggi[:10] and not (data_atto and data_atto > dopo[:10]):
            continue  # udienza già passata, fissata prima della definizione: senza la sentenza non si sa come è finita
        esito.append((data, atto))
    return sorted(esito, key=lambda voce: voce[0])


def verifica_definizione(modello: Mapping[str, Any], voce: Any, citati: Iterable[str] = ()) -> Verifica:
    """La definizione automatica regge sul modello della causa? ``citati``: gli id degli atti indicati dalla voce."""
    atti = {_testo(a.get("id")): a for a in modello.get("atti") or []}
    sentenze = sorted(((_testo(a.get("data"))[:10], a) for a in atti.values()
                       if a.get("sentenza") and a.get("appartenenza") == "causa" and _testo(a.get("data"))),
                      key=lambda voce: voce[0])
    citati = [atti[c] for c in citati if c in atti]
    definita_il = _campo(voce, "data")[:10]
    if sentenze:
        data_sentenza, sentenza = sentenze[-1]
        if any(_CORREZIONE.search(f"{_testo(a.get('etichetta'))} {_testo(a.get('nome'))}") and _testo(a.get("data"))[:10] >= data_sentenza
               and a.get("appartenenza") == "causa" for a in atti.values()):
            # Dopo la sentenza c'è il procedimento di correzione (artt. 287-288 c.p.c.): le sue udienze non riaprono la causa.
            return Verifica(False, "Dopo la sentenza c'è solo il procedimento di correzione dell'errore materiale: la causa resta definita.")
        udienze = _udienze_successive(modello, data_sentenza, atti, provvedimento_dopo=data_sentenza)
        if not udienze:
            return Verifica(False, "La sentenza della causa definisce il giudizio e nessuna udienza è fissata dopo.")
        data, atto = udienze[-1]
        return Verifica(True, (
            f"Dopo la sentenza «{_testo(sentenza.get('nome'))}» del {_data_it(data_sentenza)} il giudice ha fissato l'udienza "
            f"del {_data_it(data)} con «{_testo(atto.get('nome'))}»"
            + (f" del {_data_it(_testo(atto.get('data')))}" if atto.get("data") else "")
            + ": la causa è pendente e la sentenza non l'ha definita (art. 279, secondo comma, c.p.c.)."),
            {"sentenza_id": _testo(sentenza.get("id")), "udienza": data, "provvedimento_id": _testo(atto.get("id"))})
    contorno = [a for a in citati if a.get("appartenenza") == "contorno"]
    if contorno and len(contorno) == len(citati):
        atto = contorno[0]
        motivo = _testo(atto.get("motivo_appartenenza")) or "non è un atto di questa causa"
        return Verifica(True, (
            f"Il documento indicato come sentenza, «{_testo(atto.get('nome'))}», non è un atto di questa causa: {motivo} "
            "Un precedente prodotto con gli atti non definisce il giudizio (art. 115 c.p.c.) e nel fascicolo non c'è la "
            "sentenza del procedimento."), {"documento_id": _testo(atto.get("id"))})
    note = _campo(voce, "note")
    sentenza_citata, ruolo = _SENTENZA_CITATA.search(note), _RG_CITATO.search(note)
    if sentenza_citata and ruolo and int(sentenza_citata.group("anno")) < int(ruolo.group("anno")):
        # Stessa regola di pct/atto_della_causa: una sentenza dell'anno prima dell'iscrizione a ruolo non decide la causa.
        return Verifica(True, (
            f"La voce cita la sentenza n. {sentenza_citata.group('numero')}/{sentenza_citata.group('anno')}, anteriore "
            f"all'iscrizione a ruolo della causa (RG {ruolo.group('numero')}/{ruolo.group('anno')}): non può averla decisa ed è "
            "un precedente prodotto (art. 115 c.p.c.); nel fascicolo non c'è la sentenza del procedimento."),
            {"sentenza_citata": sentenza_citata.group(0)})
    udienze = _udienze_successive(modello, definita_il, atti, oggi=_testo(modello.get("oggi")))
    if udienze:
        data, atto = udienze[-1]
        return Verifica(True, (
            f"Nel fascicolo non c'è la sentenza del procedimento e il giudice della causa ha fissato l'udienza del "
            f"{_data_it(data)} con «{_testo(atto.get('nome'))}»"
            + (f" del {_data_it(_testo(atto.get('data')))}" if atto.get("data") else "")
            + ": la causa è pendente."), {"udienza": data, "provvedimento_id": _testo(atto.get("id"))})
    return Verifica(False, "Nessuna prova contraria alla definizione nel modello della causa: resta com'è.")


def nota_riconvalida(verifica: Verifica, voce: Any) -> str:
    return (f"{verifica.motivo} La definizione automatica del {_data_it(_campo(voce, 'data'))} («{_campo(voce, 'descrizione')}», "
            f"{_campo(voce, 'avvocato')}) è stata annullata: lo stato torna «in corso». Norme: {'; '.join(verifica.norme)}. "
            f"Regola {VERSIONE}.")


__all__ = ["AUTORE", "AUTORI_AUTOMATICI", "NORME", "VERSIONE", "Verifica", "definizione_automatica", "e_automatica",
           "fonte_citata", "nota_riconvalida", "verifica_definizione"]
