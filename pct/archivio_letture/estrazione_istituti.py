"""Dalla data all'istituto: che cosa impone davvero quel provvedimento.

`estrazione_date` trova una data e la dice ancorata: «termine del 10/09/2026».
Qui quella data viene **qualificata** — deposito di note scritte ex art.
127-ter c.p.c. — e da quella qualificazione nascono i termini che il decreto
impone senza scriverne la data: la notifica trenta giorni prima, la
costituzione dieci giorni prima.

Perché nei motori e non nei presìdi: la qualificazione si legge una volta
sola, insieme alla data, e finisce nell'archivio con la sua norma. Un presidio
che la ricavasse da sé riaprirebbe il testo a ogni richiesta dell'avvocato, e
due presìdi potrebbero qualificare lo stesso decreto in due modi diversi.

I termini derivati non sono di legge in astratto: sono quelli che **il singolo
decreto** impone. Un decreto che non parla della notifica non fa nascere un
termine di notifica, e inventarlo metterebbe in scadenziario una data che
nessun giudice ha imposto.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Iterable

from pct.provvedimenti.calcolo import calcola
from pct.provvedimenti.dispositivo import capi
from pct.provvedimenti.materia import materia_del_provvedimento
from pct.provvedimenti.collettivi import testo_per_il_ruolo
from pct.provvedimenti.termine_scritto import DataLetta, rischio_estinzione, termine_note_127_ter, udienza_tenuta_o_rinviata
from pct.registro_letture.fatti_repository import Fatto

from .istituti_processuali import (
    NOTE_127_TER,
    UDIENZA_127_BIS,
    Istituto,
    cita_127_bis,
    cita_127_ter,
    derivati_da_note,
    derivati_da_udienza_remota,
)

VERSIONE_ESTRAZIONE_ISTITUTI = "2026.09.18.istituti.v1"
#: v2 (10/11/2026): termine scritto dal giudice, perentorietà per legge, rischio di estinzione, cause del ruolo.
VERSIONE_ESTRAZIONE_ISTITUTI_V2 = "2026.11.10.istituti.v2"

#: i campi che possono portare la data di partenza di un istituto
_CAMPI_ANCORA = {"termine", "udienza", "costituzione"}


def _giorno(valore: str) -> date | None:
    from pct.registro_letture.verifica_date import interpreta_data

    return interpreta_data(str(valore or "").split("T")[0])


def _prova_istituto(istituto: Istituto) -> dict[str, str]:
    return {"codice": "istituto", "esito": "ok", "dettaglio": istituto.codice}


def _prova_norma(istituto: Istituto) -> dict[str, str]:
    return {"codice": "norma", "esito": "ok", "dettaglio": istituto.norma}


def _qualifica(fatto: Fatto, istituto: Istituto, giorno: date) -> Fatto:
    """La data letta, con il nome del suo istituto e la norma che lo governa."""
    fatto.campo = istituto.campo
    fatto.etichetta = istituto.etichetta(giorno)
    fatto.contesto = fatto.contesto or istituto.descrizione
    fatto.prove = [p for p in fatto.prove if p.get("codice") not in {"istituto", "norma"}]
    fatto.prove += [_prova_istituto(istituto), _prova_norma(istituto)]
    return fatto


def _derivato(istituto: Istituto, giorno: date, *, origine: str, posizione: int, verifica: str) -> Fatto:
    """Un termine che il decreto impone contandolo dalla data principale."""
    return Fatto(
        categoria="data", campo=istituto.campo, valore=giorno.isoformat(),
        valore_letto="", etichetta=istituto.etichetta(giorno),
        contesto=istituto.descrizione, posizione=posizione, origine=origine,
        confidenza=0.9, verifica=verifica,
        prove=[
            _prova_istituto(istituto), _prova_norma(istituto),
            {"codice": "calcolo", "esito": "ok",
             "dettaglio": f"termine contato dal provvedimento a partire dal {giorno.strftime('%d/%m/%Y')}"},
        ],
    )


def _qualifica_note(elenco: list[Fatto], testo: str) -> Fatto | None:
    """Il fatto che porta il termine per le note: quello scritto dal giudice, non la prima data del testo.

    Regola in ``pct/provvedimenti/termine_scritto.termine_note_127_ter`` (art. 127-ter, primo comma,
    c.p.c.: il giudice «assegna un termine perentorio» per le note). Fino a v1 si prendeva la prima
    data ancorata: «All'udienza del 2.11.2026 tenuta dal G.E. … rinvia all'udienza del 21.12.2026 che
    sostituisce con il deposito di note … entro il termine perentorio del 16.12.2026» faceva diventare
    termine per le note il 02/11 (l'udienza tenuta) e lasciava il 16/12 un «termine» generico
    (collaudo dell'avvocato, Tribunale di Palmi RG 792/2025, 10/11/2026).
    """
    date = [f for f in elenco if f.categoria == "data" and f.campo in _CAMPI_ANCORA and _giorno(f.valore) is not None
            and f.verifica != "respinta"]
    scelta = termine_note_127_ter(testo, [DataLetta(f.posizione, f.posizione + len(f.valore_letto or ""), f.campo) for f in date])
    return date[scelta] if scelta is not None else None



def _nota_antecedente(testo: str, ancora: Fatto, udienza: date) -> tuple[bool, Fatto | None]:
    if ancora.campo != "udienza":
        return False, None
    capi_note = [
        capo for capo in capi(testo)
        if capo.oggetto == "note" and capo.ancora and capo.ancora.tipo == "prima_udienza"
    ]
    if not capi_note:
        return False, None
    chiavi = {(capo.ancora.giorni, capo.ancora.liberi) for capo in capi_note}
    capo = capi_note[0]
    ancora.prove.append({"codice": "udienza_sostituita_distinta", "esito": "ok",
                         "dettaglio": f"Il deposito delle note precede questa udienza: {capo.ancora.letto}"})
    if len(chiavi) != 1:
        return True, None
    giorni, liberi = next(iter(chiavi))
    risultato = calcola(
        {"giorni": giorni, "direzione": "backward", "liberi": liberi, "prudenziale": not liberi},
        udienza, materia=materia_del_provvedimento(testo),
    )
    if risultato is None:
        return True, None
    return True, replace(
        ancora, valore=risultato.giorno.isoformat(), valore_letto=capo.ancora.letto,
        contesto=capo.testo, posizione=capo.inizio,
        prove=[{"codice": "calcolo", "esito": "ok", "dettaglio": risultato.spiegazione}],
    )


def qualifica_istituti(fatti: Iterable[Fatto], testo: str, *, origine: str = "", numero_rg: str = "", anno_rg: str = "") -> list[Fatto]:
    """I fatti con la data qualificata e i termini che ne discendono.

    Se il testo non cita nessuno degli istituti, i fatti tornano come sono: la
    qualificazione non si inventa. Un provvedimento collettivo si legge solo nella
    clausola del gruppo di cause del fascicolo (``pct/provvedimenti/collettivi``).
    """
    elenco = list(fatti)
    testo = testo_per_il_ruolo(str(testo or ""), numero_rg, anno_rg) if numero_rg and anno_rg else str(testo or "")
    per_127_ter = cita_127_ter(testo)
    per_127_bis = cita_127_bis(testo)
    if not per_127_ter and not per_127_bis:
        return elenco

    istituto = NOTE_127_TER if per_127_ter else UDIENZA_127_BIS
    if per_127_ter:
        ancora = _qualifica_note(elenco, testo)
    else:
        ancora = next(
            (f for f in elenco
             if f.categoria == "data" and f.campo in _CAMPI_ANCORA and _giorno(f.valore) is not None and f.verifica != "respinta"
             and not udienza_tenuta_o_rinviata(testo, f.posizione + len(f.valore_letto or ""))),
            None,
        )
    if ancora is None:
        return elenco
    giorno = _giorno(ancora.valore)
    if giorno is None:  # pragma: no cover - gia' filtrato sopra
        return elenco

    udienza = giorno
    if per_127_ter:
        distinta, nota = _nota_antecedente(testo, ancora, giorno)
        if distinta:
            if nota is None:
                return elenco
            elenco.append(nota)
            ancora = nota
            giorno = date.fromisoformat(nota.valore)
    _qualifica(ancora, istituto, giorno)
    if per_127_ter:
        # Il termine per le note è perentorio per legge (art. 127-ter, primo comma, c.p.c.).
        ancora.prove.append({"codice": "perentorieta_documentata", "esito": "ok",
                             "dettaglio": "art. 127-ter, primo comma, c.p.c.: il giudice assegna un termine perentorio per il deposito delle note"})
        rischio = rischio_estinzione(testo)
        if rischio is not None:
            ancora.prove.append({"codice": "rischio_estinzione", "esito": "ok", "dettaglio": rischio.avviso, "norma": rischio.norma})
            ancora.etichetta = f"{istituto.titolo} — {giorno:%d/%m/%Y} — perentorio, {rischio.norma.replace(' c.p.c.', '')}: rischio di estinzione"
        # Lo stesso termine ripetuto nel testo (busta PEC con corpo e allegato, registro e provvedimento):
        # ogni copia è lo stesso adempimento, con lo stesso nome.
        for copia in elenco:
            if copia is not ancora and copia.categoria == "data" and copia.campo == "termine" and copia.verifica != "respinta" \
                    and _giorno(copia.valore) == giorno:
                _qualifica(copia, istituto, giorno)
                copia.etichetta = ancora.etichetta
                copia.prove += [dict(p) for p in ancora.prove if p.get("codice") in {"perentorieta_documentata", "rischio_estinzione"}]
    derivati = derivati_da_note(testo, udienza) if per_127_ter else derivati_da_udienza_remota(testo, giorno)
    posizione = ancora.posizione
    for voce, quando in derivati:
        posizione += 1
        elenco.append(_derivato(voce, quando, origine=origine or ancora.origine,
                                posizione=posizione, verifica=ancora.verifica))
    return elenco


__all__ = ["VERSIONE_ESTRAZIONE_ISTITUTI", "VERSIONE_ESTRAZIONE_ISTITUTI_V2", "qualifica_istituti"]
