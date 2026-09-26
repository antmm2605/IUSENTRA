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
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

# v2 (collaudo sulle 30 pagine anonimizzate): il valore si confronta per tipo.
# Una data scritta «18 luglio 2026», un importo «1375» o «EUR 259.00», un numero
# «n. 812/2026» o «812 del 2026» sono gli stessi valori della pagina e passano;
# con la v1 il 37% dei valori veri riscritti così dal modello veniva bloccato.
VERSIONE_CANCELLO = "2026.09.26.cancello-ancoraggio.v2"
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
    for giorno, mese, anno in _DATA_IN_LETTERE.findall(testo):
        iso = _giorno(int(anno), _MESI[mese.casefold()], int(giorno))
        if iso:
            trovate.add(iso)
    try:
        from legal_ocr.formulario.date import trova_date

        trovate.update(voce.data.isoformat() for voce in trova_date(testo))
    except Exception:  # pragma: no cover - il formulario resta facoltativo per il cancello
        pass
    return trovate


_NESSUN_VALORE = frozenset({"n d", "nd", "n a", "na", "n c", "non disponibile", "non indicato", "non indicata", "nessuno", "nessuna", "null", "none", "vuoto"})
_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATA_IN_LETTERE = re.compile(r"\b(\d{1,2})(?:°|º)?\s+(" + "|".join(_MESI) + r")\s+(\d{4})\b", re.IGNORECASE)
# Etichette che il modello mette davanti a un numero: «n.», «R.G. n.», «prot.», «EUR», «€».
_ETICHETTA_NUMERO = re.compile(
    r"^\s*(?:(?:r\.?\s*g\.?|n\.?\s*r\.?\s*g\.?|nrg|prot(?:ocollo)?\.?|cron\.?|rep\.?|n(?:r|um)?\.?|numero|nr|€|eur|euro)\s*[:.]?\s*)+",
    re.IGNORECASE,
)
_IMPORTO = re.compile(r"^\s*(?:€|eur|euro)?\s*-?\s*(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:€|eur|euro)?\s*$", re.IGNORECASE)


def _giorno(anno: int, mese: int, giorno: int) -> str:
    try:
        return date(anno if anno >= 100 else 2000 + anno, mese, giorno).isoformat()
    except ValueError:
        return ""


def data_proposta(valore: str) -> str:
    """La data di calendario di un valore proposto, in qualunque forma scritta (o stringa vuota)."""
    testo = " ".join(str(valore or "").split())
    iso = _data_iso(testo)
    if iso:
        return iso
    trovata = re.fullmatch(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})(?:\s*(?:,|ore|h\.?)?\s*\d{1,2}[:.]\d{2}(?::\d{2})?)?", testo, re.IGNORECASE)
    if trovata:
        return _giorno(int(trovata.group(3)), int(trovata.group(2)), int(trovata.group(1)))
    trovata = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[t ]\d{1,2}:\d{2}(?::\d{2})?)?", testo, re.IGNORECASE)
    if trovata:
        return _giorno(int(trovata.group(1)), int(trovata.group(2)), int(trovata.group(3)))
    trovata = re.fullmatch(r"(?:(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica),?\s+)?" + _DATA_IN_LETTERE.pattern[2:-2], testo, re.IGNORECASE)
    if trovata:
        return _giorno(int(trovata.group(3)), _MESI[trovata.group(2).casefold()], int(trovata.group(1)))
    return ""


def _centesimi(grezzo: str) -> int | None:
    """«1.234,56» → 123456; «1234.5» → 123450; «12.450» → 1245000 (il punto delle migliaia)."""
    testo = re.sub(r"\s", "", str(grezzo or "")).lstrip("-")
    if not re.fullmatch(r"[\d.,]+", testo) or not re.search(r"\d", testo):
        return None
    if "," in testo and "." in testo:
        testo = testo.replace(".", "").replace(",", ".") if testo.rfind(",") > testo.rfind(".") else testo.replace(",", "")
    elif "," in testo:
        interi, _, decimali = testo.rpartition(",")
        if len(decimali) not in {1, 2} or "," in interi:
            return None
        testo = f"{interi}.{decimali}"
    elif "." in testo:
        interi, _, decimali = testo.rpartition(".")
        testo = testo.replace(".", "") if len(decimali) == 3 else f"{interi.replace('.', '')}.{decimali}" if len(decimali) in {1, 2} else None
        if testo is None:
            return None
    try:
        return int((Decimal(testo) * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None


def importo_proposto(valore: str) -> int | None:
    """L'importo in centesimi di un valore proposto come somma di denaro (o None)."""
    trovato = _IMPORTO.match(str(valore or ""))
    if not trovato or not re.search(r"€|eur|[.,]\d{1,2}\s*(?:€|eur|euro)?\s*$", str(valore or ""), re.IGNORECASE):
        return None
    return _centesimi(trovato.group(1))


def _importi_del_testo(testo: str) -> set[int]:
    """Solo i numeri scritti come somme: «1.234,56», «259,00», «€ 800», «540 euro».

    Un numero di ruolo o un anno («1234/2026») non è un importo: un «€ 1.234,00»
    inventato non deve trovarvi un'ancora.
    """
    grezzo = str(testo or "")
    importi: set[int] = set()
    forme = (
        r"(?<![\d/])(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)(?![\d/])",
        r"(?<![\d/.])(\d+,\d{1,2})(?![\d/])",
        r"(?:€|\beur(?:o)?\b)\s*(\d+(?:[.,]\d{1,2})?)(?![\d/])",
        r"(?<![\d/.,])(\d+(?:[.,]\d{1,2})?)\s*(?:€|\beur(?:o)?\b)",
    )
    for forma in forme:
        for token in re.findall(forma, grezzo, re.IGNORECASE):
            centesimi = _centesimi(token)
            if centesimi is not None:
                importi.add(centesimi)
    return importi


def _numeri_del_testo(testo: str) -> set[str]:
    """Ogni numero del testo, uno per uno, più due forme equivalenti che i modelli riscrivono.

    - «n. 812 del 2026» / «numero 812 del 2026» → anche «812/2026» (cifre 8122026);
    - un codice scritto a gruppi («3012 3456 7890 1234 56») → anche le cifre unite.
    Due numeri vicini qualsiasi non si uniscono mai: «342» non nasce da «1234/2026».
    """
    grezzo = str(testo or "")
    numeri = {_cifre(token) for token in re.findall(r"\d[\d.,/]*\d|\d", grezzo)}
    for numero, anno in re.findall(r"\b(\d{1,7})\s+del\s+((?:19|20)\d{2})\b", grezzo, re.IGNORECASE):
        numeri.add(numero + anno)
    for gruppo in re.findall(r"(?<![\d.,/])(\d{2,5}(?: \d{2,5}){2,})(?![\d.,/])", grezzo):
        numeri.add(_cifre(gruppo))
    return numeri


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
    numeri_testo = _numeri_del_testo(testo)
    date_testo: set[str] | None = None
    importi_testo: set[int] | None = None
    controlli: list[Controllo] = []
    for campo, grezzo in parametri.items():
        valore = " ".join(str(grezzo or "").split())
        if not valore or _semplice(valore) in _NESSUN_VALORE:
            # «n.d.», «N/A», «non indicato»: il modello dice che il valore non c'è.
            continue
        if _semplice(valore) in registri.get(campo, set()):
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO, "presente nel registro ufficiale"))
            continue
        iso = data_proposta(valore)
        if iso:
            date_testo = date_testo if date_testo is not None else _date_del_testo(testo)
            ok = iso in date_testo
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                       "data presente nel testo" if ok else "data non presente nel testo della fonte"))
            continue
        centesimi = importo_proposto(valore)
        if centesimi is not None:
            importi_testo = importi_testo if importi_testo is not None else _importi_del_testo(testo)
            ok = centesimi in importi_testo
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                       "importo presente nel testo" if ok else "importo non riconducibile al testo della fonte"))
            continue
        spoglio = _ETICHETTA_NUMERO.sub("", valore)
        if spoglio != valore and re.fullmatch(r"[\d.,\s/]+", spoglio or "") or _NUMERO.match(valore):
            cifre = _cifre(spoglio if spoglio != valore else valore)
            if not (ok := bool(cifre) and cifre in numeri_testo):
                # «1375» o «12450» per «1.375,00» / «12.450,00»: lo stesso importo senza decimali.
                importi_testo = importi_testo if importi_testo is not None else _importi_del_testo(testo)
                intero = re.fullmatch(r"\d{1,9}", spoglio.strip() if spoglio != valore else valore.strip())
                ok = bool(intero) and int(intero.group(0)) * 100 in importi_testo
            controlli.append(Controllo(campo, valore, ESITO_AMMESSO if ok else ESITO_BLOCCATO,
                                       "numero presente nel testo" if ok else "numero non riconducibile al testo della fonte"))
            continue
        # Parole intere: «n d» non si ancora dentro «in data».
        ok = f" {_semplice(valore)} " in f" {testo_semplice} "
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
    "cancello_ancoraggio", "data_proposta", "importo_proposto", "impronta", "verifica_sigillo",
]
