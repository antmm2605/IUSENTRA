"""Il procedimento d'ingiunzione letto dagli atti: dove si trova e qual è il passo successivo.

Il monitorio non ha udienze: il giudice pronuncia sul ricorso (art. 633 c.p.c.), con decreto da notificare entro
sessanta giorni dalla pronuncia (art. 644 c.p.c.), che ingiunge di pagare entro quaranta giorni con l'avvertimento
che nello stesso termine si può fare opposizione (art. 641 c.p.c.). Senza opposizione il giudice, su istanza, dichiara
esecutivo il decreto (art. 647 c.p.c.); ai fini dell'esecuzione non occorre una nuova notificazione, ma nel precetto
si menziona il provvedimento che ha disposto l'esecutorietà (art. 654 c.p.c.). Il decreto può essere già
provvisoriamente esecutivo (art. 642 c.p.c.). Con l'opposizione il giudizio prosegue secondo le norme del processo di
cognizione (art. 645 c.p.c.): da lì valgono le fasi ordinarie.

Il termine di opposizione si conta in giorni dalla notificazione, con la sospensione feriale dal 1° al 31 agosto
(art. 1 L. 742/1969, che non si applica alle controversie di lavoro, art. 3) e con la proroga al primo giorno non
festivo, sabato compreso (art. 155, commi 4 e 5, c.p.c.).

Collaudo 10/11/2026 (Giudice di Pace di Palmi, RG 4202/2024): la Lettura diceva «iscritta a ruolo, in attesa della
prima udienza»; la sequenza vera è d.i. emesso il 20/12/2024, notificato il 23/12/2024, opposizione fino al
03/02/2025, dichiarato esecutivo il 10/03/2025: il passo successivo è il precetto.

Funzione pura: riceve i documenti catalogati e i fatti dell'archivio (dizionari), non legge file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

FASE_RICORSO = "monitorio_ricorso"
FASE_NOTIFICA = "monitorio_notifica"
FASE_OPPOSIZIONE = "monitorio_termine_opposizione"
FASE_ESECUTORIETA = "monitorio_esecutorieta"
FASE_ESECUTIVO = "monitorio_esecutivo"
FASE_OPPOSTO = "monitorio_opposto"

_RE_DECRETO = re.compile(r"decreto\s*ingiuntivo", re.I)
_RE_RICORSO = re.compile(r"ricorso\s+per\s+decreto\s+ingiuntivo|ricorso\s+monitorio", re.I)
_RE_OPPOSIZIONE = re.compile(r"opposizione\s+a(?:l)?\s+decreto\s+ingiuntivo|citazione\s+in\s+opposizione", re.I)
# Il dispositivo del giudice («DICHIARA esecutivo il decreto»), non la domanda dell'istanza («dichiararsi esecutivo»).
_RE_DICHIARA_ESECUTIVO = re.compile(r"\bdichiara\s+(?:provvisoriamente\s+)?esecutiv|\bdichiara\s+(?:la\s+)?esecutoriet|decreto\s+di\s+esecutoriet", re.I)
_RE_PROVVISORIA = re.compile(r"provvisoriamente\s+esecutiv|provvisoria\s+esecuzione|ingiuntivo\s*esecutivo(?!\w)", re.I)
_RE_NOME_ESECUTIVO = re.compile(r"accoglimentodecretoingiuntivoesecutivo", re.I)
_RE_NOTIFICA_DECRETO = re.compile(r"decret|ingiunt|notificat", re.I)
UTILI = {"verificata", "corretta"}


@dataclass
class StatoMonitorio:
    codice: str
    descrizione: str
    prove: list[str] = field(default_factory=list)
    emesso_il: date | None = None
    notificato_il: date | None = None
    opposizione_fino_al: date | None = None
    esecutivo_il: date | None = None
    provvisoriamente_esecutivo: bool = False
    passi: list[dict[str, Any]] = field(default_factory=list)

    def come_dizionario(self) -> dict[str, Any]:
        def it(giorno: date | None) -> str:
            return giorno.strftime("%d/%m/%Y") if giorno else ""
        return {"codice": self.codice, "descrizione": self.descrizione, "prove": list(self.prove), "emesso_il": it(self.emesso_il),
                "notificato_il": it(self.notificato_il), "opposizione_fino_al": it(self.opposizione_fino_al),
                "esecutivo_il": it(self.esecutivo_il), "provvisoriamente_esecutivo": self.provvisoriamente_esecutivo,
                "passi": list(self.passi)}


def _giorno(valore: Any) -> date | None:
    testo = " ".join(str(valore or "").split())[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


def _it(giorno: date) -> str:
    return giorno.strftime("%d/%m/%Y")


def termine_opposizione(notificato_il: date, *, lavoro: bool = False) -> date:
    """Quaranta giorni dalla notificazione (art. 641 c.p.c.), sospensione feriale salvo lavoro, proroga art. 155 c.p.c."""
    from pct.scadenziario import _aggiungi_giorni_processuali, prossimo_giorno_lavorativo

    scadenza = _aggiungi_giorni_processuali(notificato_il, 40, sospensione_feriale=not lavoro)
    return prossimo_giorno_lavorativo(scadenza, sospensione_feriale=False)


def _fatti_di(fonti: Iterable[dict[str, Any]], oggetto_id: str) -> list[dict[str, Any]]:
    return [f for f in fonti if f.get("oggetto_id") == oggetto_id and f.get("verifica") in UTILI]


def _data_del_documento(fatti: list[dict[str, Any]]) -> date | None:
    in_calce = sorted((f for f in fatti if f.get("campo") == "data_atto"), key=lambda f: int(f.get("posizione") or 0))
    giorno = _giorno(in_calce[-1]["valore"]) if in_calce else None
    if giorno:
        return giorno
    provvedimento = sorted((f for f in fatti if f.get("campo") == "provvedimento"), key=lambda f: int(f.get("posizione") or 0))
    return _giorno(provvedimento[0]["valore"]) if provvedimento else None


def stato_monitorio(documenti: Iterable[dict[str, Any]], fonti: Iterable[dict[str, Any]], *, oggi: date,
                    cliente_ricorrente: bool | None = True, lavoro: bool = False) -> StatoMonitorio | None:
    """La fase del procedimento d'ingiunzione e il passo successivo; None se gli atti non mostrano un monitorio."""
    documenti, fonti = list(documenti or []), list(fonti or [])
    etichette = [(d, f"{d.get('etichetta', '')} {d.get('nome', '')}") for d in documenti]
    if any(_RE_OPPOSIZIONE.search(testo) for _, testo in etichette):
        return StatoMonitorio(FASE_OPPOSTO, "decreto ingiuntivo opposto: il giudizio prosegue con le norme del processo di cognizione (art. 645 c.p.c.)")
    ricorsi = [d for d, testo in etichette if _RE_RICORSO.search(testo)]
    decreti = [d for d, testo in etichette if _RE_DECRETO.search(str(d.get("etichetta") or "")) and not _RE_RICORSO.search(testo)
               or _RE_NOME_ESECUTIVO.search(str(d.get("nome") or "")) or "accoglimentodecretoingiuntivo" in str(d.get("nome") or "").lower()]
    if not ricorsi and not decreti:
        return None
    stato = StatoMonitorio(FASE_RICORSO, "ricorso per decreto ingiuntivo depositato: in attesa del decreto (il procedimento non ha udienze, art. 633 c.p.c.)")
    if ricorsi:
        stato.prove.append(str(ricorsi[0].get("etichetta") or "Ricorso per decreto ingiuntivo"))
    emissioni = [g for d in decreti if (g := _data_del_documento(_fatti_di(fonti, str(d.get("id") or ""))))]
    for f in fonti:
        if f.get("verifica") in UTILI and f.get("campo") == "provvedimento" and re.search(r"decreto\s+ingiuntivo[^.]{0,80}emess", str(f.get("contesto") or ""), re.I):
            if (g := _giorno(f.get("valore"))):
                emissioni.append(g)
    stato.emesso_il = min(emissioni) if emissioni else None
    stato.provvisoriamente_esecutivo = any(
        _RE_NOME_ESECUTIVO.search(str(d.get("nome") or "")) or any(_RE_PROVVISORIA.search(str(f.get("contesto") or "")) for f in _fatti_di(fonti, str(d.get("id") or "")))
        for d in decreti)
    if decreti or stato.emesso_il:
        stato.codice = FASE_NOTIFICA
        quando = f" il {_it(stato.emesso_il)}" if stato.emesso_il else ""
        stato.descrizione = f"decreto ingiuntivo emesso{quando}: da notificare entro sessanta giorni dalla pronuncia (art. 644 c.p.c.)"
        stato.prove.append(f"decreto ingiuntivo{quando}")
    notifiche = sorted(g for f in fonti if f.get("verifica") in UTILI and f.get("campo") == "notifica" and _RE_NOTIFICA_DECRETO.search(str(f.get("contesto") or ""))
                       and (g := _giorno(f.get("valore"))) and (stato.emesso_il is None or g >= stato.emesso_il))
    stato.notificato_il = notifiche[0] if notifiche else None
    esecutorieta = []
    for d in documenti:
        fatti = _fatti_di(fonti, str(d.get("id") or ""))
        if "istanza" in str(d.get("etichetta") or "").lower() or d.get("sezione") in {"atti", "comunicazioni", "notifiche"}:
            continue
        if any(_RE_DICHIARA_ESECUTIVO.search(str(f.get("contesto") or "")) for f in fatti) or re.search(r"decreto\s+di\s+esecutoriet", str(d.get("etichetta") or ""), re.I):
            if (g := _data_del_documento(fatti)):
                esecutorieta.append(g)
    stato.esecutivo_il = min(esecutorieta) if esecutorieta else None
    if stato.notificato_il:
        stato.opposizione_fino_al = termine_opposizione(stato.notificato_il, lavoro=lavoro)
        stato.prove.append(f"notificato il {_it(stato.notificato_il)}")
        if stato.esecutivo_il is None:
            if oggi <= stato.opposizione_fino_al:
                stato.codice = FASE_OPPOSIZIONE
                stato.descrizione = (f"decreto ingiuntivo notificato il {_it(stato.notificato_il)}: termine per l'opposizione fino al "
                                     f"{_it(stato.opposizione_fino_al)} (art. 641 c.p.c.)")
            else:
                stato.codice = FASE_ESECUTORIETA
                stato.descrizione = (f"termine per l'opposizione scaduto il {_it(stato.opposizione_fino_al)} senza opposizione agli atti: "
                                     "chiedere la dichiarazione di esecutorietà (art. 647 c.p.c.)")
    if stato.esecutivo_il or stato.provvisoriamente_esecutivo:
        stato.codice = FASE_ESECUTIVO
        if stato.esecutivo_il:
            stato.descrizione = f"decreto ingiuntivo dichiarato esecutivo il {_it(stato.esecutivo_il)} (art. 647 c.p.c.): titolo esecutivo"
            stato.prove.append(f"dichiarato esecutivo il {_it(stato.esecutivo_il)}")
        else:
            stato.descrizione = "decreto ingiuntivo provvisoriamente esecutivo (art. 642 c.p.c.): titolo esecutivo"
            stato.prove.append("provvisoriamente esecutivo")
    stato.passi = _passi(stato, cliente_ricorrente=cliente_ricorrente, oggi=oggi)
    return stato


def _passi(stato: StatoMonitorio, *, cliente_ricorrente: bool | None, oggi: date) -> list[dict[str, Any]]:
    """Il passo successivo per lo studio, secondo la parte assistita."""
    if cliente_ricorrente is False:
        if stato.codice in {FASE_NOTIFICA, FASE_OPPOSIZIONE} and stato.opposizione_fino_al:
            return [{"urgenza": 1, "azione": f"Valutare l'opposizione al decreto ingiuntivo entro il {_it(stato.opposizione_fino_al)}",
                     "motivo": "quaranta giorni dalla notificazione; con l'opposizione il giudizio segue le norme della cognizione",
                     "entro": _it(stato.opposizione_fino_al), "fonti": ("cpc_641", "cpc_645")}]
        return []
    if stato.codice == FASE_NOTIFICA:
        return [{"urgenza": 1, "azione": "Notificare il decreto ingiuntivo all'ingiunto",
                 "motivo": "il decreto diventa inefficace se non è notificato entro sessanta giorni dalla pronuncia (novanta all'estero)",
                 "entro": "", "fonti": ("cpc_644",)}]
    if stato.codice == FASE_OPPOSIZIONE and stato.opposizione_fino_al:
        return [{"urgenza": 3, "azione": f"Attendere la scadenza del termine di opposizione ({_it(stato.opposizione_fino_al)})",
                 "motivo": "decorso il termine senza opposizione si chiede la dichiarazione di esecutorietà", "entro": "",
                 "fonti": ("cpc_641", "cpc_647")}]
    if stato.codice == FASE_ESECUTORIETA:
        return [{"urgenza": 1, "azione": "Chiedere la dichiarazione di esecutorietà del decreto ingiuntivo",
                 "motivo": f"termine di opposizione scaduto il {_it(stato.opposizione_fino_al)}; istanza anche verbale, con la prova della notificazione",
                 "entro": "", "fonti": ("cpc_647",)}]
    if stato.codice == FASE_ESECUTIVO:
        return [{"urgenza": 1, "azione": "Notificare il precetto fondato sul decreto ingiuntivo esecutivo",
                 "motivo": "non occorre notificare di nuovo il decreto, ma il precetto menziona il provvedimento di esecutorietà"
                 + (f" del {_it(stato.esecutivo_il)}" if stato.esecutivo_il else "") + "; intimazione ad adempiere entro almeno dieci giorni",
                 "entro": "", "fonti": ("cpc_654", "cpc_480", "cpc_474"), "template": "ESE_PRECETTO_ADEMPIMENTO_10GG"}]
    return []


__all__ = [
    "FASE_ESECUTIVO", "FASE_ESECUTORIETA", "FASE_NOTIFICA", "FASE_OPPOSIZIONE", "FASE_OPPOSTO", "FASE_RICORSO",
    "StatoMonitorio", "stato_monitorio", "termine_opposizione",
]
