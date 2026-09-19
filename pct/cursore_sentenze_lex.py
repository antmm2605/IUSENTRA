"""Cursore durevole per la lettura automatica delle sentenze (Lex/economia).

Il giro automatico `lex_sentenza_economia_auto` legge i testi estratti dei
documenti e, quando riconosce una sentenza del fascicolo, ne alimenta la parte
economica e l'indice Lex. Senza un cursore proprio quel giro ricominciava da
capo ogni volta che un solo documento andava in errore: il segnaposto viveva
dentro l'esito dell'esecuzione e l'esecuzione con errori non veniva registrata
come completata, cosi' l'ultimo segnaposto valido restava indietro e il giro
successivo rifaceva la scansione integrale, riprovava gli stessi documenti
guasti e falliva di nuovo. Sei documenti illeggibili bastavano a tenere il
server occupato ogni dieci minuti.

Qui il segnaposto e' un file accanto all'archivio del tenant, scritto a ogni
giro anche quando il giro ha errori, e accanto al segnaposto vive l'elenco dei
documenti che non si sono lasciati leggere:

- il cursore avanza solo fino ai documenti letti **senza** errore;
- i documenti in errore restano in quarantena e vengono riprovati a ogni giro,
  cosi' l'avanzamento del cursore non li perde per strada;
- dopo `TENTATIVI_MASSIMI` tentativi il documento viene **sospeso**: non si
  riprova piu' da solo, ma resta dichiarato nell'esito perche' qualcuno lo
  guardi. Non si scarta nulla in silenzio.
- se il file cambia (mtime diverso da quello registrato) i tentativi
  ripartono: un documento rigenerato merita una lettura nuova.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

NOME_FILE_STATO = "sentenze_lex_cursore.json"
VERSIONE_STATO = "2026.09.20.v1"
TENTATIVI_MASSIMI = 5


def _adesso_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _intero(valore: Any) -> int:
    try:
        return max(0, int(valore))
    except (TypeError, ValueError):
        return 0


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


@dataclass
class DocumentoInErrore:
    """Un testo estratto che non si e' lasciato leggere."""

    tentativi: int = 0
    mtime_ns: int = 0
    errore: str = ""
    primo_errore: str = ""
    ultimo_errore: str = ""

    def sospeso(self, tentativi_massimi: int = TENTATIVI_MASSIMI) -> bool:
        return self.tentativi >= max(1, tentativi_massimi)

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "tentativi": int(self.tentativi),
            "mtime_ns": int(self.mtime_ns),
            "errore": self.errore,
            "primo_errore": self.primo_errore,
            "ultimo_errore": self.ultimo_errore,
        }

    @classmethod
    def dal_dizionario(cls, dati: Any) -> "DocumentoInErrore":
        if not isinstance(dati, dict):
            return cls()
        return cls(
            tentativi=_intero(dati.get("tentativi")),
            mtime_ns=_intero(dati.get("mtime_ns")),
            errore=_testo(dati.get("errore")),
            primo_errore=_testo(dati.get("primo_errore")),
            ultimo_errore=_testo(dati.get("ultimo_errore")),
        )


@dataclass
class StatoCursore:
    """Segnaposto del tenant: fin dove si e' letto e cosa e' rimasto indietro."""

    mtime_ns: int = 0
    percorso_piu_recente: str = ""
    aggiornato: str = ""
    in_errore: dict[str, DocumentoInErrore] = field(default_factory=dict)

    def sospesi(self, tentativi_massimi: int = TENTATIVI_MASSIMI) -> dict[str, DocumentoInErrore]:
        return {
            percorso: dato
            for percorso, dato in self.in_errore.items()
            if dato.sospeso(tentativi_massimi)
        }

    def da_riprovare(self, tentativi_massimi: int = TENTATIVI_MASSIMI) -> dict[str, DocumentoInErrore]:
        return {
            percorso: dato
            for percorso, dato in self.in_errore.items()
            if not dato.sospeso(tentativi_massimi)
        }

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "versione": VERSIONE_STATO,
            "mtime_ns": int(self.mtime_ns),
            "percorso_piu_recente": self.percorso_piu_recente,
            "aggiornato": self.aggiornato or _adesso_iso(),
            "in_errore": {
                percorso: dato.come_dizionario() for percorso, dato in sorted(self.in_errore.items())
            },
        }

    @classmethod
    def dal_dizionario(cls, dati: Any) -> "StatoCursore":
        if not isinstance(dati, dict):
            return cls()
        if _testo(dati.get("versione")) != VERSIONE_STATO:
            # Formato non riconosciuto: si riparte da zero, una sola volta.
            return cls()
        grezzi = dati.get("in_errore")
        in_errore: dict[str, DocumentoInErrore] = {}
        if isinstance(grezzi, dict):
            for percorso, dato in grezzi.items():
                chiave = _testo(percorso)
                if chiave:
                    in_errore[chiave] = DocumentoInErrore.dal_dizionario(dato)
        return cls(
            mtime_ns=_intero(dati.get("mtime_ns")),
            percorso_piu_recente=_testo(dati.get("percorso_piu_recente")),
            aggiornato=_testo(dati.get("aggiornato")),
            in_errore=in_errore,
        )


def percorso_stato(tenant_root: Path) -> Path:
    """Il segnaposto vive accanto all'archivio dei documenti del tenant."""

    return Path(tenant_root) / "fascicoli" / NOME_FILE_STATO


def leggi_stato(tenant_root: Path) -> StatoCursore:
    percorso = percorso_stato(tenant_root)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except Exception:
        return StatoCursore()
    return StatoCursore.dal_dizionario(dati)


def scrivi_stato(tenant_root: Path, stato: StatoCursore) -> bool:
    """Scrive il segnaposto in modo atomico. Non solleva: e' un'ottimizzazione."""

    percorso = percorso_stato(tenant_root)
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
        temporaneo.write_text(
            json.dumps(stato.come_dizionario(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporaneo.replace(percorso)
        return True
    except Exception:
        return False


def documenti_da_esaminare(
    percorsi: Iterable[Path],
    stato: StatoCursore,
    *,
    mtime_di: Any,
    tentativi_massimi: int = TENTATIVI_MASSIMI,
) -> tuple[list[Path], dict[str, Any]]:
    """Sceglie i documenti del giro: i nuovi piu' quelli rimasti in quarantena.

    `mtime_di` e' la funzione che legge l'mtime in nanosecondi di un percorso
    (iniettata per non legare questo modulo al filesystem nei test).
    """

    tutti = list(percorsi)
    soglia = int(stato.mtime_ns or 0)
    da_riprovare = stato.da_riprovare(tentativi_massimi)
    sospesi = stato.sospesi(tentativi_massimi)

    scelti: list[Path] = []
    nuovi = 0
    ripresi = 0
    saltati_dal_cursore = 0
    saltati_perche_sospesi = 0

    for percorso in tutti:
        chiave = str(percorso)
        mtime = _intero(mtime_di(percorso))
        registrato = stato.in_errore.get(chiave)
        if registrato is not None and registrato.mtime_ns and mtime != registrato.mtime_ns:
            # Il documento e' cambiato: merita una lettura nuova, non e' piu'
            # ne' in quarantena ne' sospeso.
            scelti.append(percorso)
            nuovi += 1
            continue
        if chiave in sospesi:
            saltati_perche_sospesi += 1
            continue
        if chiave in da_riprovare:
            scelti.append(percorso)
            ripresi += 1
            continue
        if soglia and mtime <= soglia:
            saltati_dal_cursore += 1
            continue
        scelti.append(percorso)
        nuovi += 1

    dettaglio = {
        "modalita": "incrementale" if soglia else "integrale",
        "cursore_mtime_ns": soglia,
        "documenti_catalogati": len(tutti),
        "documenti_scelti": len(scelti),
        "documenti_nuovi": nuovi,
        "documenti_ripresi": ripresi,
        "saltati_dal_cursore": saltati_dal_cursore,
        "saltati_perche_sospesi": saltati_perche_sospesi,
    }
    return scelti, dettaglio


def aggiorna_stato(
    stato: StatoCursore,
    *,
    letti_senza_errore: Iterable[Path],
    falliti: dict[str, str],
    mtime_di: Any,
    tentativi_massimi: int = TENTATIVI_MASSIMI,
) -> StatoCursore:
    """Avanza il cursore ai documenti letti bene e aggiorna la quarantena."""

    in_errore = dict(stato.in_errore)
    nuovo_mtime = int(stato.mtime_ns or 0)
    percorso_piu_recente = stato.percorso_piu_recente

    for percorso in letti_senza_errore:
        chiave = str(percorso)
        in_errore.pop(chiave, None)
        mtime = _intero(mtime_di(percorso))
        if mtime > nuovo_mtime:
            nuovo_mtime = mtime
            percorso_piu_recente = chiave

    for chiave, messaggio in (falliti or {}).items():
        chiave = str(chiave)
        precedente = in_errore.get(chiave)
        mtime = _intero(mtime_di(Path(chiave)))
        if precedente is None or (precedente.mtime_ns and precedente.mtime_ns != mtime):
            in_errore[chiave] = DocumentoInErrore(
                tentativi=1,
                mtime_ns=mtime,
                errore=_testo(messaggio),
                primo_errore=_adesso_iso(),
                ultimo_errore=_adesso_iso(),
            )
            continue
        precedente.tentativi = min(precedente.tentativi + 1, max(1, tentativi_massimi))
        precedente.mtime_ns = mtime or precedente.mtime_ns
        precedente.errore = _testo(messaggio) or precedente.errore
        precedente.ultimo_errore = _adesso_iso()
        in_errore[chiave] = precedente

    return StatoCursore(
        mtime_ns=nuovo_mtime,
        percorso_piu_recente=percorso_piu_recente,
        aggiornato=_adesso_iso(),
        in_errore=in_errore,
    )


def riepilogo(stato: StatoCursore, *, tentativi_massimi: int = TENTATIVI_MASSIMI) -> dict[str, Any]:
    """Quello che la console deve poter mostrare senza aprire il file."""

    sospesi = stato.sospesi(tentativi_massimi)
    return {
        "cursore_mtime_ns": int(stato.mtime_ns or 0),
        "aggiornato": stato.aggiornato,
        "in_quarantena": len(stato.da_riprovare(tentativi_massimi)),
        "sospesi": len(sospesi),
        "documenti_sospesi": [
            {
                "percorso": percorso,
                "tentativi": dato.tentativi,
                "errore": dato.errore,
                "primo_errore": dato.primo_errore,
                "ultimo_errore": dato.ultimo_errore,
            }
            for percorso, dato in sorted(sospesi.items())
        ],
    }
