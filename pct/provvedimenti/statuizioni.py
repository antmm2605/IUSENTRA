"""Ciò che il giudice scrive nel dispositivo, voce per voce.

Ogni capo con una data diventa una voce (``giudice.<oggetto>``) con la prova del capo:

* data esplicita → termine a quella data (un capo può assegnarne più d'una: ognuna
  con il suo soggetto, l'ultimo nominato prima della data);
* «N giorni prima dell'udienza» o «sino alla data dell'udienza» → contato dall'udienza
  (del provvedimento o, se una sola, del fascicolo) con il motore dei termini;
* «N giorni dalla comunicazione / pronuncia» → contato da quella data, se nota;
* senza decorrenza → bozza alla data più anticipata (dalla pronuncia o dalla comunicazione), con la
  decorrenza da confermare;
* dalla notificazione, da un deposito futuro o con più udienze possibili → domanda all'avvocato
  (``da_verificare``): nessuna data indovinata;
* «AVVISA che … sarà adottato entro N giorni dalla scadenza» → che cosa aspettarsi.

Se il capo fissa un termine che la legge già prevede (es. costituzione del convenuto),
la voce prende codice e norme della regola di legge: il termine resta quello del giudice.
Norma di base: art. 175 c.p.c. (il giudice fissa i termini per gli atti) nel rito civile.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .ancore import ancore_esplicite
from .calcolo import calcola
from .dispositivo import Capo, chi_e_oggetto
from .modello import Voce
from .riferimenti import Riferimenti

PREFISSO = "giudice."
NORME_RITO = {"civile": ("cpc_175",), "lavoro": ("cpc_175",), "famiglia": ("cpc_175",), "penale": (),
              "amministrativo": ("cpa_71",), "tributario": ("tu175_art79",)}
_TIPO_TERMINE = {"note": "DEPOSITO_MEMORIA", "memoria": "DEPOSITO_MEMORIA", "notifica": "NOTIFICA", "pagamento": "PAGAMENTO",
                 "deposito": "DEPOSITO_ATTO", "costituzione": "DEPOSITO_ATTO", "relazione": "ADEMPIMENTO", "giuramento": "ADEMPIMENTO"}
_ETICHETTE = {"note": "deposito delle note", "memoria": "deposito della memoria", "notifica": "notifica",
              "pagamento": "pagamento", "deposito": "deposito", "costituzione": "costituzione in giudizio",
              "relazione": "relazione e osservazioni sulla consulenza", "giuramento": "giuramento del consulente",
              "comparizione": "comparizione"}
_VERBI_INCARICO = frozenset({"invita", "onera", "ordina"})
_OGGETTI_INCARICO = frozenset({"notifica", "deposito", "pagamento", "note", "memoria"})
_PARTI = frozenset({"ricorrente", "resistente", "attore", "opponente", "parti"})
_RE_MOTIVAZIONE = re.compile(r"\bdeposito\s+della\s+motivazione\b|\bmotivazione\s+(?:della\s+sentenza\s+)?(?:sarà|verrà)\s+depositata\b", re.I)
_RE_ATTESA = re.compile(r"\b(?:provvedimento|decisione|decider\w*|sentenza|provveder\w*|adottat\w*)\b", re.I)


def _titolo(capo: Capo) -> str:
    cosa = _ETICHETTE.get(capo.oggetto, "adempimento")
    chi = f" ({capo.chi})" if capo.chi else ""
    return f"Termine assegnato dal giudice: {cosa}{chi}"


def _voce(capo: Capo, materia: str, regola: dict[str, Any] | None = None, **campi: Any) -> Voce:
    oggetto = capo.oggetto or "termine"
    perentorio = capo.perentorio if capo.perentorio is not None or regola is None else regola.get("perentorio")
    tipo = _TIPO_TERMINE.get(capo.oggetto) or ("TERMINE_PERENTORIO" if perentorio else "TERMINE_ORDINATORIO" if perentorio is False else "ADEMPIMENTO")
    base: dict[str, Any] = {
        "regola_id": PREFISSO + oggetto, "genere": "termine", "titolo": _titolo(capo), "norme": NORME_RITO.get(materia, ()),
        "prova": capo.testo[:300], "confidenza": 0.8, "chi": capo.chi, "perentorio": perentorio,
        "codice": f"PROVV_{oggetto.upper()}", "tipo_termine": tipo, "scadenziario": True,
    }
    if regola is not None:
        base.update(titolo=f"{regola['titolo']} — termine assegnato dal giudice", norme=tuple(regola.get("norme", ())),
                    codice=str(regola.get("codice") or base["codice"]), tipo_termine=str(regola.get("tipo_termine") or tipo),
                    chi=capo.chi or str(regola.get("chi") or ""))
    base.update(campi)
    return Voce(**base)


def _domanda(capo: Capo, materia: str, testo: str, regola: dict[str, Any] | None = None) -> Voce:
    return _voce(capo, materia, regola, genere="da_verificare", domanda=testo, scadenziario=False, confidenza=0.5)


def voce_del_capo(capo: Capo, rif: Riferimenti, materia: str, regola: dict[str, Any] | None = None) -> Voce | None:
    ancora = capo.ancora
    if ancora is None and capo.verbo in _VERBI_INCARICO and capo.oggetto in _OGGETTI_INCARICO and capo.chi in _PARTI:
        # «Invita parte ricorrente a depositare la prova della notificazione»: un incarico senza data resta un adempimento.
        return _voce(capo, materia, regola, genere="adempimento", scadenziario=False, confidenza=0.7,
                     titolo=f"Adempimento chiesto dal giudice: {_ETICHETTE.get(capo.oggetto, 'adempimento')} ({capo.chi})")
    if ancora is None or ancora.tipo in {"udienza_esplicita", "per_rinvio"}:
        return None
    if ancora.tipo == "esplicita":
        if ancora.giorno is None:
            return None
        if ancora.giorno < rif.oggi:
            return _voce(capo, materia, regola, genere="verifica", giorno=ancora.giorno, scadenziario=False,
                         titolo=f"{_titolo(capo)}: data già passata ({ancora.giorno:%d/%m/%Y}), verificare")
        return _voce(capo, materia, regola, giorno=ancora.giorno, ora=ancora.ora,
                     dati=(("Data scritta nel provvedimento", ancora.letto, "dispositivo"),))
    if ancora.tipo in {"prima_udienza", "fino_udienza"}:
        if rif.udienza is None:
            return _domanda(capo, materia, rif.domanda_udienza(_titolo(capo)), regola)
        if ancora.tipo == "fino_udienza":
            return _voce(capo, materia, regola, giorno=rif.udienza, dati=(rif.dato_udienza(),), dies_a_quo=rif.udienza,
                         id_appuntamento=rif.id_appuntamento)
        calcolo = calcola({"giorni": ancora.giorni, "direzione": "backward", "liberi": ancora.liberi,
                           "prudenziale": not ancora.liberi}, rif.udienza, materia=materia)
        if calcolo is None:
            return _domanda(capo, materia, f"{_titolo(capo)}: «{ancora.letto}» non è calcolabile con certezza, indicarne la data.", regola)
        return _voce(capo, materia, regola, giorno=calcolo.giorno, calcolo=calcolo.spiegazione, dati=(rif.dato_udienza(),),
                     dies_a_quo=rif.udienza, id_appuntamento=rif.id_appuntamento)
    if ancora.tipo == "da_evento":
        return _da_evento(capo, rif, materia, regola)
    return _senza_decorrenza(capo, rif, materia, regola)


def _senza_decorrenza(capo: Capo, rif: Riferimenti, materia: str, regola: dict[str, Any] | None) -> Voce:
    """«Termine di 10 giorni» senza decorrenza: bozza alla data più anticipata possibile, da confermare.

    Si conta dal primo giorno certo tra la data in calce al provvedimento e la sua comunicazione (art. 176, co. 2,
    c.p.c.: le ordinanze fuori udienza si comunicano): la scadenza proposta non è mai successiva a quella vera.
    Senza alcuna data certa resta la domanda all'avvocato.
    """
    ancora = capo.ancora
    letto = ancora.letto if ancora is not None else ""
    certi = [(dies, dato) for dies, dato in (rif.dato_evento("pronuncia"), rif.dato_evento("comunicazione")) if dies is not None]
    calcolo = None
    if certi and ancora is not None and ancora.giorni:
        dies, dato = min(certi, key=lambda coppia: coppia[0])
        calcolo = calcola({"giorni": ancora.giorni, "direzione": "forward"}, dies, materia=materia)
    if calcolo is None:
        return _domanda(capo, materia, f"Il giudice assegna «{letto}» senza dire da quando decorrono: indicare la decorrenza.", regola)
    domanda = (f"Il giudice assegna «{letto}» senza dire da quando decorrono: la data è contata dal {dies:%d/%m/%Y}, "
               "il giorno certo più anticipato. Confermare la decorrenza.")
    return _voce(capo, materia, regola, giorno=calcolo.giorno, calcolo=calcolo.spiegazione, dati=(dato,), dies_a_quo=dies,
                 domanda=domanda, nota=f"Decorrenza da confermare: {domanda}", confidenza=0.6)


def _da_evento(capo: Capo, rif: Riferimenti, materia: str, regola: dict[str, Any] | None) -> Voce:
    ancora = capo.ancora
    if ancora is None:  # pragma: no cover - filtrato dal chiamante
        return _domanda(capo, materia, _titolo(capo), regola)
    if ancora.evento == "scadenza" and capo.verbo in {"avvisa", "avverte"} and _RE_ATTESA.search(capo.testo):
        return _voce(capo, materia, None, genere="attesa", scadenziario=False, codice="", chi="giudice",
                     titolo=f"Provvedimento del giudice atteso entro {ancora.giorni} giorni dalla scadenza del termine")
    dies, dato = rif.dato_evento(ancora.evento)
    if dies is None:
        return _domanda(capo, materia, Riferimenti.domanda_evento(ancora.evento, _titolo(capo)), regola)
    calcolo = calcola({"giorni": ancora.giorni, "direzione": "forward"}, dies, materia=materia)
    if _RE_MOTIVAZIONE.search(capo.testo) and calcolo is not None:
        # «Fissa per il deposito della motivazione il termine di 60 giorni»: è il giudice che deposita
        # (art. 429 c.p.c. nel lavoro); dal deposito decorrono i termini di impugnazione, non da qui.
        return _voce(capo, materia, None, genere="attesa", scadenziario=False, codice="", chi="giudice", giorno=calcolo.giorno,
                     norme=("cpc_429",) if materia == "lavoro" else NORME_RITO.get(materia, ()), calcolo=calcolo.spiegazione,
                     dati=(dato,), dies_a_quo=dies,
                     titolo=f"Motivazione del giudice attesa entro il {calcolo.giorno:%d/%m/%Y}: dal deposito decorrono i termini di impugnazione")
    if calcolo is None:
        return _domanda(capo, materia, f"{_titolo(capo)}: «{ancora.letto}» non è calcolabile con certezza, indicarne la data.", regola)
    return _voce(capo, materia, regola, giorno=calcolo.giorno, calcolo=calcolo.spiegazione, dati=(dato,), dies_a_quo=dies)


def segmenti(capo: Capo) -> list[Capo]:
    """Un capo con più date esplicite diventa un capo per data, ciascuno con il suo soggetto."""
    esplicite = ancore_esplicite(capo.testo)
    if len(esplicite) < 2:
        return [capo]
    pezzi = []
    for indice, (ancora, inizio, _fine) in enumerate(esplicite):
        da = esplicite[indice - 1][2] if indice else 0
        a = esplicite[indice + 1][1] if indice + 1 < len(esplicite) else len(capo.testo)
        testo = capo.testo[da:a]
        chi, oggetto = chi_e_oggetto(testo, inizio - da)
        pezzi.append(replace(capo, testo=testo.strip(" ,;"), inizio=capo.inizio + da, chi=chi or capo.chi,
                             oggetto=oggetto or capo.oggetto, ancora=ancora))
    return pezzi


def voci_dei_capi(capi_letti: list[Capo], rif: Riferimenti, materia: str, *, salta_oggetti: frozenset[str] = frozenset(),
                  regole_dei_capi: dict[int, dict[str, Any]] | None = None, coperti: frozenset[int] = frozenset()) -> list[Voce]:
    regole_dei_capi = regole_dei_capi or {}
    voci: list[Voce] = []
    for capo in capi_letti:
        if capo.oggetto in salta_oggetti or capo.inizio in coperti:
            continue
        for pezzo in segmenti(capo):
            voce = voce_del_capo(pezzo, rif, materia, regole_dei_capi.get(capo.inizio))
            if voce is not None:
                voci.append(voce)
    return voci


def rinvii_senza_regola(capi_letti: list[Capo], voci: list[Voce], materia: str, *, salta_oggetti: frozenset[str] = frozenset()) -> list[Voce]:
    """«Termini di cui all'art. X» senza una regola di legge che li calcoli: si chiede."""
    coperte = re.sub(r"[^a-z0-9]", "", " ".join(v.regola_id for v in voci).lower())
    domande = []
    for capo in capi_letti:
        ancora = capo.ancora
        if capo.oggetto in salta_oggetti or ancora is None or ancora.tipo != "per_rinvio" or ancora.norma.replace(".", "") in coperte:
            continue
        domande.append(_domanda(capo, materia, f"Il giudice rinvia ai termini dell'art. {ancora.norma}: indicare le scadenze."))
    return domande


__all__ = ["NORME_RITO", "PREFISSO", "rinvii_senza_regola", "segmenti", "voce_del_capo", "voci_dei_capi"]
