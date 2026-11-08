"""Riconvalida delle bozze «termine lungo» nate dalle PEC di sentenza prima della correzione del 31/10/2026.

Base normativa: art. 133 c.p.c. (la sentenza è resa pubblica con il deposito) e art. 327 c.p.c.
(sei mesi dalla pubblicazione); la comunicazione di cancelleria non fa decorrere il termine.

Verifica sulle PEC reali del 31/10/2026: per 33 bozze su 40 la data di decorrenza era quella
della comunicazione, perché la PEC non riporta la data dell'evento e la sentenza allegata è
l'originale del giudice, senza timbro di pubblicazione. Il principio è quello delle fonti certe:

- il software cerca la data di deposito: prima la sentenza depositata nel fascicolo telematico
  (PST, data del portale), poi il timbro «pubbl. il» letto dall'archivio delle letture, solo se
  legato allo stesso numero della sentenza comunicata; se la trova, ricalcola il termine e
  dichiara la fonte. Sul campione reale due proposte su quattro con la sentenza dal portale
  partivano dal giorno dopo il deposito: la scadenza indicata sarebbe stata tardiva;
- se non la trova, decide l'avvocato: la bozza resta da confermare con l'avviso che la data non
  è certa, e si ricontrolla quando il fascicolo riceve la sentenza dal portale. Nulla si cancella
  e nulla si conferma al posto dell'avvocato;
- intanto la data proposta è la più prudente (06/11/2026): se il testo della sentenza nel fascicolo
  dice quando è stata decisa («pronunciato in pari data» con l'udienza, o la data in calce prima
  della firma), il termine si conta da lì. La pubblicazione non può precedere la decisione, quindi
  la scadenza non è mai successiva a quella vera; la comunicazione arriva dopo e darebbe una
  scadenza tardiva (fascicolo Alessi, RG 2539/2025 Velletri: decisa il 07/10/2026, comunicata l'08/10).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from datetime import date

from pct.termine_lungo_sentenza import (
    data_decisione,
    data_deposito_dal_portale,
    data_pubblicazione_da_fatti,
    numero_sentenza,
    scadenza_termine_lungo,
)

MARCATORE_PEC = "PEC_TERMINE_PROPOSTO:"
CODICE_TERMINE_LUNGO = "CIV_APPELLO_LUNGO"
NON_CERTA = "DATA_DEPOSITO_NON_CERTA"
DAI_DOCUMENTI = "DATA_DEPOSITO_DAI_DOCUMENTI"
DALLA_DECISIONE = "DATA_DECISIONE_PRUDENZIALE"
_SENTENZA = re.compile(r"\bS\s?E\s?N\s?T\s?E\s?N\s?Z\s?A\b", re.IGNORECASE)
# L'ordinanza del giudice monocratico che dichiara l'estinzione ha natura di sentenza (si impugna con l'appello
# nel termine dell'art. 327 c.p.c.): la sua data in calce vale come la decisione di una sentenza.
_ESTINZIONE = re.compile(r"\bdichiara\s+(?:l['’]\s?)?estinzione\b|\bestinzione\s+del\s+(?:processo|giudizio)\b", re.IGNORECASE)
_ENTRO = re.compile(r"(entro il )\d{2}/\d{2}/\d{4}")
_CALCOLATI = re.compile(r"calcolati dal \d{2}/\d{2}/\d{4}(?:, data da verificare sul provvedimento|, da verificare sulla data di pubblicazione)?")
_FINESTRA_GIORNI = 60
AVVISO = (
    "Data di deposito non certa: la data indicata è quella della comunicazione di cancelleria, che non fa "
    "decorrere il termine (artt. 133 e 327 c.p.c.). Verificare la data di pubblicazione della sentenza sul "
    "portale o sulla copia con il timbro di deposito e correggere prima di confermare."
)


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def da_riconvalidare(scadenza: Any) -> bool:
    """Bozza di termine lungo nata da una PEC, con decorrenza uguale alla data della comunicazione."""
    note = _valore(scadenza, "note")
    if _valore(scadenza, "stato") != "BOZZA" or MARCATORE_PEC not in note:
        return False
    if _valore(scadenza, "deadline_profile_code") != CODICE_TERMINE_LUNGO or DAI_DOCUMENTI in note:
        return False
    if NON_CERTA in note:
        return True  # già segnalata: si ricontrolla finché non compare la fonte certa
    decorrenza, comunicazione = _valore(scadenza, "data_decorrenza")[:10], _valore(scadenza, "source_event_at")[:10]
    return bool(decorrenza) and decorrenza == comunicazione


def _fatti_della_sentenza(fatti: Iterable[Any], numero: str) -> list[Any]:
    compatto = re.sub(r"\s+", "", numero)
    return [fatto for fatto in fatti if compatto in re.sub(r"\s+", "", _valore(fatto, "contesto"))]


def decisione_dai_testi(testi: Iterable[str], *, comunicazione: date, estinzione: bool = False) -> date | None:
    """La data della decisione letta nelle sentenze del fascicolo decise nei 60 giorni prima della comunicazione;
    solo se una. Con ``estinzione`` contano i provvedimenti che dichiarano l'estinzione del processo."""
    trovate: set[date] = set()
    riconosce = _ESTINZIONE if estinzione else _SENTENZA
    for testo in testi:
        testo = str(testo or "")
        if not riconosce.search(testo if estinzione else testo[:4000]):
            continue
        giorno = data_decisione(testo)
        if giorno is not None and 0 <= (comunicazione - giorno).days <= _FINESTRA_GIORNI:
            trovate.add(giorno)
    return next(iter(trovate)) if len(trovate) == 1 else None


def allinea_testi(note: str, descrizione: str, *, scadenza: str, decorrenza: date, origine: str) -> tuple[str, str]:
    """Le frasi che riportano la scadenza e la decorrenza della proposta seguono la data ricalcolata.

    Senza, la voce dice «entro il 08/04/2027 … calcolati dal 08/10/2026» mentre la scadenza è il 07/04/2027
    (fascicolo Alessi, 8080, 08/11/2026): l'avvocato leggerebbe due date diverse per lo stesso termine.
    """
    giorno = date.fromisoformat(scadenza[:10]).strftime("%d/%m/%Y")
    note = "\n".join(_ENTRO.sub(lambda m: m.group(1) + giorno, riga) if riga.startswith("Termine proposto:") else riga
                     for riga in note.splitlines())
    descrizione = _CALCOLATI.sub(f"calcolati dal {decorrenza:%d/%m/%Y} ({origine})", descrizione, count=1)
    return note, descrizione


def _prudenziale(scadenziario: Any, scadenza: Any, decisione: date, *, testo: str, note: str) -> bool:
    origine = "giorno della decisione scritto nel provvedimento: verificare la data di deposito"
    if f"{DALLA_DECISIONE} decisione={decisione.isoformat()}" in note:
        # Già ricalcolata: si riallineano soltanto le frasi rimaste con la data della comunicazione.
        nuove, descrizione = allinea_testi(note, _valore(scadenza, "descrizione"), scadenza=_valore(scadenza, "data_scadenza"),
                                           decorrenza=decisione, origine=origine)
        if (nuove, descrizione) != (note, _valore(scadenza, "descrizione")):
            scadenziario.aggiorna(_valore(scadenza, "id"), note=nuove, descrizione=descrizione)
        return False
    calcolo = scadenza_termine_lungo(decisione, lavoro="Sospensione feriale non applicata" in testo)
    if calcolo["deadline"] >= _valore(scadenza, "data_scadenza")[:10]:
        return False  # solo se anticipa la scadenza: mai una data più tardiva
    note_senza = "\n".join(r for r in note.splitlines() if not r.startswith(DALLA_DECISIONE))
    note_senza, descrizione = allinea_testi(note_senza, _valore(scadenza, "descrizione"), scadenza=calcolo["deadline"],
                                            decorrenza=decisione, origine=origine)
    scadenziario.aggiorna(
        _valore(scadenza, "id"), data_scadenza=calcolo["deadline"], data_decorrenza=decisione.isoformat(),
        legal_due_at=calcolo["deadline"], raw_due_at=calcolo["rawDeadline"], descrizione=descrizione,
        note=(f"{note_senza}\n{DALLA_DECISIONE} decisione={decisione.isoformat()}: in attesa della data di deposito, il "
              "termine è contato dal giorno della decisione scritto nel provvedimento, che la pubblicazione non può "
              "precedere (artt. 133 e 327 c.p.c.).").strip(),
    )
    return True


def riconvalida_bozze(
    scadenziario: Any,
    fatti_del_fascicolo: Callable[[str], Iterable[Any]],
    documenti_del_fascicolo: Callable[[str], Iterable[Any]] | None = None,
    testi_del_fascicolo: Callable[[str], Iterable[str]] | None = None,
) -> dict[str, int]:
    esito = {"dal_portale": 0, "dai_documenti": 0, "da_giudicare": 0, "dalla_decisione": 0}
    for scadenza in list(scadenziario.tutte(solo_aperte=False)):
        if not da_riconvalidare(scadenza):
            continue
        testo = f"{_valore(scadenza, 'titolo')} {_valore(scadenza, 'descrizione')}"
        numero = numero_sentenza(testo)
        fascicolo_id = _valore(scadenza, "id_fascicolo")
        note = _valore(scadenza, "note")
        deposito, fonte = None, ""
        try:
            comunicazione = date.fromisoformat(_valore(scadenza, "source_event_at")[:10])
        except ValueError:
            comunicazione = None
        if fascicolo_id and comunicazione and documenti_del_fascicolo is not None:
            deposito = data_deposito_dal_portale(documenti_del_fascicolo(fascicolo_id), comunicazione=comunicazione)
            fonte = "dal_portale" if deposito else ""
        if deposito is None and numero and fascicolo_id:
            deposito = data_pubblicazione_da_fatti(_fatti_della_sentenza(fatti_del_fascicolo(fascicolo_id), numero), numero=numero)
            fonte = "dai_documenti" if deposito else ""
        if deposito is not None:
            lavoro = "Sospensione feriale non applicata" in testo
            calcolo = scadenza_termine_lungo(deposito, lavoro=lavoro)
            origine = ("data di deposito della sentenza nel fascicolo telematico (portale)" if fonte == "dal_portale"
                       else f"data di pubblicazione della sentenza n. {numero} letta dai documenti del fascicolo")
            note, descrizione = allinea_testi(note, _valore(scadenza, "descrizione").replace(AVVISO, "").strip(),
                                              scadenza=calcolo["deadline"], decorrenza=deposito, origine=origine)
            scadenziario.aggiorna(
                _valore(scadenza, "id"), data_scadenza=calcolo["deadline"], data_decorrenza=deposito.isoformat(),
                legal_due_at=calcolo["deadline"], raw_due_at=calcolo["rawDeadline"],
                descrizione=f"Termine lungo calcolato dal deposito del {deposito:%d/%m/%Y} ({origine}).\n{descrizione}".strip(),
                note=(f"{note.replace(NON_CERTA, '').strip()}\n{DAI_DOCUMENTI} deposito={deposito.isoformat()}: {origine}; "
                      "la data della comunicazione è stata sostituita.").strip(),
            )
            esito[fonte] += 1
        else:
            if NON_CERTA not in note:
                note = f"{note}\n{NON_CERTA}".strip()
                scadenziario.aggiorna(
                    _valore(scadenza, "id"), descrizione=f"{AVVISO}\n{_valore(scadenza, 'descrizione')}".strip(), note=note,
                )
                esito["da_giudicare"] += 1
            estinzione = "estinzione" in _valore(scadenza, "titolo").lower()
            decisione = (decisione_dai_testi(testi_del_fascicolo(fascicolo_id), comunicazione=comunicazione, estinzione=estinzione)
                         if testi_del_fascicolo is not None and fascicolo_id and comunicazione else None)
            if decisione is not None and _prudenziale(scadenziario, scadenza, decisione, testo=testo, note=note):
                esito["dalla_decisione"] += 1
    return esito


__all__ = ["AVVISO", "DAI_DOCUMENTI", "DALLA_DECISIONE", "NON_CERTA", "allinea_testi", "da_riconvalidare",
           "decisione_dai_testi", "riconvalida_bozze"]
