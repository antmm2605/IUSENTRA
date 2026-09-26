"""Provenienza delle uscite AI e cancello deterministico prima di ogni azione.

Due regole, valide per ogni punto in cui un modello propone qualcosa che il
gestionale poi usa (voce del catalogo, profilo di una PEC, bozza di un atto):

1. **Provenienza**: ogni uscita porta con sé modello, versione delle regole,
   impronta SHA-256 del testo letto, citazione, parametri estratti, esito del
   cancello, chi l'ha approvata e quando. L'impronta del record (sigillo)
   rende riconoscibile ogni modifica successiva (art. 20 CAD, integrità del
   documento informatico; art. 12 e art. 13 Reg. UE 2024/1689 sulla
   registrazione e la trasparenza dei sistemi di AI).
2. **Cancello di ancoraggio**: il modello propone, le regole decidono. Un
   numero, una data, un nome o un codice proposti dal modello passano solo se
   si trovano nel testo della fonte o in un registro ufficiale (uffici
   giudiziari, anagrafica del fascicolo). Un valore senza ancora non diventa
   mai un'azione: resta una proposta da verificare (art. 14 Reg. UE
   2024/1689, sorveglianza umana).

Lo spunto viene dalle rassegne del 25-26/09/2026: la tracciabilità della
provenienza (registro ICC), la separazione fra proposta probabilistica e
modifica deterministica (TX Text Control) e il blocco dei valori numerici non
riconducibili alla pagina (valutazione per stadi, Reducto).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

VERSIONE_CANCELLO = "2026.09.26.cancello-ancoraggio.v1"
ESITO_AMMESSO = "ammesso"
ESITO_BLOCCATO = "bloccato"

_DATA = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$|^\s*(\d{4})-(\d{2})-(\d{2})\s*$")
_NUMERO = re.compile(r"^[\s€]*[\d.,\s/]+$")


def impronta(testo: Any) -> str:
    return hashlib.sha256(str(testo or "").encode("utf-8")).hexdigest()


def _semplice(testo: Any) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", base).split())


def _cifre(testo: str) -> str:
    return re.sub(r"\D", "", testo)


def _date_del_testo(testo: str) -> set[str]:
    trovate: set[str] = set()
    for giorno, mese, anno in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", testo):
        anno = anno if len(anno) == 4 else f"20{anno}"
        trovate.add(f"{int(anno):04d}-{int(mese):02d}-{int(giorno):02d}")
    for anno, mese, giorno in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", testo):
        trovate.add(f"{anno}-{mese}-{giorno}")
    try:
        from legal_ocr.formulario.date import trova_date

        trovate.update(voce.data.isoformat() for voce in trova_date(testo))
    except Exception:  # pragma: no cover - il formulario resta facoltativo per il cancello
        pass
    return trovate


def _data_iso(valore: str) -> str:
    corrispondenza = _DATA.match(valore)
    if not corrispondenza:
        return ""
    if corrispondenza.group(4):
        return f"{corrispondenza.group(4)}-{corrispondenza.group(5)}-{corrispondenza.group(6)}"
    giorno, mese, anno = corrispondenza.group(1), corrispondenza.group(2), corrispondenza.group(3)
    anno = anno if len(anno) == 4 else f"20{anno}"
    return f"{int(anno):04d}-{int(mese):02d}-{int(giorno):02d}"


@dataclass(frozen=True)
class Controllo:
    campo: str
    valore: str
    esito: str
    motivo: str


@dataclass(frozen=True)
class EsitoCancello:
    ammesso: bool
    controlli: tuple[Controllo, ...]
    versione: str = VERSIONE_CANCELLO

    @property
    def bloccati(self) -> list[Controllo]:
        return [c for c in self.controlli if c.esito == ESITO_BLOCCATO]

    def to_dict(self) -> dict[str, Any]:
        return {"ammesso": self.ammesso, "versione": self.versione, "controlli": [asdict(c) for c in self.controlli]}


def cancello_ancoraggio(parametri: dict[str, Any], testo: str, *, registri: dict[str, Iterable[str]] | None = None) -> EsitoCancello:
    """Ogni valore proposto passa solo se ancorato al testo o a un registro.

    - date: la stessa data di calendario deve comparire nel testo (in qualsiasi forma);
    - numeri e importi: la stessa sequenza di cifre deve comparire nel testo;
    - nomi, codici, citazioni: il testo normalizzato deve contenerli, oppure il
      registro indicato per quel campo (`registri[campo]`) deve contenerli.
    """
    registri = {campo: {_semplice(v) for v in valori} for campo, valori in (registri or {}).items()}
    testo_semplice = _semplice(testo)
    # I numeri del testo, uno per uno: «1.234,56», «1234/2026». Confrontare con
    # la sequenza di tutte le cifre del testo farebbe passare numeri inventati
    # che compaiono per caso a cavallo di due numeri veri.
    numeri_testo = {_cifre(token) for token in re.findall(r"\d[\d.,/]*\d|\d", str(testo or ""))}
    date_testo: set[str] | None = None
    controlli: list[Controllo] = []
    for campo, grezzo in parametri.items():
        valore = " ".join(str(grezzo or "").split())
        if not valore:
            continue
        if _semplice(valore) in registri.get(campo, set()):
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO, "presente nel registro ufficiale"))
            continue
        iso = _data_iso(valore)
        if iso:
            date_testo = date_testo if date_testo is not None else _date_del_testo(testo)
            ok = iso in date_testo
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                       "data presente nel testo" if ok else "data non presente nel testo della fonte"))
            continue
        if _NUMERO.match(valore):
            cifre = _cifre(valore)
            ok = bool(cifre) and cifre in numeri_testo
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                       "numero presente nel testo" if ok else "numero non riconducibile al testo della fonte"))
            continue
        ok = _semplice(valore) in testo_semplice
        controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                   "valore presente nel testo" if ok else "valore non presente nel testo né nei registri"))
    return EsitoCancello(ammesso=all(c.esito == ESITO_AMMESSO for c in controlli), controlli=tuple(controlli))


@dataclass
class Provenienza:
    """Chi ha prodotto l'uscita, da quale testo, con quali verifiche."""

    azione: str  # es. catalogo.seconda_lettura, pec.profilo, editor.bozza
    modello: str
    versione_regole: str
    sha256_input: str
    citazione: str = ""
    parametri: dict[str, Any] = field(default_factory=dict)
    cancello: dict[str, Any] = field(default_factory=dict)
    approvazione: str = "da_approvare"  # da_approvare | automatica | avvocato:<utente>
    creato_il: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    precedente: str = ""  # sigillo della provenienza precedente dello stesso oggetto

    def sigillo(self) -> str:
        dati = {chiave: valore for chiave, valore in asdict(self).items()}
        return hashlib.sha256(json.dumps(dati, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "sigillo": self.sigillo()}


def verifica_sigillo(dati: dict[str, Any]) -> bool:
    """Il record di provenienza non è stato modificato dopo la registrazione."""
    campi = {chiave: valore for chiave, valore in dict(dati or {}).items() if chiave != "sigillo"}
    try:
        return Provenienza(**campi).sigillo() == str(dati.get("sigillo") or "")
    except TypeError:
        return False


__all__ = [
    "ESITO_AMMESSO", "ESITO_BLOCCATO", "VERSIONE_CANCELLO", "Controllo", "EsitoCancello", "Provenienza",
    "cancello_ancoraggio", "impronta", "verifica_sigillo",
]
