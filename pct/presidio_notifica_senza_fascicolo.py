"""PEC con ordine di notifica ma senza fascicolo collegato: proposta in BOZZA da lavorare.

Il presidio delle notifiche L. 53/1994 nasce solo su un fascicolo: senza collegamento non si crea
un presidio orfano. Fino al 09/11/2026 la PEC veniva però scartata in silenzio («fascicolo non
collegato, presidio non creato») e l'avvocato non vedeva l'ordine del giudice.

Si usa il meccanismo già esistente delle proposte di scadenza in BOZZA (come
``pct/scadenze_proposte_pec``): la proposta compare nella coda «Proposte» dello scadenziario anche
senza fascicolo, non entra in agenda, notifiche o conteggi operativi e l'avvocato la conferma o la
scarta. Quando la PEC viene collegata il presidio si rimaterializza e la proposta si chiude da sola.

Base normativa: L. 53/1994, art. 3-bis (notifica a mezzo PEC dell'avvocato); art. 415, commi 4-5,
c.p.c. (ricorso e decreto notificati a cura dell'attore entro dieci giorni dalla pronuncia del
decreto); art. 435, commi 2-3, c.p.c. (appello: dieci giorni dal deposito del decreto, decorrenti
dalla comunicazione secondo Corte cost. 15/1977); art. 281-undecies c.p.c. (procedimento
semplificato). La data della proposta è solo un promemoria di verifica a dieci giorni dalla
ricezione della PEC (anticipato all'ultimo giorno lavorativo se cade di sabato o festivo: non è un
termine, quindi non si proroga in avanti come vorrebbe l'art. 155 c.p.c.), non un termine di legge: il termine effettivo si legge nel provvedimento e si
calcola nel presidio dopo il collegamento. Nessun invio automatico.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from pct.ora_italiana import giorno_italiano, oggi_roma

MARCATORE = "PROPOSTA_NOTIFICA_SENZA_FASCICOLO"
PROFILO = "PEC_PROPOSTA_NOTIFICA"
GIORNI_VERIFICA = 10
_RG_RE = re.compile(r"\b(\d{1,7})/(\d{4})(?:/[A-Z]{2,5})?\b", re.I)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit].strip()


def marcatore(message_id: str) -> str:
    return f"{MARCATORE}:{_clean(message_id, 160)}"


def numero_ruolo(understanding: dict[str, Any], subject: str = "") -> str:
    """RG letto dal JSON V2 o, in mancanza, dall'oggetto della PEC di cancelleria."""

    procedimento = understanding.get("procedimento") if isinstance(understanding.get("procedimento"), dict) else {}
    numero = _clean(procedimento.get("rg_numero"), 12)
    anno = _clean(procedimento.get("rg_anno"), 4)
    if numero and anno:
        return f"{numero}/{anno}"
    oggetto = subject or _clean((understanding.get("message") or {}).get("subject_normalized"), 240)
    from legal_ocr.formulario.riferimenti_normativi import atto_normativo_prima

    for trovato in _RG_RE.finditer(oggetto or ""):
        # «L. 53/1994» nell'oggetto è la legge sulle notifiche in proprio, non il ruolo della causa.
        if not atto_normativo_prima(oggetto, trovato.start(1)):
            return f"{trovato.group(1)}/{trovato.group(2)}"
    return ""


def data_promemoria(ricevuta: date, *, oggi: date | None = None) -> date:
    """Il giorno del promemoria: dieci giorni dalla ricezione, anticipato all'ultimo giorno lavorativo.

    Il promemoria non è un termine di legge, quindi non si applica la proroga dell'art. 155, commi 4-5,
    c.p.c. (che sposta in avanti, a favore della parte, il termine che scade di sabato o di festivo).
    Serve a far verificare il termine vero, che decorre dalla pronuncia o dal deposito del decreto
    (artt. 415, comma 4, e 435, comma 2, c.p.c.) e quindi può scadere prima: un promemoria che cade di
    sabato, domenica o festivo si anticipa all'ultimo giorno lavorativo precedente, mai a prima di oggi.
    """

    from pct.scadenziario import è_giorno_lavorativo

    limite = oggi or oggi_roma()
    giorno = ricevuta + timedelta(days=GIORNI_VERIFICA)
    while giorno > limite and not è_giorno_lavorativo(giorno, sospensione_feriale=False):
        giorno -= timedelta(days=1)
    return max(giorno, limite)


def campi_proposta(
    *,
    message_id: str,
    understanding: dict[str, Any],
    candidate: dict[str, Any],
    received_at: str,
    oggi: date | None = None,
) -> dict[str, Any] | None:
    """Campi per ``GestioneScadenziario.nuova``; ``None`` se la verifica sarebbe già decorsa."""

    try:
        ricevuta = date.fromisoformat(giorno_italiano(received_at)[:10])
    except ValueError:
        ricevuta = oggi or oggi_roma()
    if ricevuta + timedelta(days=GIORNI_VERIFICA) < (oggi or oggi_roma()):
        return None
    verifica = data_promemoria(ricevuta, oggi=oggi)
    rg = numero_ruolo(understanding)
    procedimento = understanding.get("procedimento") if isinstance(understanding.get("procedimento"), dict) else {}
    ufficio = _clean(procedimento.get("ufficio"), 120)
    riferimento = " ".join(part for part in (f"RG {rg}" if rg else "", ufficio) if part) or "della PEC"
    estratto = _clean(candidate.get("text_excerpt"), 360)
    return {
        "titolo": f"PEC con ordine di notifica: crea o collega il fascicolo {riferimento}"[:180],
        "data_scadenza": verifica.isoformat(),
        "descrizione": (
            "Il provvedimento ricevuto via PEC ordina al difensore di notificare (L. 53/1994, art. 3-bis; "
            "artt. 415, commi 4-5, 435 e 281-undecies c.p.c.), ma la PEC non è collegata a un fascicolo: "
            "il presidio della notifica non è stato aperto. Creare o collegare il fascicolo dalla PEC; "
            "il presidio nasce al collegamento. La data è un promemoria di verifica a dieci giorni dalla "
            "ricezione (anticipato all'ultimo giorno lavorativo se cade di sabato o festivo), non il termine "
            "di legge, che si legge nel provvedimento."
        ),
        "note": "\n".join(
            (
                marcatore(message_id),
                f"Regola: {_clean(candidate.get('rule_id'), 80) or '-'} ({_clean(candidate.get('rulepack_version'), 60) or '-'})",
                f"Ricevuta il: {ricevuta.strftime('%d/%m/%Y')}",
                "Proposta in bozza: revisione dell'avvocato obbligatoria, nessun invio automatico.",
            )
        ),
        "id_fascicolo": "",
        "source_event_type": "legal_notification_order_unlinked",
        "source_event_at": _clean(received_at, 40),
        "deadline_profile_code": PROFILO,
        "source_snippet": estratto,
        "source_snippet_label": "Ordine di notifica",
        "source_document_name": _clean(candidate.get("source_file"), 160) or "allegato PEC",
        "source_message_id": _clean(message_id, 160),
        "source_confidence": float(candidate.get("confidence") or 0.0),
    }


def proponi_collegamento(
    manager: Any,
    *,
    message_id: str,
    understanding: dict[str, Any],
    candidate: dict[str, Any],
    received_at: str,
    responsabile: str = "",
    oggi: date | None = None,
) -> dict[str, Any]:
    """Crea una sola proposta per PEC (idempotente sul marcatore, anche dopo conferma o scarto)."""

    from pct.scadenziario import StatoTermine, TipoTermine

    chiave = marcatore(message_id)
    for voce in manager.tutte(solo_aperte=False):
        if chiave in str(getattr(voce, "note", "") or ""):
            return {"created": False, "id": str(getattr(voce, "id", "")), "motivo": "proposta già registrata"}
    campi = campi_proposta(
        message_id=message_id, understanding=understanding, candidate=candidate, received_at=received_at, oggi=oggi,
    )
    if campi is None:
        return {"created": False, "id": "", "motivo": "verifica già decorsa: proposta non creata"}
    voce = manager.nuova(
        titolo=campi.pop("titolo"),
        tipo=TipoTermine.ADEMPIMENTO,
        data_scadenza=campi.pop("data_scadenza"),
        id_fascicolo=campi.pop("id_fascicolo"),
        descrizione=campi.pop("descrizione"),
        note=campi.pop("note"),
        id_utente_responsabile=responsabile,
        stato=StatoTermine.BOZZA,
        **campi,
    )
    return {"created": True, "id": str(getattr(voce, "id", "")), "motivo": "proposta creata"}


def chiudi_dopo_collegamento(manager: Any, *, message_id: str, fascicolo_id: str, attore: str = "") -> int:
    """Collegata la PEC e aperto il presidio, la proposta ha esaurito il suo scopo: si scarta con motivo."""

    from pct.scadenziario import StatoTermine

    chiave = marcatore(message_id)
    chiuse = 0
    for voce in list(manager.tutte(solo_aperte=False)):
        if getattr(voce, "stato", None) != StatoTermine.BOZZA or chiave not in str(getattr(voce, "note", "") or ""):
            continue
        manager.scarta_bozza(
            str(getattr(voce, "id", "")),
            motivo=f"PEC collegata al fascicolo {fascicolo_id}: presidio della notifica aperto.",
            attore=attore,
        )
        chiuse += 1
    return chiuse


_TITOLO_RG_RE = re.compile(r"\s*RG (\d{1,7}/\d{4})")
_RICEVUTA_RE = re.compile(r"^Ricevuta il: (\d{2})/(\d{2})/(\d{4})$", re.M)
RIGA_RICONVALIDA = "Riconvalida automatica"


def _rg_normativo(voce: Any) -> str:
    """Il riferimento normativo scambiato per RG nel titolo della proposta («RG 53/1994»), se c'è."""

    from legal_ocr.formulario.riferimenti_normativi import e_numero_di_atto_normativo

    trovato = _TITOLO_RG_RE.search(str(getattr(voce, "titolo", "") or ""))
    if not trovato:
        return ""
    numero = trovato.group(1)
    testo = " ".join(str(getattr(voce, campo, "") or "") for campo in ("source_snippet", "descrizione"))
    citazioni = [m for m in re.finditer(re.escape(numero) + r"(?!\d)", testo)]
    norme = [e_numero_di_atto_normativo(testo, m.start(), m.end()) for m in citazioni]
    # Solo se ogni comparsa del numero nella fonte è una citazione normativa: un vero R.G. resta.
    return norme[0] if norme and all(norme) else ""


def riconvalida_proposte(manager: Any, *, oggi: date | None = None) -> dict[str, Any]:
    """Le proposte in BOZZA già scritte ripassano le regole correnti; idempotente.

    - RG letto da un riferimento normativo («RG 53/1994» è la L. 53/1994): il numero si toglie dal
      titolo. La proposta resta aperta perché l'ordine di notifica c'è davvero; cambia solo
      l'identificazione della causa, che si ricava collegando la PEC al fascicolo.
    - Promemoria caduto di sabato, domenica o festivo: si anticipa all'ultimo giorno lavorativo
      (``data_promemoria``).
    Ogni rettifica lascia una riga «Riconvalida automatica» nelle note. Le proposte confermate,
    scartate o annullate dall'avvocato non si toccano.
    """

    from pct.scadenziario import StatoTermine

    oggi = oggi or oggi_roma()
    esito: dict[str, Any] = {"rg_normativi": 0, "date_anticipate": 0, "errori": 0, "ids": []}
    for voce in list(manager.tutte(solo_aperte=False)):
        if getattr(voce, "stato", None) != StatoTermine.BOZZA or str(getattr(voce, "deadline_profile_code", "") or "") != PROFILO:
            continue
        note = str(getattr(voce, "note", "") or "")
        campi: dict[str, Any] = {}
        righe: list[str] = []
        norma = _rg_normativo(voce)
        if norma:
            titolo = _TITOLO_RG_RE.sub("", str(voce.titolo), count=1).strip()
            if titolo.endswith("il fascicolo"):
                titolo = f"{titolo} della PEC"
            campi["titolo"] = titolo
            righe.append(f"{RIGA_RICONVALIDA} {oggi:%d/%m/%Y}: «{norma}» è un riferimento normativo, non il numero di ruolo; "
                         "RG tolto dal titolo, si ricava collegando la PEC al fascicolo.")
        ricevuta = _RICEVUTA_RE.search(note)
        if ricevuta:
            giorno = date(int(ricevuta.group(3)), int(ricevuta.group(2)), int(ricevuta.group(1)))
            attuale = str(getattr(voce, "data_scadenza", "") or "")[:10]
            if attuale == (giorno + timedelta(days=GIORNI_VERIFICA)).isoformat() and attuale >= oggi.isoformat():
                nuova = data_promemoria(giorno, oggi=oggi).isoformat()
                if nuova != attuale:
                    campi["data_scadenza"] = nuova
                    righe.append(f"{RIGA_RICONVALIDA} {oggi:%d/%m/%Y}: promemoria del {date.fromisoformat(attuale):%d/%m/%Y} "
                                 f"(giorno non lavorativo) anticipato al {date.fromisoformat(nuova):%d/%m/%Y}; non è un termine "
                                 "di legge, quindi non si proroga in avanti (art. 155 c.p.c.).")
        if not campi:
            continue
        try:
            manager.aggiorna(str(voce.id), note="\n".join([note, *righe]).strip(), **campi)
        except Exception:  # una proposta non aggiornabile non blocca le altre
            esito["errori"] += 1
            continue
        esito["rg_normativi"] += 1 if norma else 0
        esito["date_anticipate"] += 1 if "data_scadenza" in campi else 0
        esito["ids"].append(str(voce.id))
    esito["ids"] = esito["ids"][:50]
    return esito


__all__ = [
    "GIORNI_VERIFICA", "MARCATORE", "PROFILO", "campi_proposta", "chiudi_dopo_collegamento", "data_promemoria", "marcatore",
    "numero_ruolo", "proponi_collegamento", "riconvalida_proposte",
]
