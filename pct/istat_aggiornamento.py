"""Aggiornamento automatico degli indici FOI dalla fonte ufficiale ISTAT (servizio SDMX).

Richiesta dell'avvocato del 31/10/2026: gli indici di luglio e agosto 2026 mancavano e la
tabella si aggiornava solo a mano. La fonte certa è il servizio dati ufficiale dell'ISTAT
(esploradati.istat.it, SDMX), flusso «Foi, mensili dal 2026 (base 2025)»: indice generale
senza tabacchi (ECOICOP 2 = 00ST), numero indice (MEASURE 4) e variazione tendenziale
pubblicata (MEASURE 7). La variazione «accertata dall'ISTAT» è quella che vale per
l'aggiornamento dei canoni (art. 32 L. 392/1978; L. 431/1998) e per le rivalutazioni.

Regole (fonti certe):
- si importano solo i mesi con indice e variazione entrambi pubblicati;
- un mese già presente non si sovrascrive se il valore differisce: si segnala (le
  rettifiche ISTAT si guardano a mano, mai in silenzio);
- valori fuori misura (indice non fra 80 e 200, variazione oltre ±20 punti, salti di
  mese) bloccano l'aggiornamento;
- ogni importazione pubblica una nuova versione della tabella con fonte, URL e data.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable

FLUSSO_FOI = "IT1,169_748_DF_DCSP_FOI1B2025_1,1.0"
BASE = 2025
URL_SERVIZIO = "https://esploradati.istat.it/SDMXWS/rest/data/{flusso}/?startPeriod={dal}&format=csv"
PAGINA_FONTE = "https://www.istat.it/notizia/indice-dei-prezzi-per-le-rivalutazioni-monetarie/"
_SENZA_TABACCHI = "00ST"
_DATO_FOI = "101"
_INDICE, _VARIAZIONE_ANNUA = "4", "7"


@dataclass
class EsitoAggiornamento:
    nuovi: list[dict[str, Any]] = field(default_factory=list)
    discordanze: list[str] = field(default_factory=list)
    bloccato: str = ""

    @property
    def aggiornabile(self) -> bool:
        return bool(self.nuovi) and not self.bloccato


def url_dati(dal: date) -> str:
    return URL_SERVIZIO.format(flusso=FLUSSO_FOI, dal=f"{dal.year:04d}-{dal.month:02d}")


def _colonna(riga: dict[str, str], *nomi: str) -> str:
    for nome in nomi:
        for chiave, valore in riga.items():
            if chiave and chiave.strip().upper() == nome:
                return str(valore or "").strip()
    return ""


def leggi_csv(testo: str) -> dict[tuple[int, int], dict[str, float]]:
    """{(anno, mese): {"index": …, "variation_yoy": …}} dalle righe FOI senza tabacchi, Italia, mensili."""
    valori: dict[tuple[int, int], dict[str, float]] = {}
    for riga in csv.DictReader(io.StringIO(testo)):
        # Solo il dato nazionale mensile: il file contiene anche le 77 province.
        if _colonna(riga, "FREQ") != "M" or _colonna(riga, "REF_AREA") != "IT":
            continue
        if _colonna(riga, "DATA_TYPE") != _DATO_FOI or _colonna(riga, "ECOICOP_2") != _SENZA_TABACCHI:
            continue
        misura = _colonna(riga, "MEASURE")
        periodo = _colonna(riga, "TIME_PERIOD")
        grezzo = _colonna(riga, "OBS_VALUE").replace(",", ".")
        try:
            anno, mese = int(periodo[:4]), int(periodo[5:7])
            valore = float(grezzo)
        except ValueError:
            continue
        chiave = {"4": "index", "7": "variation_yoy"}.get(misura)
        if chiave:
            valori.setdefault((anno, mese), {})[chiave] = valore
    return valori


def confronta(esistenti: Iterable[dict[str, Any]], scaricati: dict[tuple[int, int], dict[str, float]]) -> EsitoAggiornamento:
    esito = EsitoAggiornamento()
    presenti = {(int(r.get("year", 0)), int(r.get("month", 0))): r for r in esistenti}
    for (anno, mese), dati in sorted(scaricati.items()):
        if "index" not in dati or "variation_yoy" not in dati:
            continue
        indice, variazione = dati["index"], dati["variation_yoy"]
        if not (80.0 <= indice <= 200.0) or abs(variazione) > 20.0:
            esito.bloccato = f"Valore fuori misura per {mese:02d}/{anno}: indice {indice}, variazione {variazione}."
            return esito
        attuale = presenti.get((anno, mese))
        if attuale is not None:
            if abs(float(attuale.get("index", 0)) - indice) > 1e-9 or int(attuale.get("base", BASE)) != BASE:
                esito.discordanze.append(
                    f"{mese:02d}/{anno}: in tabella {attuale.get('index')}, ISTAT {indice} (verificare la rettifica)."
                )
            continue
        esito.nuovi.append({"year": anno, "month": mese, "index": indice, "variation_yoy": variazione, "base": BASE})
    # i mesi nuovi devono proseguire la serie senza salti
    ultimo = max(presenti, default=None)
    for riga in esito.nuovi:
        atteso = (ultimo[0] + (ultimo[1] // 12), ultimo[1] % 12 + 1) if ultimo else None
        if atteso and (riga["year"], riga["month"]) != atteso:
            esito.bloccato = f"Serie non continua: manca {atteso[1]:02d}/{atteso[0]} prima di {riga['month']:02d}/{riga['year']}."
            return esito
        ultimo = (riga["year"], riga["month"])
    return esito


def mese_atteso(oggi: date) -> tuple[int, int]:
    """L'ultimo mese che l'ISTAT dovrebbe aver pubblicato: il precedente dopo metà mese, altrimenti quello prima."""
    anno, mese = oggi.year, oggi.month - (1 if oggi.day >= 16 else 2)
    while mese < 1:
        anno, mese = anno - 1, mese + 12
    return anno, mese


def serve_aggiornare(righe: Iterable[dict[str, Any]], oggi: date) -> bool:
    """Si chiede alla fonte solo se manca un mese che dovrebbe essere già pubblicato (nessuna chiamata inutile)."""
    ultimo = max(((int(r.get("year", 0)), int(r.get("month", 0))) for r in righe), default=(0, 0))
    return ultimo < mese_atteso(oggi)


def scarica_https(url: str, *, timeout: float = 60.0) -> str:
    """Download del CSV ufficiale (rispetta i proxy di sistema)."""
    from urllib.request import Request, urlopen

    richiesta = Request(url, headers={"User-Agent": "IUSENTRA/aggiornamento-indici-ISTAT", "Accept": "text/csv"})
    with urlopen(richiesta, timeout=timeout) as risposta:  # noqa: S310 - URL fisso del servizio ISTAT
        return risposta.read().decode("utf-8", errors="replace")


def aggiorna_foi(
    norme: Any,
    scarica: Callable[[str], str],
    *,
    oggi: date,
) -> dict[str, Any]:
    """Scarica, controlla e pubblica i mesi nuovi della tabella FOI. Nessun dato inventato."""
    esistenti = list(norme.rows("istat_foi"))
    in_base = [r for r in esistenti if int(r.get("base", 0)) == BASE]
    dal = date(oggi.year - 1, 1, 1) if not in_base else date(oggi.year, 1, 1)
    url = url_dati(dal)
    try:
        testo = scarica(url)
    except Exception as exc:
        return {"esito": "fonte_non_raggiungibile", "url": url, "errore": type(exc).__name__}
    esito = confronta(esistenti, leggi_csv(testo))
    risposta = {"url": url, "nuovi": [f"{r['month']:02d}/{r['year']}" for r in esito.nuovi], "discordanze": esito.discordanze}
    if esito.bloccato:
        return {**risposta, "esito": "bloccato", "motivo": esito.bloccato}
    if not esito.aggiornabile:
        return {**risposta, "esito": "gia_aggiornata"}
    righe = sorted(esistenti + esito.nuovi, key=lambda r: (int(r["year"]), int(r["month"])))
    tabella = norme.get_table("istat_foi")
    norme.update_table_rows(
        "istat_foi",
        righe,
        published_at=oggi.isoformat(),
        effective_from=oggi.isoformat(),
        label=f"ISTAT FOI fino a {esito.nuovi[-1]['month']:02d}/{esito.nuovi[-1]['year']} (servizio SDMX)",
        notes=[f"Importati dal servizio ufficiale ISTAT {url} il {oggi.strftime('%d/%m/%Y')}.", f"Fonte: {PAGINA_FONTE}"],
        defaults=dict(tabella.get("defaults") or {}),
        origin="istat_sdmx",
        source_changed=True,
    )
    return {**risposta, "esito": "aggiornata"}


__all__ = [
    "BASE", "FLUSSO_FOI", "EsitoAggiornamento", "aggiorna_foi", "confronta", "leggi_csv", "mese_atteso",
    "scarica_https", "serve_aggiornare", "url_dati",
]
