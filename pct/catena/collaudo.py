"""Collaudo notturno della catena: modello della causa → Lettura → guardiano, con il codice installato.

Il collaudo end-to-end completo (documenti caricati dalla pagina, ciclo delle letture, catalogo, Lettura e guardiano su
uno studio temporaneo) gira nei test e nel gate locale (``tests/test_catena_collaudo_materie.py``). Ogni notte, sul
server, si ripete la parte che decide: fonti scritte come le legge il catalogo, ``ragiona`` → vista della Lettura →
controlli del guardiano su uno scadenziario vuoto o con proposte automatiche. Se una regola del motore o del
guardiano cambia comportamento, il collaudo non è superato e il lavoro lo registra (console Pianificazioni).

Casi con dati fittizi, presi dalle formule dei provvedimenti reali (artt. 127-ter, 415, 416, 631 c.p.c.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from . import guardiano

VERSIONE_COLLAUDO = "2026.11.19.collaudo-catena.v1"
ROMA = ZoneInfo("Europe/Rome")
STUDIO = {"avvocati": ["Avv. Mario Rossi"]}


@dataclass(frozen=True)
class Caso:
    codice: str
    descrizione: str
    fascicolo: dict[str, Any]
    documenti: tuple[dict[str, Any], ...]
    oggi: date
    attese: tuple[tuple[str, str, str], ...]  # (codice incoerenza, riparazione, data) attese
    scadenze: tuple[dict[str, Any], ...] = ()
    studio: dict[str, Any] = field(default_factory=lambda: dict(STUDIO))


def _doc(oid, nome, natura, etichetta, testo, data=""):
    return {"id": oid, "nome": nome, "natura": natura, "etichetta": etichetta, "testo": testo, "data_documento": data}


PIGNORAMENTO = _doc("PIG", "Atto di pignoramento.pdf", "atto_esecutivo", "Atto di pignoramento",
                    "ATTO DI PIGNORAMENTO PRESSO TERZI. L'Associazione Alfa, rappresentata e difesa dall'Avv. Mario Rossi, "
                    "creditrice in forza di decreto ingiuntivo, pignora i crediti della debitrice Beta s.r.l. " * 3)
VERBALE_631 = _doc("V631", "12631033s.pdf", "provvedimento", "Provvedimento dell'ufficio giudiziario",
                   "Tribunale Civile di Palmi\nCancelleria Esecuzioni Mobiliari Proc n.792/2025\nAll'udienza del 2.11.2026 "
                   "tenuta dal G.E. dott. Bianchi, viene chiamata la causa iscritta al n.792/2025 R.G.E. tra ASSOCIAZIONE ALFA "
                   "contro BETA Srl\nIl G.E\nPoiche' nessuno e' presente rinvia all'udienza del 21.12.2026 che sostituisce con il "
                   "deposito di note scritte ex art.127 ter c.p.c. entro il termine perentorio del\n16.12.2026. Ai sensi "
                   "dell'art.631 c.p.c.\nSi comunichi\nIl Giudice O.T.")
RICORSO_LAVORO = _doc("RIC", "Ricorso.pdf", "atto_principale", "Ricorso in materia di lavoro (art. 414 c.p.c.)",
                      "TRIBUNALE DI VICENZA RICORSO EX ART. 414 C.P.C. La prof.ssa Gialli Anna, rappresentata e difesa "
                      "dall'Avv. Mario Rossi, ricorre contro il MINISTERO DELL'ISTRUZIONE E DEL MERITO. " * 3)
DECRETO_415 = _doc("DEC", "4194926s.pdf", "provvedimento", "Decreto di fissazione udienza",
                   "TRIBUNALE ORDINARIO di VICENZA SEZIONE PRIMA DECRETO FISSAZIONE Il Giudice del Lavoro, letto il ricorso che "
                   "precede, visto l'art. 415, commi 2 e 3, c.p.c. FISSA la comparizione delle parti dinanzi a sé per l'udienza "
                   "del 09/02/2027; Dispone che la trattazione dell'udienza sia sostituita dallo scambio di note scritte da "
                   "depositarsi nel termine perentorio del giorno dell'udienza fissata, entro le ore 14.00 ex art. 127 ter c.p.c.. "
                   "ORDINA che il ricorso con il pedissequo decreto sia notificato a cura dell'istante alla controparte nei "
                   "termini di legge. Si avverte che il convenuto ha l'onere di costituirsi in cancelleria, a pena di decadenza, "
                   "almeno dieci giorni prima dell'udienza come sopra fissata.\n\nVicenza, 09/10/2026 Il Giudice del Lavoro")
ESECUZIONE = {"id": "C1", "numero_rg": "792", "anno_rg": "2025", "codice_oggetto_pst": "510002", "tipo": "CIVILE",
              "tribunale": "Tribunale di Palmi"}
LAVORO = {"id": "C2", "numero_rg": "1571", "anno_rg": "2026", "codice_oggetto_pst": "222050", "tipo": "LAVORO",
          "controparte": "Ministero dell'Istruzione e del Merito", "tribunale": "Tribunale di Vicenza"}
RICORSO_DI = _doc("RDI", "Ricorso per decreto ingiuntivo.pdf", "atto_principale", "Ricorso per decreto ingiuntivo",
                  "GIUDICE DI PACE DI PALMI RICORSO PER DECRETO INGIUNTIVO L'Associazione Alfa, rappresentata dall'Avv. Mario Rossi. " * 3)
DECRETO_DI = _doc("DI", "accoglimentoDecretoIngiuntivo.pdf", "provvedimento", "Decreto ingiuntivo",
                  "Decreto ingiuntivo n. 1109/2026 RG n. 4202/2026\nUFFICIO DEL GIUDICE DI PACE DI PALMI DECRETO INGIUNTIVO Il "
                  "Giudice di Pace, letto il ricorso depositato da ASSOCIAZIONE ALFA-Avv. MARIO ROSSI; INGIUNGE a BETA S.R.L. di "
                  "pagare entro quaranta giorni dalla notifica la somma di € 2.400,00. AVVERTE la parte ingiunta che può proporre "
                  "opposizione nel termine perentorio di quaranta giorni dalla notifica. Si comunichi. PALMI, 20-11-2026")
MONITORIO = {"id": "C3", "numero_rg": "4202", "anno_rg": "2026", "codice_oggetto_pst": "010001", "tipo": "CIVILE",
             "tribunale": "Giudice di Pace di Palmi"}
PROPOSTA_COSTITUZIONE = {"id": "P1", "titolo": "Costituzione del convenuto con memoria difensiva", "data": "2027-01-29",
                         "stato": "BOZZA", "note": "PEC_TERMINE_PROPOSTO:x:LAV_416_COSTITUZIONE"}

CASI: tuple[Caso, ...] = (
    Caso("esecuzione_631", "Rinvio per diserzione con note scritte: termine perentorio del 16/12/2026 nello scadenziario, "
         "udienza sostituita del 21/12/2026 in agenda (artt. 127-ter e 631 c.p.c.)", ESECUZIONE, (PIGNORAMENTO, VERBALE_631),
         date(2026, 11, 10), (("termine_certo_senza_scadenza", guardiano.CREA_SCADENZA, "2026-12-16"),
                              ("udienza_non_in_agenda", guardiano.CREA_UDIENZA, "2026-12-21"))),
    Caso("lavoro_415", "Rito del lavoro contro la P.A.: la proposta di costituzione del convenuto è un termine della "
         "controparte e si scarta (art. 416 c.p.c.)", LAVORO, (RICORSO_LAVORO, DECRETO_415), date(2026, 11, 10),
         # Notifica di ricorso e decreto all'Avvocatura dello Stato almeno trenta giorni prima dell'udienza (art. 415,
         # commi 4-5, c.p.c.: 08/01/2027, anticipato dal sabato 09/01 e dalla domenica 10/01); note scritte nel giorno
         # dell'udienza sostituita (art. 127-ter c.p.c.); udienza in agenda.
         (("termine_della_controparte", guardiano.SCARTA_BOZZA, "2027-01-29"),
          ("termine_certo_senza_scadenza", guardiano.CREA_SCADENZA, "2027-01-08"),
          ("termine_certo_senza_scadenza", guardiano.CREA_SCADENZA, "2027-02-09"),
          ("udienza_non_in_agenda", guardiano.CREA_UDIENZA, "2027-02-09")), scadenze=(PROPOSTA_COSTITUZIONE,)),
    Caso("monitorio_644", "Decreto ingiuntivo dello studio: sessanta giorni dalla pronuncia del 20/11/2026 per notificarlo, "
         "termine certo anche senza conoscere il luogo della notifica (art. 644 c.p.c.)", MONITORIO, (RICORSO_DI, DECRETO_DI),
         date(2026, 11, 25), (("termine_certo_senza_scadenza", guardiano.CREA_SCADENZA, "2027-01-19"),)),
    Caso("studio_senza_avvocati", "Senza il nome dell'avvocato nelle Impostazioni la parte onerata non è certa: nessuna "
         "scrittura, un avviso", ESECUZIONE, (PIGNORAMENTO, VERBALE_631), date(2026, 11, 10),
         # L'udienza fissata non dipende dalla parte onerata: resta da mettere in agenda.
         (("studio_senza_avvocati", "", ""), ("udienza_non_in_agenda", guardiano.CREA_UDIENZA, "2026-12-21")),
         studio={"avvocati": []}),
)


def _lettura(caso: Caso) -> dict[str, Any]:
    from pct.fascicolo_lettura.ragionamento import passi, vista
    from pct.ragionamento import FontiCausa, ragiona

    causa = ragiona(FontiCausa(fascicolo=dict(caso.fascicolo), studio=dict(caso.studio), documenti=[dict(d) for d in caso.documenti],
                               scadenze=[dict(s) for s in caso.scadenze], oggi=caso.oggi)).come_dizionario()
    return {"ragionamento": vista(causa), "prossimi_passi": [{"azione": p.azione} for p in passi(causa)]}


def esegui_caso(caso: Caso, *, lettura: Callable[[Caso], dict[str, Any]] = _lettura) -> dict[str, Any]:
    try:
        stato = guardiano.StatoFascicolo(fascicolo_id=caso.fascicolo["id"], oggi=caso.oggi, lettura=lettura(caso),
                                         scadenze=[dict(s) for s in caso.scadenze],
                                         studio_con_avvocati=bool(caso.studio.get("avvocati")))
        trovate = [(i.codice, i.riparazione, str(i.dati.get("data") or "")) for i in guardiano.controlla(stato)]
    except Exception as exc:  # un caso guasto è un collaudo non superato, mai un lavoro che si ferma
        return {"codice": caso.codice, "superato": False, "errore": f"{type(exc).__name__}: {exc}"[:300]}
    attese = [tuple(a) for a in caso.attese]
    mancanti = [a for a in attese if a not in trovate]
    inattese = [t for t in trovate if t not in attese]
    return {"codice": caso.codice, "descrizione": caso.descrizione, "superato": not mancanti and not inattese,
            "mancanti": mancanti, "inattese": inattese}


def esegui_collaudo(casi: tuple[Caso, ...] = CASI) -> dict[str, Any]:
    from pct.fascicolo_lettura import VERSIONE_LETTURA
    from pct.ragionamento import VERSIONE

    esiti = [esegui_caso(caso) for caso in casi]
    corretti = sum(1 for e in esiti if e["superato"])
    return {"versione": VERSIONE_COLLAUDO, "guardiano": guardiano.VERSIONE, "ragionamento": VERSIONE,
            "lettura": VERSIONE_LETTURA, "eseguito_il": datetime.now(ROMA).isoformat(timespec="seconds"),
            "superato": bool(esiti) and corretti == len(esiti), "corretti": corretti, "totali": len(esiti), "casi": esiti}


__all__ = ["CASI", "Caso", "VERSIONE_COLLAUDO", "esegui_caso", "esegui_collaudo"]
