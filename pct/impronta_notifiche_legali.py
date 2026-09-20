"""Semaforo del presidio notifiche legali: fermo finché non cambia nulla.

Il presidio `legal_notification_relata_presidio` esisteva come giro a
orologio: ogni quindici minuti rileggeva tutti i fascicoli dello studio
— `documenti_json` compreso — ricostruiva la relata di ciascuno,
risincronizzava le proiezioni per ogni destinatario e riallineava lo
scadenziario. Anche quando non era arrivata nessuna PEC e nessuno aveva
toccato un fascicolo. Con trecento fascicoli sono novantasei giri al
giorno di lavoro identico a vuoto.

Il presidio non ha motivo di cercare da solo: ha tre sorgenti, e tutte e
tre sanno dire in una riga se sono cambiate.

1. Le PEC che portano una notifica legale. Non tutte le PEC: solo quelle
   che il motore ha gia' riconosciuto come notifica e ha scritto in
   `pec_legal_notification_presidia`. Una PEC che non prevede una
   notifica legale non entra in quella tabella e quindi non sveglia
   niente, che e' esattamente il comportamento voluto.
2. Le PEC lavorate che non hanno trovato un fascicolo, che devono
   restare visibili allo studio.
3. I fascicoli: se l'avvocato archivia un fascicolo, cambia uno stato o
   allega un documento, la relata cambia anche senza che arrivi una PEC.
   Legare il presidio alla sola PEC lascerebbe la topbar e lo
   scadenziario indietro fino alla PEC successiva, e nessuno se ne
   accorgerebbe: e' un guasto silenzioso, e qui non se ne accettano.

L'impronta somma le tre sorgenti con conteggi e ultima modifica, senza
leggere i contenuti. Se coincide con quella dell'ultimo giro andato a
buon fine, il presidio esce subito.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NOME_FILE_IMPRONTA = "presidio_notifiche_impronta.json"
VERSIONE_IMPRONTA = "2026.09.20.v1"


def _testo(valore: Any) -> str:
    return " ".join(str(valore if valore is not None else "").split()).strip()


def _adesso_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Impronta:
    """Lo stato delle tre sorgenti, ridotto a poche righe confrontabili."""

    pec_notifiche: str = ""
    pec_senza_fascicolo: str = ""
    fascicoli: str = ""
    destinatari: str = ""

    def chiave(self) -> str:
        grezzo = "|".join(
            (
                VERSIONE_IMPRONTA,
                self.pec_notifiche,
                self.pec_senza_fascicolo,
                self.fascicoli,
                self.destinatari,
            )
        )
        return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()

    def completa(self) -> bool:
        """Falso quando una sorgente non si e' lasciata interrogare.

        Un'impronta parziale non deve mai fermare il presidio: meglio un
        giro di troppo che una notifica che non arriva.
        """

        return all(
            _testo(parte)
            for parte in (self.pec_notifiche, self.pec_senza_fascicolo, self.fascicoli, self.destinatari)
        )

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "versione": VERSIONE_IMPRONTA,
            "chiave": self.chiave(),
            "pec_notifiche": self.pec_notifiche,
            "pec_senza_fascicolo": self.pec_senza_fascicolo,
            "fascicoli": self.fascicoli,
            "destinatari": self.destinatari,
        }

    @classmethod
    def dal_dizionario(cls, dati: Any) -> "Impronta":
        if not isinstance(dati, dict) or _testo(dati.get("versione")) != VERSIONE_IMPRONTA:
            return cls()
        return cls(
            pec_notifiche=_testo(dati.get("pec_notifiche")),
            pec_senza_fascicolo=_testo(dati.get("pec_senza_fascicolo")),
            fascicoli=_testo(dati.get("fascicoli")),
            destinatari=_testo(dati.get("destinatari")),
        )


def componi(*valori: Any) -> str:
    """Riduce il risultato di una interrogazione a una riga confrontabile."""

    return "|".join(_testo(valore) for valore in valori)


def percorso_impronta(cartella: Any) -> Path:
    return Path(str(cartella)) / NOME_FILE_IMPRONTA


def leggi_impronta(cartella: Any) -> tuple[Impronta, dict[str, Any]]:
    percorso = percorso_impronta(cartella)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except Exception:
        return Impronta(), {}
    if not isinstance(dati, dict):
        return Impronta(), {}
    return Impronta.dal_dizionario(dati.get("impronta")), dati


def scrivi_impronta(cartella: Any, impronta: Impronta, *, esito: dict[str, Any] | None = None) -> bool:
    """Registra l'impronta dell'ultimo giro riuscito. Non solleva mai."""

    percorso = percorso_impronta(cartella)
    dati = {
        "versione": VERSIONE_IMPRONTA,
        "aggiornato": _adesso_iso(),
        "impronta": impronta.come_dizionario(),
        "ultimo_giro": esito or {},
    }
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
        temporaneo.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaneo.replace(percorso)
        return True
    except Exception:
        return False


def riattiva_presidio(cartella: Any) -> None:
    """Toglie l'impronta: il prossimo giro rifa' il lavoro per intero.

    Da chiamare quando un evento reale rende la proiezione sospetta e non
    si vuole aspettare che una delle tre sorgenti se ne accorga.
    """

    try:
        percorso_impronta(cartella).unlink(missing_ok=True)
    except Exception:
        pass


def si_puo_fermare(attuale: Impronta, salvata: Impronta) -> bool:
    """Vero solo se le tre sorgenti sono ferme e l'impronta e' attendibile."""

    if not attuale.completa() or not salvata.completa():
        return False
    return attuale.chiave() == salvata.chiave()


def esito_fermo(attuale: Impronta, precedente: dict[str, Any] | None = None) -> dict[str, Any]:
    """L'esito che il presidio restituisce quando non c'e' niente da fare.

    Dichiara perche' si e' fermato e quando aveva lavorato l'ultima volta:
    uno zero senza spiegazione sarebbe indistinguibile da un guasto.
    """

    dati = precedente or {}
    ultimo = dati.get("ultimo_giro") if isinstance(dati.get("ultimo_giro"), dict) else {}
    return {
        "ok": True,
        "stato": "fermo",
        "motivo": "nessuna PEC di notifica nuova e nessun fascicolo modificato dall'ultimo giro",
        "impronta": attuale.come_dizionario(),
        "ultimo_giro_utile": {
            "quando": _testo(dati.get("aggiornato")),
            "scanned": ultimo.get("scanned"),
            "items": ultimo.get("items"),
            "recipients": ultimo.get("recipients"),
        },
    }
