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
    "veneto": "VENETO", "friuli venezia giulia": "FRIULI VENEZIA GIULIA", "friuli v g": "FRIULI VENEZIA GIULIA",
    "friuli": "FRIULI VENEZIA GIULIA", "trentino a a": "TRENTINO ALTO ADIGE", "trentino": "TRENTINO ALTO ADIGE", "emilia romagna": "EMILIA-ROMAGNA",
    "toscana": "TOSCANA", "umbria": "UMBRIA", "marche": "MARCHE", "lazio": "LAZIO", "abruzzo": "ABRUZZO",
    "molise": "MOLISE", "campania": "CAMPANIA", "basilicata": "BASILICATA", "calabria": "CALABRIA",
    "sicilia": "SICILIA", "sardegna": "SARDEGNA", "puglia": "PUGLIA",
}
_TAR = re.compile(r"\b(?:tribunale amministrativo(?: regionale)?|t a r|tar|tribunale regionale di giustizia amministrativa)\b")
# Città sedi dei TAR scritte in modo diverso dal Portale dell'Avvocato.
_CITTA_ALIAS = {"reggio di calabria": "reggio calabria", "reggio": "reggio calabria", "l aquila": "l aquila", "aquila": "l aquila"}


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


def _citta_nel_testo(testo: str, sedi: list[tuple[str, str, str, str]]) -> tuple[str, str, str, str] | None:
    """La sede la cui città compare nel testo (la più lunga prima: «reggio calabria» prima di «reggio»)."""
    for alias, citta in sorted(_CITTA_ALIAS.items(), key=lambda voce: -len(voce[0])):
        testo = re.sub(rf"\b{alias}\b", citta, testo)
    for sede in sorted(sedi, key=lambda voce: -len(voce[3])):
        if re.search(rf"\b{re.escape(sede[3])}\b", testo):
            return sede
    return None


def sede_da_testo(testo: str) -> str:
    """Codice SIGA della sede nominata nel testo (TAR, Consiglio di Stato, CGARS); vuoto se non è chiara.

    Vale per l'epigrafe di un atto («Il T.A.R. per la Calabria - Sezione staccata di
    Reggio Calabria») e per l'ufficio scritto a mano nel fascicolo («TAR VENEZIA»,
    «Tribunale amministrativo del Veneto», «Tar della Calabria sede di Reggio
    Calabria»): la regione dà la sede principale, la città la sezione staccata;
    la sola città basta quando è sede di un TAR. «TAR» senza luogo non basta.
    """
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
    dopo = semplice[trovato.end():][:120]
    tutte = _sedi_tar()
    regione = next((_REGIONI[nome] for nome in sorted(_REGIONI, key=len, reverse=True) if re.search(rf"\b{nome}\b", dopo)), "")
    if not regione:
        citta = _citta_nel_testo(dopo, tutte)
        return citta[1] if citta else ""
    sedi = [s for s in tutte if s[2] == _semplice(regione)]
    senza_regione = dopo
    for nome, valore in _REGIONI.items():
        if valore == regione and nome not in {"bolzano", "trento"}:
            senza_regione = re.sub(rf"\b{nome}\b", " ", senza_regione)
    citta = _citta_nel_testo(senza_regione, sedi)
    if citta:
        return citta[1]
    principale = next((s for s in sedi if s[0].endswith("0000")), None)
    return principale[1] if principale else ""


def codice_ufficio_da_testo(testo: str) -> str:
    """Il codice del registro uffici IUSENTRA (T170001, CDS000000…) della sede nominata nel testo."""
    sede = sede_da_testo(testo)
    return next((codice for codice, (siga, _etichetta) in catalogo.SEDI.items() if siga == sede), "") if sede else ""


def giustizia_amministrativa(testo: str) -> bool:
    """Il testo nomina un giudice amministrativo (TAR, Consiglio di Stato, CGARS), anche senza sede."""
    semplice = _semplice(testo)
    return bool(_TAR.search(semplice)) or "consiglio di stato" in semplice or "consiglio di giustizia amministrativa" in semplice


_UFFICIO_ORDINARIO = re.compile(
    r"\b(?:tribunale(?! amministrativo| regionale di giustizia)(?: ordinario)?(?: di| del| della| per)?|corte d ?appello|corte di appello|"
    r"giudice di pace|giudice del lavoro|sezione lavoro|corte di cassazione|corte suprema di cassazione|corte dei conti)\b"
)
_AMMINISTRATIVO = re.compile(
    r"\b(?:tribunale amministrativo(?: regionale)?|t a r|tar|tribunale regionale di giustizia amministrativa|consiglio di stato|"
    r"consiglio di giustizia amministrativa|reg ric|registro generale dei ricorsi)\b"
)


def ruolo_amministrativo(fatto: Any) -> bool:
    """Il numero letto è il registro generale di un giudice amministrativo, non di un altro ufficio.

    Il fascicolo di un'ottemperanza contiene la sentenza del giudice ordinario da
    eseguire: il suo «R.G. 2914/2024» è del Tribunale di Palmi, non il NRG del TAR.
    Il numero vale solo se l'ultimo ufficio nominato prima di esso è un giudice
    amministrativo (o la sigla del registro ricorsi lo segue); le sigle del ruolo
    civile (R.G.L., R.G.A.C.) lo escludono. Senza un giudice amministrativo nel
    contesto non si propone nulla: meglio un dato da indicare che un NRG sbagliato.
    """
    letto = _semplice(getattr(fatto, "valore_letto", ""))
    if re.match(r"^(?:r g l|rgl|r g a c|rgac)\b", letto):
        return False
    contesto = _semplice(getattr(fatto, "contesto", ""))
    numero, _, anno = str(getattr(fatto, "valore", "") or "").partition("/")
    posizione = -1
    if numero and anno:
        cercato = re.search(rf"\b0*{int(numero) if numero.isdigit() else re.escape(numero)} {anno[-4:]}\b", contesto)
        posizione = cercato.start() if cercato else -1
    prima = contesto if posizione < 0 else contesto[:posizione]
    dopo = "" if posizione < 0 else contesto[posizione:posizione + 60]
    ultimo_amm = max((m.start() for m in _AMMINISTRATIVO.finditer(prima)), default=-1)
    ultimo_ord = max((m.start() for m in _UFFICIO_ORDINARIO.finditer(prima)), default=-1)
    if ultimo_amm > ultimo_ord:
        return True
    return ultimo_ord < 0 and bool(_AMMINISTRATIVO.search(dopo)) and not _UFFICIO_ORDINARIO.search(dopo)


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
        if not nrg or not ruolo_amministrativo(fatto):
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


__all__ = ["codice_ufficio_da_testo", "dati_letti", "giustizia_amministrativa", "nrg_da_ruolo", "ruolo_amministrativo", "sede_da_testo"]
