"""Ricerca del fascicolo a partire dal nome del cliente.

L'avvocato cerca per come chiama le cose: nome e cognome del cliente, non
l'identificativo del fascicolo. Il confronto deve reggere l'ordine invertito
(«Rossi Mario» e «Mario Rossi»), gli accenti, la punteggiatura e le ragioni
sociali, e deve restare deterministico: nessuna corrispondenza approssimata
viene proposta come certa, e chi chiama decide sempre con quale soglia.

Il modulo non conosce Flask ne' la PEC: prende i gestori del dominio e
restituisce candidati ordinati, cosi' che la stessa regola valga per il
presidio PEC, per l'acquisizione documenti e per qualunque altro punto in cui
si debba ricondurre un documento al fascicolo giusto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

SOGLIA_CERTA = 0.86
SOGLIA_PROPOSTA = 0.60
LIMITE_PREDEFINITO = 20


def _testo(valore: Any) -> str:
    if valore is None:
        return ""
    if hasattr(valore, "value"):
        valore = valore.value
    return re.sub(r"\s+", " ", str(valore)).strip()


def campo(oggetto: Any, *nomi: str) -> str:
    """Primo campo valorizzato fra quelli indicati, da oggetto o dizionario."""
    for nome in nomi:
        valore = oggetto.get(nome, "") if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
        testo = _testo(valore)
        if testo:
            return testo
    return ""


def normalizza(valore: Any) -> str:
    """Minuscolo, senza punteggiatura e con spazi singoli: la forma confrontabile."""
    testo = _testo(valore).lower()
    testo = re.sub(r"[\W_]+", " ", testo, flags=re.UNICODE)
    return re.sub(r"\s+", " ", testo).strip()


def parole(valore: Any) -> tuple[str, ...]:
    return tuple(parte for parte in normalizza(valore).split() if parte)


def punteggio_nome(richiesta: Any, candidato: Any) -> float:
    """Somiglianza fra due nomi, indipendente dall'ordine delle parole."""
    parole_richiesta = set(parole(richiesta))
    parole_candidato = set(parole(candidato))
    if not parole_richiesta or not parole_candidato:
        return 0.0
    if parole_richiesta == parole_candidato:
        return 1.0
    comuni = len(parole_richiesta & parole_candidato)
    if not comuni:
        return 0.0
    punteggio = comuni / max(len(parole_richiesta), len(parole_candidato))
    if min(len(parole_richiesta), len(parole_candidato)) >= 2 and (
        parole_richiesta.issubset(parole_candidato) or parole_candidato.issubset(parole_richiesta)
    ):
        punteggio = max(punteggio, 0.86)
    return punteggio


def varianti_cliente(cliente: Any) -> list[str]:
    """Tutti i modi in cui quel cliente puo' essere scritto."""
    nome = campo(cliente, "nome")
    cognome = campo(cliente, "cognome")
    grezze = [
        campo(cliente, "nome_completo", "ragione_sociale", "denominazione"),
        " ".join(parte for parte in (nome, cognome) if parte),
        " ".join(parte for parte in (cognome, nome) if parte),
    ]
    viste: set[str] = set()
    varianti: list[str] = []
    for valore in grezze:
        chiave = normalizza(valore)
        if valore and chiave and chiave not in viste:
            viste.add(chiave)
            varianti.append(valore)
    return varianti


def punteggio_cliente(richiesta: str, cliente: Any) -> float:
    """Miglior somiglianza fra la richiesta e i modi di scrivere quel cliente."""
    diretto = max((punteggio_nome(richiesta, variante) for variante in varianti_cliente(cliente)), default=0.0)
    if diretto >= SOGLIA_CERTA:
        return diretto
    # Ricerca mentre si digita: «ros» deve trovare «Rossi» prima che il nome sia
    # completo, ma vale meno di una corrispondenza per parole intere.
    chiave = normalizza(richiesta)
    if len(chiave) >= 3:
        for variante in varianti_cliente(cliente):
            normalizzata = normalizza(variante)
            if normalizzata.startswith(chiave) or any(parte.startswith(chiave) for parte in normalizzata.split()):
                return max(diretto, SOGLIA_PROPOSTA)
            if chiave in normalizzata:
                return max(diretto, SOGLIA_PROPOSTA - 0.05)
    return diretto


@dataclass(frozen=True)
class CandidatoFascicolo:
    """Un fascicolo proposto per la ricerca, con il perche' e quanto e' sicuro."""

    fascicolo_id: str
    etichetta: str
    numero: str
    titolo: str
    cliente: str
    stato: str
    punteggio: float
    certo: bool

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "value": self.fascicolo_id,
            "label": self.etichetta,
            "numero": self.numero,
            "titolo": self.titolo,
            "cliente": self.cliente,
            "stato": self.stato,
            "punteggio": round(self.punteggio, 4),
            "certo": self.certo,
        }


def _etichetta(fascicolo: Any, cliente: str) -> str:
    numero = campo(fascicolo, "numero")
    titolo = campo(fascicolo, "titolo")
    parti = [parte for parte in (numero, titolo) if parte]
    if cliente:
        parti.append(cliente)
    return " — ".join(parti) or campo(fascicolo, "id")


def cerca_fascicoli(
    fascicoli: Iterable[Any],
    *,
    richiesta: str,
    clienti_per_id: dict[str, Any] | None = None,
    stati_esclusi: Iterable[str] = ("ARCHIVIATO",),
    limite: int = LIMITE_PREDEFINITO,
) -> list[CandidatoFascicolo]:
    """Fascicoli che corrispondono al nome cercato, dal piu' sicuro al meno.

    La corrispondenza si valuta sul cliente del fascicolo — dall'anagrafica
    quando c'e', altrimenti dal nome denormalizzato sul fascicolo — e, in
    subordine, sul numero e sul titolo, perche' l'avvocato a volte cerca «1733»
    o «sfratto Bianchi» invece del nome.
    """
    chiave = normalizza(richiesta)
    if len(chiave) < 2:
        return []
    esclusi = {str(stato).upper() for stato in stati_esclusi}
    clienti_per_id = clienti_per_id or {}
    candidati: list[CandidatoFascicolo] = []
    for fascicolo in fascicoli:
        stato = campo(fascicolo, "stato").upper()
        if stato in esclusi:
            continue
        id_cliente = campo(fascicolo, "id_cliente")
        cliente = clienti_per_id.get(id_cliente)
        nome_cliente = campo(fascicolo, "nome_cliente")
        if cliente is not None:
            punteggio = punteggio_cliente(richiesta, cliente)
            etichetta_cliente = (varianti_cliente(cliente) or [nome_cliente])[0]
        else:
            punteggio = punteggio_cliente(richiesta, {"nome_completo": nome_cliente})
            etichetta_cliente = nome_cliente
        numero = campo(fascicolo, "numero")
        titolo = campo(fascicolo, "titolo")
        for altro in (numero, titolo):
            normalizzato = normalizza(altro)
            if normalizzato and chiave in normalizzato:
                punteggio = max(punteggio, SOGLIA_PROPOSTA - 0.1)
        if punteggio < SOGLIA_PROPOSTA - 0.1:
            continue
        candidati.append(
            CandidatoFascicolo(
                fascicolo_id=campo(fascicolo, "id"),
                etichetta=_etichetta(fascicolo, etichetta_cliente),
                numero=numero,
                titolo=titolo,
                cliente=etichetta_cliente,
                stato=stato,
                punteggio=punteggio,
                certo=punteggio >= SOGLIA_CERTA,
            )
        )
    candidati.sort(key=lambda voce: (-voce.punteggio, voce.numero, voce.etichetta))
    return candidati[: max(1, int(limite or LIMITE_PREDEFINITO))]
