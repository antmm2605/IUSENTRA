"""Il cancello di ancoraggio misurato stadio per stadio sulle trenta pagine.

Per ogni pagina un lettore (il modello locale, oppure il lettore simulato dei
test) propone i valori numerici che trova: date, importi, numeri. Ogni
proposta si giudica due volte, in modo indipendente:

1. **verità**: il valore, ridotto alla sua forma canonica (data ISO, importo in
   centesimi, numero in cifre), è uno dei valori veri della pagina?
2. **cancello**: `cancello_ancoraggio` lo ammette o lo blocca guardando solo il
   testo letto.

Ne escono le misure della rassegna Reducto:

- valori inventati che passano il cancello (obiettivo: zero);
- valori veri bloccati a torto, contati solo se il valore è davvero nel testo
  letto (obiettivo: meno del 2%); quelli guastati dal riconoscimento ottico si
  contano a parte, come errori di **lettura**;
- quanti valori veri il lettore trova (**estrazione**).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from .pagine_anonime import DATA, IMPORTO, NUMERO, PAGINE, Pagina, Valore

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def data_canonica(valore: Any) -> str:
    testo = str(valore or "").strip().casefold()
    trovata = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", testo)
    if trovata:
        anno, mese, giorno = int(trovata.group(1)), int(trovata.group(2)), int(trovata.group(3))
    else:
        trovata = re.search(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b", testo)
        if trovata:
            giorno, mese, anno = int(trovata.group(1)), int(trovata.group(2)), int(trovata.group(3))
        else:
            trovata = re.search(r"\b(\d{1,2})\s+(" + "|".join(_MESI) + r")\s+(\d{4})\b", testo)
            if not trovata:
                return ""
            giorno, mese, anno = int(trovata.group(1)), _MESI[trovata.group(2)], int(trovata.group(3))
    if anno < 100:
        anno += 2000
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return ""


def importo_canonico(valore: Any) -> str:
    testo = re.sub(r"[^\d.,-]", "", str(valore or "").replace(" ", ""))
    testo = testo.lstrip("-")
    if not re.search(r"\d", testo):
        return ""
    if "," in testo and "." in testo:
        # l'ultimo separatore è quello dei decimali
        if testo.rfind(",") > testo.rfind("."):
            testo = testo.replace(".", "").replace(",", ".")
        else:
            testo = testo.replace(",", "")
    elif "," in testo:
        interi, _, decimali = testo.rpartition(",")
        testo = f"{interi.replace(',', '')}.{decimali}" if len(decimali) in {1, 2} else testo.replace(",", "")
    elif testo.count(".") == 1 and len(testo.rpartition(".")[2]) == 3:
        testo = testo.replace(".", "")  # «1.250» è milleduecentocinquanta
    elif testo.count(".") > 1:
        interi, _, decimali = testo.rpartition(".")
        testo = f"{interi.replace('.', '')}.{decimali}" if len(decimali) in {1, 2} else testo.replace(".", "")
    try:
        return f"{Decimal(testo).quantize(Decimal('0.01'))}"
    except (InvalidOperation, ValueError):
        return ""


def numero_canonico(valore: Any) -> str:
    return re.sub(r"\D", "", str(valore or ""))


def canonico(tipo: str, valore: Any) -> str:
    if tipo == DATA:
        return data_canonica(valore)
    if tipo == IMPORTO:
        return importo_canonico(valore)
    return numero_canonico(valore)


def _veri(pagina: Pagina) -> dict[str, set[str]]:
    veri: dict[str, set[str]] = {DATA: set(), IMPORTO: set(), NUMERO: set()}
    for valore in pagina.valori:
        veri[valore.tipo].add(canonico(valore.tipo, valore.valore))
    return veri


def forma_italiana(valore: Valore) -> str:
    """Come il valore vero si scrive in una pagina italiana (per la prova di lettura)."""
    if valore.tipo == DATA:
        anno, mese, giorno = valore.valore.split("-")
        return f"{giorno}/{mese}/{anno}"
    if valore.tipo == IMPORTO:
        interi, _, decimali = valore.valore.partition(".")
        return f"{int(interi):,}".replace(",", ".") + f",{decimali or '00'}"
    return valore.valore


def nel_testo(valore: Valore, testo: str) -> bool:
    """Stadio di lettura: il valore vero si ritrova nel testo letto (con le stesse regole del cancello)."""
    from pct.provenienza_ai import cancello_ancoraggio

    return cancello_ancoraggio({"v": forma_italiana(valore)}, testo).ammesso


@dataclass
class Proposta:
    tipo: str
    valore: str
    vero: bool
    ammesso: bool
    nel_testo: bool = True  # per un valore vero: la sua forma giusta è nel testo letto
    motivo: str = ""
    # Non è fra i valori elencati ma è scritto nella pagina (un nome, una percentuale,
    # un periodo di tabella, una stringa copiata con l'errore di lettura): non è inventato.
    presente: bool = False


def _semplice(testo: Any) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", base).split())


def scritto_nella_pagina(tipo: str, valore: str, testo: str) -> bool:
    """Il valore compare nella pagina, letteralmente o nella stessa forma canonica (giudizio indipendente dal cancello)."""
    if _semplice(valore) and f" {_semplice(valore)} " in f" {_semplice(testo)} ":
        return True
    if tipo == DATA:
        date = {data_canonica(m) for m in re.findall(r"\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}|\d{1,2}\s+[a-z]+\s+\d{4}", testo, re.I)}
        return bool(data_canonica(valore)) and data_canonica(valore) in date
    if tipo == IMPORTO:
        importi = {importo_canonico(m) for m in re.findall(r"\d[\d.]*,\d{1,2}|\d{1,3}(?:\.\d{3})+", testo)}
        return bool(importo_canonico(valore)) and importo_canonico(valore) in importi
    return False


@dataclass
class EsitoPagina:
    id: str
    lettore: str
    proposte: list[Proposta]
    veri_totali: int
    veri_trovati: int
    veri_nel_testo: int
    secondi: float
    errore: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _segnaposto(valore: str) -> bool:
    from pct.provenienza_ai import _NESSUN_VALORE, _semplice as _semplice_cancello

    return _semplice_cancello(valore) in _NESSUN_VALORE


def valuta_pagina(pagina: Pagina, proposte: Iterable[dict[str, Any]], *, lettore: str, secondi: float = 0.0, errore: str = "") -> EsitoPagina:
    from pct.provenienza_ai import cancello_ancoraggio

    veri = _veri(pagina)
    trovati: set[tuple[str, str]] = set()
    giudicate: list[Proposta] = []
    corrotti = {(v.tipo, canonico(v.tipo, v.valore)) for v in pagina.valori if v.lettura_corrotta}
    for proposta in proposte:
        tipo = str(proposta.get("tipo") or "").strip().casefold()
        valore = " ".join(str(proposta.get("valore") or "").split())
        if not valore or _segnaposto(valore):
            # «n.d.», «N/A»: il lettore dice che il valore non c'è. Il cancello
            # non lo fa passare come dato, quindi non è un valore inventato.
            continue
        if tipo not in {DATA, IMPORTO, NUMERO}:
            tipo = DATA if data_canonica(valore) else IMPORTO if re.search(r"[€,]|euro", valore, re.I) else NUMERO
        forma = canonico(tipo, valore)
        vero = bool(forma) and forma in veri[tipo]
        if not vero and tipo == NUMERO:
            # un importo o una data chiesti come «numero»: si confrontano con le cifre
            vero = bool(forma) and forma in {numero_canonico(v.valore) for v in pagina.valori}
        if vero:
            trovati.add((tipo, forma))
        esito = cancello_ancoraggio({"valore": valore}, pagina.testo)
        controllo = esito.controlli[0] if esito.controlli else None
        giudicate.append(Proposta(
            tipo=tipo, valore=valore, vero=vero, ammesso=esito.ammesso,
            nel_testo=not (vero and (tipo, forma) in corrotti), motivo=controllo.motivo if controllo else "",
            presente=not vero and scritto_nella_pagina(tipo, valore, pagina.testo),
        ))
    return EsitoPagina(
        id=pagina.id, lettore=lettore, proposte=giudicate,
        veri_totali=len(pagina.valori), veri_trovati=len(trovati),
        veri_nel_testo=sum(1 for v in pagina.valori if not v.lettura_corrotta),
        secondi=round(secondi, 2), errore=errore,
    )


def riepilogo(esiti: list[EsitoPagina]) -> dict[str, Any]:
    proposte = [p for e in esiti for p in e.proposte]
    vere_nel_testo = [p for p in proposte if p.vero and p.nel_testo]
    bloccate_a_torto = [p for p in vere_nel_testo if not p.ammesso]
    inventate = [p for p in proposte if not p.vero and not p.presente]
    return {
        "pagine": len(esiti),
        "valori_veri": sum(e.veri_totali for e in esiti),
        "lettura_valori_nel_testo": sum(e.veri_nel_testo for e in esiti),
        "estrazione_valori_trovati": sum(e.veri_trovati for e in esiti),
        "proposte": len(proposte),
        "proposte_vere": sum(1 for p in proposte if p.vero),
        "presenti_non_elencate": sum(1 for p in proposte if not p.vero and p.presente),
        "inventate": len(inventate),
        "inventate_passate": sum(1 for p in inventate if p.ammesso),
        "vere_bloccate_a_torto": len(bloccate_a_torto),
        "quota_blocchi_a_torto": round(len(bloccate_a_torto) / len(vere_nel_testo), 4) if vere_nel_testo else 0.0,
        "vere_bloccate_per_lettura": sum(1 for p in proposte if p.vero and not p.nel_testo and not p.ammesso),
        "secondi_medi": round(sum(e.secondi for e in esiti) / len(esiti), 2) if esiti else 0.0,
    }


# ── Il lettore simulato: forme varie dei valori veri e alcuni valori inventati ──

def _forme(valore: Valore, indice: int) -> str:
    """Il valore vero scritto in una delle forme in cui lo riscrive un modello."""
    if valore.tipo == DATA:
        anno, mese, giorno = (int(x) for x in valore.valore.split("-"))
        nomi = list(_MESI)
        forme = (f"{giorno:02d}/{mese:02d}/{anno}", valore.valore, f"{giorno} {nomi[mese - 1]} {anno}", f"{giorno:02d}.{mese:02d}.{anno}", f"{giorno}/{mese}/{anno}")
    elif valore.tipo == IMPORTO:
        numero = Decimal(valore.valore)
        interi = f"{int(numero):,}".replace(",", ".")
        decimali = f"{numero:.2f}".split(".")[1]
        forme = (f"€ {interi},{decimali}", f"{numero:.2f}", f"{interi},{decimali} euro", f"{numero.normalize():f}", f"EUR {numero:.2f}")
    else:
        forme = (valore.valore, f"n. {valore.valore}", valore.valore.replace("/", " / "))
    return forme[indice % len(forme)]


def _inventati(pagina: Pagina) -> list[dict[str, str]]:
    """Valori plausibili che nella pagina non ci sono: data spostata, cifra cambiata, somma."""
    inventati: list[dict[str, str]] = []
    date_vere = [v for v in pagina.valori if v.tipo == DATA]
    importi = [v for v in pagina.valori if v.tipo == IMPORTO]
    numeri = [v for v in pagina.valori if v.tipo == NUMERO]
    veri = _veri(pagina)
    if date_vere:
        giorno = date.fromisoformat(date_vere[0].valore) + timedelta(days=1)
        while giorno.isoformat() in veri[DATA]:
            giorno += timedelta(days=1)
        inventati.append({"tipo": DATA, "valore": giorno.strftime("%d/%m/%Y")})
    if importi:
        falso = Decimal(importi[0].valore) + Decimal("90")
        while f"{falso:.2f}" in veri[IMPORTO]:
            falso += Decimal("90")
        inventati.append({"tipo": IMPORTO, "valore": f"€ {falso:.2f}".replace(".", ",")})
    if len(importi) >= 2:
        somma = Decimal(importi[0].valore) + Decimal(importi[-1].valore)
        if f"{somma:.2f}" not in veri[IMPORTO]:
            inventati.append({"tipo": IMPORTO, "valore": f"{somma:.2f}"})
    if numeri:
        cifre = numeri[0].valore
        falso = cifre[:-1] + str((int(cifre[-1]) + 3) % 10) if cifre[-1].isdigit() else cifre + "1"
        inventati.append({"tipo": NUMERO, "valore": falso})
    return inventati


def lettore_simulato(pagina: Pagina, *, indice: int = 0) -> list[dict[str, str]]:
    proposte = [{"tipo": v.tipo, "valore": _forme(v, indice + n)} for n, v in enumerate(pagina.valori)]
    return proposte + _inventati(pagina)


# ── Il modello locale ─────────────────────────────────────────────────────────

SCHEMA_VALORI = {
    "type": "object",
    "properties": {
        "valori": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tipo": {"type": "string", "enum": [DATA, IMPORTO, NUMERO]}, "valore": {"type": "string"}, "descrizione": {"type": "string"}},
                "required": ["tipo", "valore", "descrizione"],
            },
        }
    },
    "required": ["valori"],
}


def domanda_valori(pagina: Pagina) -> str:
    return (
        "Sei il praticante di uno studio legale italiano. Dalla pagina che segue elenca TUTTI i valori numerici utili "
        "all'avvocato: date (tipo «data»), importi in euro (tipo «importo»), numeri di ruolo, di sentenza, di decreto, "
        "di protocollo, codici e partite IVA (tipo «numero»). Per ogni valore scrivi il valore com'è nella pagina e una "
        "breve descrizione. Non calcolare e non aggiungere valori che non sono scritti. Rispondi solo con il JSON.\n\n"
        f"PAGINA ({pagina.tipo}):\n{pagina.testo}"
    )


def valuta_con_modello(pagina: Pagina, genera: Callable[[str, dict[str, Any]], str], *, modello: str) -> EsitoPagina:
    inizio = time.monotonic()
    errore = ""
    try:
        risposta = json.loads(genera(domanda_valori(pagina), SCHEMA_VALORI) or "{}")
        valori = list(risposta.get("valori") or []) if isinstance(risposta, dict) else []
    except Exception as exc:
        valori, errore = [], str(exc)[:200]
    return valuta_pagina(pagina, [v for v in valori if isinstance(v, dict)], lettore=modello, secondi=time.monotonic() - inizio, errore=errore)


def valuta_simulato() -> list[EsitoPagina]:
    return [valuta_pagina(p, lettore_simulato(p, indice=i), lettore="simulato") for i, p in enumerate(PAGINE)]


__all__ = [
    "EsitoPagina", "Proposta", "SCHEMA_VALORI", "canonico", "data_canonica", "domanda_valori", "importo_canonico",
    "lettore_simulato", "nel_testo", "numero_canonico", "riepilogo", "valuta_con_modello", "valuta_pagina", "valuta_simulato",
]
