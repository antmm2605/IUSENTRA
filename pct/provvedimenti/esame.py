"""L'esame di un provvedimento del giudice: dal testo alle voci proposte all'avvocato.

Sequenza (ogni passo in un modulo piccolo):

1. ``tipi``: che provvedimento è (catalogo dei documenti + formule del dispositivo);
2. ``materia``: quale rito ne governa i termini;
3. ``dispositivo``: i capi, con chi, che cosa e l'ancora della data;
4. ``udienze``: l'udienza fissata dal provvedimento, altrimenti quella del fascicolo;
5. ``caso_127_ter``: il decreto di trattazione scritta senza data (``pct/note_127_ter``);
6. ``regole``: i termini di legge della tabella versionata, se il giudice non li scrive;
7. ``statuizioni``: i termini che il giudice scrive nel dispositivo;
8. ``verifiche``: preavvisi minimi e riti esclusi.

Solo lettura: nessuna scrittura avviene qui. Le bozze nello scadenziario le crea il
chiamante (``scadenziario.proposte_scadenziario``) con il meccanismo di conferma.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Any

from .caso_127_ter import adatta_note_con_data, esamina_127_ter_senza_data
from .dispositivo import capi
from .materia import RITI_CPC, materia_del_provvedimento
from .modello import EsitoProvvedimento, Voce
from .regole import voci_di_legge
from .riferimenti import Riferimenti
from .statuizioni import rinvii_senza_regola, voci_dei_capi
from .testo import estratto, normalizza
from .tipi import TIPI, riconosci_tipi
from .udienze import MODALITA, udienza_del_fascicolo, udienze_lette
from .verifiche import fuori_ambito, verifiche_preavviso

#: norma della fissazione d'udienza, per rito
_NORME_UDIENZA = {"civile": ("cpc_175",), "lavoro": ("cpc_415",), "famiglia": ("cpc_473bis14",), "penale": ("cpp_552",),
                  "amministrativo": ("cpa_71",), "tributario": ("tu175_art79",)}
_NORME_MODALITA = {"cartolare": ("cpc_127ter",), "da_remoto": ("cpc_127bis",)}


def _prove_tipo(testo: str, tipi: tuple[str, ...]) -> dict[str, str]:
    prove: dict[str, str] = {}
    for tipo in tipi:
        trovato = re.search(TIPI[tipo][1], testo, re.I) if tipo in TIPI else None
        if trovato:
            prove[tipo] = estratto(testo, trovato.start(), trovato.end())
    return prove


def _pronuncia(testo: str) -> date | None:
    from pct.note_127_ter.decreto import riconosci_decreto
    from pct.notifica_ricorso_lavoro import data_di_pronuncia

    giorno = data_di_pronuncia(testo)
    if giorno is None and (decreto := riconosci_decreto(testo)) is not None:
        giorno = decreto.data_pronuncia
    return giorno


def _voci_udienze(lette: list, materia: str) -> list[Voce]:
    voci = []
    for udienza in lette:
        etichetta = MODALITA.get(udienza.modalita, "udienza")
        voci.append(Voce(
            "provvedimento.udienza", "udienza", f"{etichetta[:1].upper()}{etichetta[1:]} del {udienza.giorno:%d/%m/%Y}",
            norme=_NORME_MODALITA.get(udienza.modalita, _NORME_UDIENZA.get(materia, ())), prova=udienza.prova,
            giorno=udienza.giorno, ora=udienza.ora, modalita=udienza.modalita, confidenza=0.9 if udienza.da_capo else 0.75,
            dati=(("Udienza", f"{udienza.giorno:%d/%m/%Y}" + (f" ore {udienza.ora}" if udienza.ora else ""), "provvedimento"),),
        ))
    return voci


def _riferimenti(lette: list, *, oggi: date, comunicata_il: date | None, pronuncia: date | None, pubblicazione: date | None,
                 prove: dict[str, str], fascicolo: dict[str, Any]) -> Riferimenti:
    base = {"oggi": oggi, "comunicata_il": comunicata_il, "pronuncia": pronuncia, "pubblicazione": pubblicazione, "prove_tipo": prove}
    if len(lette) == 1:
        return Riferimenti(udienza=lette[0].giorno, udienza_ora=lette[0].ora, udienza_fonte="provvedimento",
                           udienza_candidate=(lette[0].giorno,), modalita=lette[0].modalita, **base)
    if len(lette) > 1:
        return Riferimenti(udienza_candidate=tuple(u.giorno for u in lette), modalita=lette[0].modalita, **base)
    riferita = udienza_del_fascicolo(oggi=oggi, **fascicolo)
    return Riferimenti(udienza=riferita.giorno, udienza_ora=riferita.ora, udienza_fonte="fascicolo" if riferita.giorno else "",
                       udienza_candidate=riferita.candidate, id_appuntamento=riferita.id_appuntamento, **base)


def _senza_doppioni(voci: list[Voce]) -> list[Voce]:
    viste: set[tuple[str, str, str]] = set()
    uniche = []
    for voce in voci:
        chiave = (voce.regola_id, voce.giorno.isoformat() if voce.giorno else "", voce.codice or voce.titolo)
        if chiave not in viste:
            viste.add(chiave)
            uniche.append(voce)
    return uniche


def esamina_provvedimento(
    testo: str, *, oggi: date, comunicata_il: date | None = None, fascicolo_id: str = "", rg: str = "", ufficio: str = "",
    giudice: str = "", materia: Any = "", prossima_udienza: Any = "", appuntamenti: Iterable[Any] = (),
    scadenze: Iterable[Any] = (), opposizione_proposta: bool = False,
) -> EsitoProvvedimento | None:
    """Le voci proposte dal provvedimento, o None se il testo non è un provvedimento riconosciuto."""
    pulito = normalizza(testo)
    tipi = riconosci_tipi(testo)
    if not tipi:
        return None
    rito = materia_del_provvedimento(testo, dichiarata=materia, ufficio=ufficio, rg=rg)
    scadenze, appuntamenti = list(scadenze or []), list(appuntamenti or [])
    prove = _prove_tipo(pulito, tipi)
    esito = EsitoProvvedimento(tipi=tipi, materia=rito, data_pronuncia=_pronuncia(testo))
    esito.voci.extend(fuori_ambito(tipi, rito, prove, pulito))
    sentenza = "sentenza" in tipi
    capi_letti = [] if sentenza else capi(pulito)
    lette = [] if sentenza else udienze_lette(pulito, capi_letti, oggi=oggi)
    pubblicazione = None
    if sentenza:
        from pct.termine_lungo_sentenza import data_pubblicazione

        pubblicazione = data_pubblicazione(testo)
    fascicolo = {"fascicolo_id": fascicolo_id, "rg": rg, "appuntamenti": appuntamenti, "scadenze": scadenze,
                 "prossima_udienza": prossima_udienza}
    rif = _riferimenti(lette, oggi=oggi, comunicata_il=comunicata_il, pronuncia=esito.data_pronuncia,
                       pubblicazione=pubblicazione, prove=prove, fascicolo=fascicolo if not sentenza else {})
    escludi: set[str] = set()
    salta: frozenset[str] = frozenset()
    if "note_127_ter" in tipi and rito in RITI_CPC:
        voci_127, esito_127 = esamina_127_ter_senza_data(
            testo, oggi=oggi, comunicata_il=comunicata_il, fascicolo_id=fascicolo_id, rg=rg, ufficio=ufficio, giudice=giudice,
            prossima_udienza=prossima_udienza, appuntamenti=appuntamenti, scadenze=scadenze, opposizione_proposta=opposizione_proposta,
        )
        if esito_127 is not None:
            esito.note_127_ter = esito_127
            esito.voci.extend(voci_127)
            escludi.add("civ.127ter.decisione")
            salta = frozenset({"note", "deposito", "notifica"})
    if esito.note_127_ter is None:
        esito.voci.extend(_voci_udienze(lette, rito))
    di_legge, decise, coperti = voci_di_legge(tipi, rito, pulito, capi_letti, rif, escludi=escludi)
    esito.voci.extend(di_legge)
    dai_capi = voci_dei_capi(capi_letti, rif, rito, salta_oggetti=salta, regole_dei_capi=decise, coperti=coperti)
    if "note_127_ter" in tipi and esito.note_127_ter is None:
        dai_capi = adatta_note_con_data(dai_capi, testo=testo, comunicata_il=comunicata_il)
    esito.voci.extend(dai_capi)
    esito.voci.extend(rinvii_senza_regola(capi_letti, esito.voci, rito, salta_oggetti=salta))
    esito.voci.extend(verifiche_preavviso(tipi, rito, rif))
    esito.voci = _senza_doppioni(esito.voci)
    return esito


__all__ = ["esamina_provvedimento"]
