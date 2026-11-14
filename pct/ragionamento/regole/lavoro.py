"""Rito del lavoro: la notifica del ricorso e del decreto di fissazione dell'udienza (art. 415 c.p.c.).

Il decreto che «ordina che il ricorso con il pedissequo decreto sia notificato a cura dell'istante nei
termini di legge» rimanda all'art. 415, commi 4–6: notifica entro dieci giorni dalla pronuncia del decreto
(termine ordinatorio) e almeno trenta giorni prima dell'udienza (quaranta se la notifica è all'estero).
L'ordine scritto dal giudice è una fonte certa: non si chiede conferma (G-9). Per le amministrazioni statali
la notifica si fa presso l'Avvocatura dello Stato competente (art. 415, ultimo comma, c.p.c.; art. 11
R.D. 1611/1933). La diffida stragiudiziale e le sue ricevute non sono questa notifica (G-3).
"""

from __future__ import annotations

import re

from pct.notifica_ricorso_lavoro import proposte_art_415

from ..modello import Conclusione, Dubbio
from ..norme import norme
from ..testo import data_it, giorno
from .calcolo import esito as esito_termine
from .contesto import Contesto, chi
from .sentenza import data_pubblicazione


_NON_DEFINITIVA = re.compile(r"\b(?:non\s+definitivament[eo]|sentenza\s+non\s+definitiva)\b", re.I)


def conclusioni_lavoro(ctx: Contesto) -> list[Conclusione]:
    if ctx.rito.codice != "lavoro":
        return []
    decisioni = sorted(
        (data, atto.nome)
        for atto in ctx.della_causa()
        if atto.sentenza and atto.testo and not _NON_DEFINITIVA.search(atto.testo)
        and (data := giorno(data_pubblicazione(atto.testo) or atto.data)) is not None
        and data <= ctx.oggi
    )
    esito: list[Conclusione] = []
    for atto, ordine in ctx.ordini:
        if ordine.codice != "notifica_ordinata" or chi(ordine.onerato, ctx.posizione) not in {"noi", "ignoto"}:
            continue
        udienze = [u for u in ctx.udienze if u.fonte and u.fonte.oggetto_id == atto.id]
        udienza = giorno(udienze[0].data) if udienze else None
        fonti = norme("cpc_415_notifica", "l53_art3bis")
        if ctx.rito.contro_pa:
            fonti += norme("rd1611_art11")
        # La sentenza rende storico l'ordine per quella trattazione. Un decreto
        # successivo, o con udienza ancora successiva, resta da valutare.
        riferimento = max((data for data in (udienza, giorno(atto.data)) if data), default=None)
        decisione = next((
            d for d in decisioni
            if riferimento and (d[0] > riferimento or d[0] == riferimento == udienza)
        ), None)
        if decisione:
            data, nome = decisione
            motivo = f"Il giudice ha poi deciso la causa con «{nome}» del {data_it(data)}."
            esito.append(Conclusione(
                codice="notifica_ricorso_decreto_415", cosa="Ordine di notifica del ricorso e del decreto",
                letto=ordine.fonte, norme=fonti,
                come="Consultare il decreto originario e la sentenza nel fascicolo.",
                perche="L’ordine riguardava la trattazione precedente alla decisione.",
                stato="non_dovuto", prova_o_motivo=motivo, onerato="noi",
                motivo_senza_termine="Adempimento storico. La verifica della notifica resta distinta.",
            ))
            continue
        dubbi = []
        if udienza is None:
            dubbi.append(Dubbio("udienza_ignota", "Il decreto ordina la notifica ma la lettura non trova l'udienza fissata.",
                                "la data d'udienza del decreto", ordine.fonte))
        dubbi.append(Dubbio(
            "destinazione_notifica_ignota",
            "Il termine minimo a difesa dipende da dove deve essere eseguita la notifica.",
            "il destinatario e la destinazione della notifica: Italia (30 giorni) o estero (40 giorni)",
            ordine.fonte,
        ))
        proposta = next(iter(proposte_art_415(atto.testo, udienza=udienza)), None)
        termine = None
        if proposta:
            termine = esito_termine(
                giorno(proposta.due_date), oggi=ctx.oggi, perentorio=proposta.perentorio,
                decorrenza=proposta.dies_a_quo, evento="pronuncia del decreto",
                computo=proposta.note, rito=ctx.rito,
                conseguenze="Verificare il termine minimo a difesa rispetto alla data d'udienza.",
            )
        else:
            dubbi.append(Dubbio(
                "pronuncia_ignota", "Manca una data univoca di pronuncia per il termine ordinatorio.",
                "la data di pronuncia sull'originale del decreto", ordine.fonte,
            ))
        prove_da_verificare = any(set(notifica.atti) & {atto.id, *atto.copie} for notifica in ctx.notifiche)
        if prove_da_verificare:
            dubbi.append(Dubbio(
                "consegna_da_verificare", "Una notifica del decreto risulta dai testi letti.",
                "la ricevuta verificata e correlata al ricorso, al decreto e al destinatario", ordine.fonte,
            ))
        come = "notifica a mezzo PEC con relata (art. 3-bis L. 53/1994) del ricorso con il decreto in calce"
        if ctx.rito.contro_pa:
            come += (", per l'amministrazione statale presso l'Avvocatura dello Stato competente per territorio "
                     "(art. 415, ultimo comma, c.p.c.; art. 11 R.D. 1611/1933)")
        esito.append(Conclusione(
            codice="notifica_ricorso_decreto_415", cosa="Notificare alla controparte il ricorso con il decreto di fissazione dell'udienza",
            letto=ordine.fonte, norme=fonti,
            come=come, perche=("il decreto lo ordina «a cura dell'istante»: senza notifica il contraddittorio non si instaura e "
                               "l'udienza non può tenersi nei confronti del convenuto"),
            stato="dubbio" if prove_da_verificare else "da_fare",
            prova_o_motivo="La consegna va verificata sulle ricevute correlate agli atti e al destinatario.",
            termine=termine, template="builtin-tmp-not-003",
            onerato="noi", dubbi=dubbi,
        ))
    return esito


__all__ = ["conclusioni_lavoro"]
