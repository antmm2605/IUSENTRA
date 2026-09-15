"""La consegna: l'archivio dà il fatto al presidio, il presidio scrive e conferma.

È l'atto che chiude la catena. I due motori leggono e scrivono i fatti
nell'archivio; l'archivio sa quali presìdi usano quali fatti; qui glieli
consegna. Il presidio che ha un registro proprio — lo scadenziario, l'agenda —
ci scrive una riga e **conferma** indicando quale riga ha creato. Da quel
momento l'archivio non gli ripropone più quel fatto: niente doppioni, e il
giro si ferma.

Tre esiti, tutti dichiarati, nessuno silenzioso:

- **consegnato**: il presidio ha scritto la riga, e il riferimento la ritrova;
- **non pertinente**: il presidio ha guardato e non la scrive, perché quel dato
  è già nel suo registro (una scadenza per quella data esiste già) o perché non
  lo riguarda. Non torna più;
- **rifiutato**: il presidio non è riuscito a scriverla. Il motivo resta e al
  giro successivo si riprova.

Si consegnano solo i fatti che il collaudo ha **verificato** o che l'avvocato
ha **corretto**: una data soltanto plausibile non finisce nello scadenziario
senza che nessuno l'abbia confermata, si chiede nel riquadro delle conferme.

Base normativa delle scadenze create: le stesse del fatto d'origine (termini
processuali del c.p.c. e del D.Lgs. 149/2022); la riga creata resta una
proposta da confermare, non un termine calcolato d'ufficio.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pct.archivio_letture.distribuzione import PRESIDI_CHE_SCRIVONO, fatti_per_presidio
from pct.registro_letture import RegistroLetture

logger = logging.getLogger(__name__)

# Le scadenze e gli appuntamenti nati da una lettura si riconoscono da questa
# etichetta: l'avvocato deve poter vedere che cosa ha scritto il software.
ORIGINE = "archivio delle letture"
NOTA_CONSEGNA = "Creata dalla lettura automatica dei documenti: da confermare."


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _giorno(valore: Any) -> str:
    giorno = _testo(valore)[:10]
    if len(giorno) == 10 and giorno[4] == "-" and giorno[7] == "-":
        try:
            date.fromisoformat(giorno)
        except ValueError:
            return ""
        return giorno
    return ""


def _ora(fatto: Any) -> str:
    """L'ora letta insieme alla data, se il motore l'ha trovata: «2026-11-10T09:30»."""
    valore = _testo(getattr(fatto, "valore", ""))
    return valore[11:16] if len(valore) >= 16 and valore[10] == "T" else ""


# ---- scadenziario ----------------------------------------------------------

def _consegna_scadenziario(fascicolo: Any, fatti: list[Any]) -> list[dict[str, str]]:
    """Ogni termine letto diventa una scadenza, se non c'è già per quel giorno."""
    from pct.scadenziario import TipoTermine
    from web.helpers import get_scadenziario

    gestore = get_scadenziario()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    esistenti = {
        _giorno(getattr(scadenza, "data_scadenza", ""))
        for scadenza in gestore.tutte(id_fascicolo=fascicolo_id, solo_aperte=False)
    }
    esiti: list[dict[str, str]] = []
    for fatto in fatti:
        giorno = _giorno(getattr(fatto, "valore", ""))
        if not giorno:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": "il fatto non porta una data di calendario"})
            continue
        if giorno in esistenti:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": f"una scadenza per il {giorno} è già nel fascicolo"})
            continue
        titolo = _testo(getattr(fatto, "etichetta", "")) or "Termine letto dai documenti"
        try:
            scadenza = gestore.nuova(
                titolo=titolo[:120],
                tipo=TipoTermine.TERMINE_PERENTORIO if _testo(getattr(fatto, "campo", "")) == "termine" else TipoTermine.ADEMPIMENTO,
                data_scadenza=giorno,
                id_fascicolo=fascicolo_id,
                descrizione=_testo(getattr(fatto, "contesto", ""))[:300],
                note=NOTA_CONSEGNA,
            )
        except Exception as exc:
            esiti.append({"fatto_id": fatto.id, "stato": "rifiutato", "motivo": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        esistenti.add(giorno)
        esiti.append({"fatto_id": fatto.id, "stato": "consegnato", "riferimento": _testo(getattr(scadenza, "id", ""))})
    return esiti


# ---- agenda ----------------------------------------------------------------

def _procedimento(fascicolo: Any) -> str:
    """Il riferimento con cui l'agenda lega un impegno al fascicolo: il numero di ruolo.

    L'appuntamento non ha un campo «fascicolo»: il legame passa dal campo
    `procedimento`, dove lo studio scrive «RG numero/anno».
    """
    numero = _testo(getattr(fascicolo, "numero_rg", ""))
    anno = _testo(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        return f"RG {numero}/{anno}"
    return _testo(getattr(fascicolo, "numero", "")) or _testo(getattr(fascicolo, "titolo", ""))[:60]


def _consegna_agenda(fascicolo: Any, fatti: list[Any]) -> list[dict[str, str]]:
    """Ogni udienza letta diventa un appuntamento, se non c'è già per quel giorno."""
    from pct.agenda import TipoAppuntamento
    from web.helpers import get_agenda

    gestore = get_agenda()
    procedimento = _procedimento(fascicolo)
    esistenti = {
        _giorno(getattr(appuntamento, "data_ora", ""))
        for appuntamento in gestore.tutti()
        if procedimento and procedimento in _testo(getattr(appuntamento, "procedimento", ""))
    }
    esiti: list[dict[str, str]] = []
    for fatto in fatti:
        giorno = _giorno(getattr(fatto, "valore", ""))
        if not giorno:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": "il fatto non porta una data di calendario"})
            continue
        if giorno in esistenti:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": f"un impegno del {giorno} è già in agenda per questo procedimento"})
            continue
        ora = _ora(fatto) or "09:00"
        try:
            appuntamento = gestore.aggiungi(
                titolo=(_testo(getattr(fatto, "etichetta", "")) or "Udienza letta dai documenti")[:120],
                tipo=TipoAppuntamento.UDIENZA,
                data_ora=f"{giorno}T{ora}:00",
                luogo=_testo(getattr(fascicolo, "tribunale", "")),
                allow_overlap=True,
                procedimento=procedimento,
                tribunale=_testo(getattr(fascicolo, "tribunale", "")),
                cliente=_testo(getattr(fascicolo, "nome_cliente", "")),
                id_cliente=_testo(getattr(fascicolo, "id_cliente", "")),
                note=NOTA_CONSEGNA,
            )
        except Exception as exc:
            esiti.append({"fatto_id": fatto.id, "stato": "rifiutato", "motivo": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        esistenti.add(giorno)
        esiti.append({"fatto_id": fatto.id, "stato": "consegnato", "riferimento": _testo(getattr(appuntamento, "id", ""))})
    return esiti


CONSEGNATARI = {"scadenziario": _consegna_scadenziario, "agenda": _consegna_agenda}


# ---- il giro di consegna ----------------------------------------------------

def consegna_fascicolo(fascicolo: Any, *, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Consegna ai presìdi i fatti che spettano loro e non hanno ancora preso.

    Non rilegge nulla: prende i fatti dall'archivio, chiede al presidio di
    scriverli, registra la conferma. A consegne chiuse questa funzione non ha
    più niente da fare e il giro si ferma.
    """
    from web.services.archivio_letture_runtime import fatti_fascicolo
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    esito: dict[str, Any] = {"fascicolo_id": fascicolo_id, "presidi": {}, "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
    if not fascicolo_id:
        return esito
    tutti = fatti_fascicolo(fascicolo, verifiche=None)
    for presidio in PRESIDI_CHE_SCRIVONO:
        spettanti = fatti_per_presidio(tutti, presidio.nome)
        da_prendere = registro.da_consegnare(tenant, fascicolo_id, presidio.nome, spettanti)
        if not da_prendere:
            esito["presidi"][presidio.nome] = {"spettanti": len(spettanti), "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
            continue
        consegnatario = CONSEGNATARI.get(presidio.nome)
        if consegnatario is None:
            continue
        try:
            risultati = consegnatario(fascicolo, da_prendere)
        except Exception as exc:
            # Il presidio non ha potuto lavorare: i fatti restano da consegnare
            # e il motivo si registra su ciascuno, così si riprova al giro dopo.
            logger.exception("Consegna al presidio %s non riuscita per il fascicolo %s", presidio.nome, fascicolo_id)
            risultati = [{"fatto_id": fatto.id, "stato": "rifiutato", "motivo": f"{type(exc).__name__}: {exc}"[:200]} for fatto in da_prendere]
        conteggi = {"spettanti": len(spettanti), "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
        for riga in risultati:
            stato = str(riga.get("stato") or "rifiutato")
            try:
                registro.segna_consegna(
                    tenant, fascicolo_id, str(riga.get("fatto_id") or ""), presidio.nome,
                    stato=stato, riferimento=str(riga.get("riferimento") or ""),
                    motivo=str(riga.get("motivo") or ""), versione_presidio=presidio.versione,
                )
            except Exception as exc:
                logger.debug("Conferma di consegna non registrata (%s): %s", presidio.nome, exc)
                continue
            chiave = {"consegnato": "consegnati", "non_pertinente": "non_pertinenti", "rifiutato": "rifiutati"}.get(stato, "rifiutati")
            conteggi[chiave] += 1
            esito[chiave] += 1
        esito["presidi"][presidio.nome] = conteggi
    if esito["consegnati"]:
        from web.services.lettura_cache import invalida_lettura

        invalida_lettura(fascicolo_id)
    return esito


__all__ = ["CONSEGNATARI", "NOTA_CONSEGNA", "ORIGINE", "consegna_fascicolo"]
