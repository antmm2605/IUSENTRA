"""Helper condivisi per i calcolatori giuridici modulari.

Funzioni di parsing e formattazione usate dai moduli di ``pct/calcolatori``.
Nessuna logica di dominio: solo normalizzazione input e utilità di calendario.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        raw = str(value).replace("€", "").replace(" ", "").strip()
        if not raw:
            return default
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        return float(raw)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "si", "sì", "yes", "on"}


def parse_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = clean_text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1


def year_denominator(day: date) -> int:
    year = day.year
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def fmt_date_it(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else clean_text(value)


def fmt_eur(valore: Any, decimali: int = 2) -> str:
    """Importo in formato italiano: punto per le migliaia, virgola per i decimali.

    Esiste qui perche' il formato di Python e' l'inverso di quello italiano e la
    sostituzione ingenua (`replace(",", ".")`) produce «30.000.00»: un numero che
    in un atto non si puo' scrivere.
    """
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return clean_text(valore)
    return f"{numero:,.{max(0, int(decimali))}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def payload_get(payload: Mapping[str, Any], key: str, default: Any = "") -> Any:
    try:
        return payload.get(key, default)
    except AttributeError:
        return default


_MESI_IT = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


def mese_it(mese: int) -> str:
    return _MESI_IT[mese - 1] if 1 <= mese <= 12 else str(mese)


def messaggio_indice_istat_mancante(norme: Any, tipo: str, anno: int, mese: int, contesto: str = "") -> str:
    """Spiega perche' un indice ISTAT manca e cosa puo' fare l'avvocato.

    L'ISTAT pubblica l'indice di un mese circa due mesi dopo, con il comunicato
    in Gazzetta Ufficiale: chiedere il mese in corso non e' un errore
    dell'utente ne' un guasto, e il messaggio deve dirlo invece di limitarsi a
    negare il dato.
    """
    ultimo = None
    try:
        ultimo = norme.istat_last_available(tipo)
    except Exception:
        ultimo = None
    richiesto = f"{mese_it(mese)} {anno}"
    dettaglio = f" ({contesto})" if contesto else ""
    if not ultimo:
        return (
            f"Indice ISTAT {tipo.upper()} non disponibile per {richiesto}{dettaglio}: "
            "la serie non e' caricata."
        )
    disponibile = f"{mese_it(int(ultimo.get('month', 0)))} {ultimo.get('year', '?')}"
    posteriore = (anno, mese) > (int(ultimo.get("year", 0)), int(ultimo.get("month", 0)))
    if posteriore:
        return (
            f"Indice ISTAT {tipo.upper()} non ancora pubblicato per {richiesto}{dettaglio}. "
            f"L'ultimo indice pubblicato e' quello di {disponibile}: l'ISTAT diffonde ogni "
            "mese con circa due mesi di ritardo, con il comunicato in Gazzetta Ufficiale. "
            "Usa l'ultimo mese pubblicato, oppure attendi il comunicato successivo."
        )
    return (
        f"Indice ISTAT {tipo.upper()} non disponibile per {richiesto}{dettaglio}: la serie "
        f"caricata copre fino a {disponibile} e non risale piu' indietro. "
        "Aggiorna la tabella normativa da /legal-intelligence."
    )


def messaggio_periodo_scaduto(copertura: Mapping[str, Any], cosa: str, cadenza: str) -> str:
    """Avviso quando la tabella a periodi non copre la data di calcolo."""
    fine = copertura.get("ultimo_fine") or copertura.get("ultimo_inizio")
    if fine:
        try:
            fine = datetime.strptime(str(fine), "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
    return (
        f"{cosa}: la tabella caricata arriva al {fine} e non copre la data indicata. "
        f"Il dato e' aggiornato {cadenza}: il valore mostrato e' quello dell'ultimo periodo "
        "disponibile e va confermato sulla Gazzetta Ufficiale prima dell'uso in atti."
    )
