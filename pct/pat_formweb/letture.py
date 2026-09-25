"""Dati del procedimento amministrativo letti dai documenti già nel fascicolo.

Il fascicolo di un ricorso già depositato contiene di solito la sentenza, gli
atti notificati e le ricevute: il registro generale (NRG) e la sede del TAR vi
sono scritti in epigrafe («Il Tribunale Amministrativo Regionale per il Lazio
(Sezione Seconda) … sul ricorso numero di registro generale 10549 del 2025»).
Questi dati li ha già estratti e collaudati l'archivio delle letture
(``pct/archivio_letture``): qui si consultano i fatti, non si rilegge nulla.

Un dato letto è una proposta: la scheda lo mostra «da verificare» con il
documento da cui viene, e diventa del procedimento solo quando l'avvocato lo
conferma. La sede segue la scrittura del Formweb: sede principale del TAR
della regione o sezione staccata quando il documento la nomina (l. 6 dicembre
1971 n. 1034; art. 136 c.p.a. per il deposito telematico).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from . import catalogo

VERIFICHE_UTILI = ("verificata", "plausibile", "corretta")
_REGIONI = {
    "piemonte": "PIEMONTE", "valle d aosta": "VALLE D'AOSTA", "lombardia": "LOMBARDIA", "liguria": "LIGURIA",
    "trentino alto adige": "TRENTINO ALTO ADIGE", "bolzano": "TRENTINO ALTO ADIGE", "trento": "TRENTINO ALTO ADIGE",
    "veneto": "VENETO", "friuli venezia giulia": "FRIULI VENEZIA GIULIA", "emilia romagna": "EMILIA-ROMAGNA",
    "toscana": "TOSCANA", "umbria": "UMBRIA", "marche": "MARCHE", "lazio": "LAZIO", "abruzzo": "ABRUZZO",
    "molise": "MOLISE", "campania": "CAMPANIA", "basilicata": "BASILICATA", "calabria": "CALABRIA",
    "sicilia": "SICILIA", "sardegna": "SARDEGNA", "puglia": "PUGLIA",
}
_TAR = re.compile(r"\b(?:tribunale amministrativo regionale|t a r|tar|tribunale regionale di giustizia amministrativa)\b")


def _semplice(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


def _sedi_tar() -> list[tuple[str, str, str, str]]:
    """(chiave bundle, codice SIGA, regione, città) per ogni sede TAR del Formweb."""
    righe = []
    for chiave, (codice, etichetta) in catalogo.SEDI.items():
        if etichetta.startswith("TAR ") and " - " in etichetta:
            regione, citta = etichetta[4:].split(" - ", 1)
            righe.append((chiave, codice, _semplice(regione), _semplice(citta)))
    return righe


def sede_da_testo(testo: str) -> str:
    """Codice SIGA della sede nominata nel testo (TAR, Consiglio di Stato, CGARS); vuoto se non è chiara."""
    semplice = _semplice(testo)
    if not semplice:
        return ""
    if "consiglio di giustizia amministrativa" in semplice:
        return "cgagiur"
    if "consiglio di stato" in semplice:
        return "cds"
    trovato = _TAR.search(semplice)
    if not trovato:
        return ""
    dopo = semplice[trovato.end():]
    regione = next((_REGIONI[nome] for nome in sorted(_REGIONI, key=len, reverse=True) if re.search(rf"\b{nome}\b", dopo[:80])), "")
    if not regione:
        return ""
    sedi = [s for s in _sedi_tar() if s[2] == _semplice(regione)]
    staccata = re.search(r"\b(?:sezione staccata|sede staccata|sede) di ([a-z ]+)", dopo)
    if staccata:
        citta = next((s for s in sedi if staccata.group(1).startswith(s[3])), None)
        if citta:
            return citta[1]
    for nome in ("bolzano", "trento"):
        if regione == "TRENTINO ALTO ADIGE" and re.search(rf"\b{nome}\b", dopo[:80]):
            return next((s[1] for s in sedi if s[3] == nome), "")
    principale = next((s for s in sedi if s[0].endswith("0000")), None)
    return principale[1] if principale else ""


def nrg_da_ruolo(valore: str) -> str:
    """«10549/2025» → «202510549», come lo chiede il Formweb."""
    trovato = re.fullmatch(r"\s*(\d{1,6})\s*/\s*(\d{4})\s*", str(valore or ""))
    return f"{trovato.group(2)}{int(trovato.group(1)):05d}" if trovato else ""


def dati_letti(fatti: Iterable[Any], nomi: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """NRG e sede proposti dai fatti «ruolo» dell'archivio, con i documenti da cui vengono."""
    nomi = nomi or {}
    candidati: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if getattr(fatto, "categoria", "") != "ruolo" or getattr(fatto, "campo", "") != "numero_ruolo":
            continue
        if getattr(fatto, "verifica", "") not in VERIFICHE_UTILI:
            continue
        nrg = nrg_da_ruolo(getattr(fatto, "valore", ""))
        if not nrg:
            continue
        voce = candidati.setdefault(nrg, {"valore": nrg, "rg": fatto.valore, "verifica": fatto.verifica,
                                          "documenti": [], "sede": ""})
        if fatto.verifica == "verificata":
            voce["verifica"] = "verificata"
        documento = nomi.get(getattr(fatto, "oggetto_id", ""), "")
        if documento and documento not in voce["documenti"]:
            voce["documenti"].append(documento)
        voce["sede"] = voce["sede"] or sede_da_testo(getattr(fatto, "contesto", ""))
    if not candidati:
        return {}
    ordinati = sorted(candidati.values(), key=lambda v: (v["verifica"] != "verificata", not v["sede"], -len(v["documenti"])))
    scelto = ordinati[0]
    esito: dict[str, dict[str, Any]] = {"nrg": {k: scelto[k] for k in ("valore", "rg", "verifica", "documenti")}}
    if len(candidati) > 1:
        esito["nrg"]["altri"] = [v["rg"] for v in ordinati[1:]]
    if scelto["sede"]:
        esito["sede"] = {"valore": scelto["sede"], "verifica": scelto["verifica"], "documenti": scelto["documenti"]}
    return esito


__all__ = ["dati_letti", "nrg_da_ruolo", "sede_da_testo"]
