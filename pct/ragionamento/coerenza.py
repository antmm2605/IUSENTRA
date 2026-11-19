"""I controlli di coerenza del modello: ogni contraddizione si scioglie con le fonti o diventa un dubbio dichiarato.

Controlli (uno per regola, con la ragione):
1. un termine non è un'udienza: per le note scritte vale il termine assegnato (art. 127-ter c.p.c.), l'udienza
   sostituita è un'altra data (G-1, G-9);
2. il termine di un'altra parte non è nostro (art. 416 c.p.c. per il convenuto; G-6);
3. una data anteriore all'atto che la fa decorrere è un errore materiale, non un termine (G-11);
4. un «pagato» richiede la prova dell'incasso (art. 2697 c.c.; G-4);
5. una prova di notifica appartiene a un solo atto e a una sola spedizione (art. 3-bis L. 53/1994; G-3, G-5);
6. il rito è coerente con gli atti; un monitorio senza opposizione non ha udienze (artt. 641 e 647 c.p.c.; G-10, G-12);
7. non esistono due proforma per lo stesso compenso (G-13);
8. le decadenze dell'art. 416 c.p.c. si contano dalla prima udienza fissata con il decreto, non da un rinvio (G-6).
"""

from __future__ import annotations

from typing import Any, Iterable

from pct.incasso_provato import pagato_senza_prova
from pct.proforma_unica import decidi

from .modello import Conclusione, Contraddizione, Dubbio, Fonte, TermineAssegnato, Udienza
from .regole.contesto import Contesto
from .regole.economia import riscontro_incasso
from .rito import rito_da_atti
from .testo import data_it, pulito, semplice



def _termine_e_udienza(udienze: list[Udienza], termini: list[TermineAssegnato]) -> list[Contraddizione]:
    esito = []
    for udienza in udienze:
        if udienza.modalita != "note_scritte" or not udienza.fonte:
            continue
        note = [t for t in termini if t.fonte.oggetto_id == udienza.fonte.oggetto_id and t.adempimento.startswith("Depositare le note")]
        for termine in note:
            if termine.scadenza and termine.scadenza != udienza.data:
                esito.append(Contraddizione(
                    "termine_non_udienza",
                    f"Il provvedimento fissa l'udienza del {data_it(udienza.data)} sostituita da note scritte e il termine per "
                    f"le note al {data_it(termine.scadenza)}.", True,
                    f"vale il termine assegnato dal giudice ({data_it(termine.scadenza)}): è perentorio (art. 127-ter, primo comma, "
                    f"c.p.c.); il {data_it(udienza.data)} è la data dell'udienza sostituita, non un termine", termine.fonte))
    return esito


def _presenze_scritte(fatti: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Le udienze che il provvedimento o il registro dichiarano in presenza («… 09:00 in presenza»), dai fatti collaudati."""
    from pct.archivio_letture.rettifica_termini import _RE_IN_PRESENZA

    esito: dict[str, str] = {}
    for fatto in fatti or ():
        if (fatto.get("categoria") == "data" and fatto.get("campo") == "udienza" and fatto.get("tipo") in {"documento", "allegato_pec"}
                and fatto.get("verifica") in {"verificata", "corretta"} and _RE_IN_PRESENZA.search(pulito(fatto.get("contesto")))):
            esito.setdefault(pulito(fatto.get("valore"))[:10], pulito(fatto.get("contesto"))[:200])
    return esito


def _scadenzario(scadenze: Iterable[dict[str, Any]], conclusioni: list[Conclusione], ctx: Contesto,
                 fatti: Iterable[dict[str, Any]] = ()) -> list[Contraddizione]:
    """Il confronto con le scadenze e l'agenda già registrate: ciò che il modello direbbe diversamente."""
    esito = []
    presenze = _presenze_scritte(fatti)
    termini_modello = {c.termine.scadenza: c for c in conclusioni if c.termine and c.termine.scadenza}
    udienze_modello = {u.data: u for u in ctx.udienze}
    for voce in scadenze:
        giorno = pulito(voce.get("data_scadenza") or voce.get("data"))[:10]
        titolo = semplice(voce.get("titolo"))
        stato = semplice(voce.get("stato"))
        if not giorno or stato in {"annullato", "annullata", "completato", "completata", "chiuso"}:
            continue
        if ctx.posizione == "attiva" and "costituzione del convenuto" in titolo:
            esito.append(Contraddizione("termine_altra_parte", f"In scadenziario «{pulito(voce.get('titolo'))}» del {data_it(giorno)}.",
                                        True, "è il termine della controparte (art. 416 c.p.c.): non è un nostro adempimento"))
        udienza = udienze_modello.get(giorno)
        in_presenza = (udienza and udienza.modalita == "presenza") or giorno in presenze
        if titolo.startswith("opposizione alla trattazione scritta") and in_presenza:
            # Il termine di opposizione decorre dalla comunicazione (art. 127-ter, secondo comma, c.p.c.): il giorno
            # dell'udienza fissata in presenza non è quel termine.
            dove = (f"il registro dice «{presenze[giorno]}»" if giorno in presenze else
                    f"il provvedimento «{udienza.fonte.nome if udienza.fonte else ''}» fissa per il {data_it(giorno)} un'udienza in presenza")
            esito.append(Contraddizione(
                "udienza_detta_opposizione", f"In scadenziario «{pulito(voce.get('titolo'))}» del {data_it(giorno)}.", False,
                f"{dove}: il {data_it(giorno)} è un'udienza in presenza; l'opposizione alla trattazione scritta decorre dalla "
                "comunicazione (art. 127-ter, secondo comma, c.p.c.); correggere la scadenza",
                udienza.fonte if udienza else None))
        e_udienza = titolo.startswith("udienza") or titolo.startswith("comparizione")
        if e_udienza and giorno not in udienze_modello and giorno in termini_modello:
            esito.append(Contraddizione("termine_non_udienza", f"In agenda «{pulito(voce.get('titolo'))}» del {data_it(giorno)}.",
                                        True, f"per il modello è il termine «{termini_modello[giorno].cosa}», non un'udienza"))
        if e_udienza and ctx.rito.codice == "monitorio":
            esito.append(Contraddizione("rito_coerente", f"Udienza del {data_it(giorno)} in un procedimento monitorio.", False,
                                        "senza opposizione il monitorio non ha udienze (artt. 641 e 647 c.p.c.): verificare se è "
                                        "di un'altra causa"))
    return esito


def _pagato(pagamenti: Iterable[dict[str, Any]], parcelle: Iterable[dict[str, Any]]) -> tuple[list[Contraddizione], list[Dubbio]]:
    """«Pagato» senza prova: regola unica di `pct/incasso_provato.pagato_senza_prova` (artt. 1188 e 2697 c.c.)."""
    contraddizioni, dubbi = [], []
    parcelle = list(parcelle)
    for voce in pagamenti:
        if voce.get("voce") == "contributo_unificato":
            continue  # il contributo si versa all'erario: lo controlla il confronto con il dovuto (art. 13 D.P.R. 115/2002)
        importo = voce.get("importo")
        registrato = bool(riscontro_incasso(voce, parcelle))
        presidio = {"status": voce.get("stato"), "updated_by": voce.get("autore") or voce.get("origine"), "receipt_id": voce.get("prova_incasso"),
                    "history": voce.get("storico") or []}
        if semplice(voce.get("stato")) not in {"pagato", "parziale"}:
            continue
        fonte = Fonte(pulito(voce.get("documento")) or "economia", pulito(voce.get("voce")), pulito(voce.get("note"))[:200],
                      pulito(voce.get("data")), "economia")
        aperta = pagato_senza_prova(presidio, incasso_registrato=registrato)
        contraddizioni.append(Contraddizione(
            "pagato_senza_prova", f"«{pulito(voce.get('voce'))}» risulta pagato (€ {importo}), scritto da «{pulito(voce.get('origine'))}».",
            not aperta, "lo stato è stato deciso dall'avvocato o l'incasso è registrato" if not aperta else
            "nessuna prova d'incasso: lo stato corretto è «da incassare» (art. 2697 c.c.)", fonte))
        if aperta:
            dubbi.append(Dubbio("incasso_non_provato", f"La somma di € {importo} ({pulito(voce.get('voce'))}) non risulta incassata: "
                                "manca la prova del pagamento.", "il bonifico o la quietanza del pagamento", fonte))
    return contraddizioni, dubbi


def _proforma(parcelle: Iterable[dict[str, Any]]) -> tuple[list[Contraddizione], list[Dubbio]]:
    """Una sola proforma automatica per lo stesso compenso: regola unica di `pct/proforma_unica.decidi`."""
    valida, superate = decidi(list(parcelle))
    if not superate:
        return [], []
    numeri = ", ".join(pulito(p.get("numero") or p.get("id")) for p in [valida, *superate])
    return ([Contraddizione("proforma_doppia", f"{len(superate) + 1} proforma automatiche per lo stesso compenso ({numeri}).", True,
                            f"vale la proforma {pulito(valida.get('numero') or valida.get('id'))}; le altre sono superate")],
            [Dubbio("proforma_doppia", f"Proforma automatiche ripetute per lo stesso compenso: {numeri}.",
                    "la conferma dell'annullamento delle proforma superate")])


def _prove_notifica(ctx: Contesto) -> list[Contraddizione]:
    esito = []
    proprietari: dict[str, str] = {}
    for notifica in ctx.notifiche:
        for fonte in notifica.fonti:
            if fonte in proprietari and proprietari[fonte] != notifica.notifica_id:
                esito.append(Contraddizione("prova_un_solo_atto", f"La ricevuta {fonte} è attribuita a due spedizioni.", False,
                                            "una ricevuta prova una sola spedizione (art. 3-bis, comma 3, L. 53/1994)"))
            proprietari[fonte] = notifica.notifica_id
    for atto in ctx.atti:
        if atto.appartenenza == "contorno" and "stragiudizial" in atto.motivo_appartenenza:
            esito.append(Contraddizione("prova_un_solo_atto", f"«{atto.nome}» è un atto stragiudiziale.", True,
                                        "le sue ricevute PEC provano l'invio della diffida, non la notifica di un atto della causa",
                                        Fonte(atto.id, atto.nome, "", atto.data)))
    return esito


def _rito(ctx: Contesto) -> list[Contraddizione]:
    dagli_atti = rito_da_atti(a.etichetta for a in ctx.della_causa())
    if dagli_atti and ctx.rito.codice not in {dagli_atti, "ignoto"} and not (
            {dagli_atti, ctx.rito.codice} <= {"esecuzione_mobiliare", "esecuzione_presso_terzi"}):
        sciolta = ctx.rito.codice_oggetto != ""
        return [Contraddizione("rito_coerente", f"Il codice oggetto dice «{ctx.rito.etichetta}», gli atti indicano «{dagli_atti}».",
                               sciolta, "prevale il codice oggetto ministeriale con cui la causa è iscritta" if sciolta else
                               "manca il codice oggetto: il rito resta da stabilire")]
    return []


def _decadenze_416(ctx: Contesto) -> list[Contraddizione]:
    costituzioni = [t for t in ctx.termini if t.adempimento.startswith("Costituirsi")]
    if len(costituzioni) < 2:
        return []
    prima = min(costituzioni, key=lambda t: t.fonte.data or "9999")
    return [Contraddizione("decadenze_416", f"Un provvedimento successivo ({data_it(t.fonte.data)}) indicherebbe un nuovo termine di "
                           "costituzione.", True, f"vale quello riferito alla prima udienza fissata con il decreto del "
                           f"{data_it(prima.fonte.data)}: le decadenze dell'art. 416 c.p.c. non si riaprono", t.fonte)
            for t in costituzioni if t is not prima]


def controlla(ctx: Contesto, conclusioni: list[Conclusione], errori_materiali: list[tuple[str, Fonte]], *,
              pagamenti: list[dict[str, Any]], parcelle: list[dict[str, Any]], scadenze: list[dict[str, Any]],
              fatti: list[dict[str, Any]] | None = None) -> tuple[list[Contraddizione], list[Dubbio]]:
    contraddizioni = _termine_e_udienza(ctx.udienze, ctx.termini) + _prove_notifica(ctx) + _rito(ctx) + _decadenze_416(ctx)
    contraddizioni += _scadenzario(scadenze, conclusioni, ctx, fatti)
    dubbi: list[Dubbio] = []
    for giorno, fonte in errori_materiali:
        contraddizioni.append(Contraddizione("data_anteriore_atto", f"Il provvedimento del {data_it(fonte.data)} indica il "
                                             f"{data_it(giorno)}, data anteriore al provvedimento stesso.", False,
                                             "non è un termine: probabile errore materiale", fonte))
        dubbi.append(Dubbio("errore_materiale", f"Data del {data_it(giorno)} anteriore al provvedimento del {data_it(fonte.data)}: "
                            "probabile errore materiale, non è stata trasformata in termine.",
                            "la correzione del provvedimento o la lettura del fascicolo d'ufficio", fonte))
    from .regole.monitorio import decorrenze_incoerenti

    for giorno, pronuncia, fonte in decorrenze_incoerenti(ctx):
        messaggio = (f"L’istanza indica la decorrenza del {data_it(giorno)}, "
                     f"anteriore al decreto del {data_it(pronuncia)}.")
        contraddizioni.append(Contraddizione("data_anteriore_atto", messaggio, False, fonte=fonte))
        dubbi.append(Dubbio("errore_materiale", messaggio, "la data nella ricevuta originale di notifica", fonte))
    for controllo in (_pagato(pagamenti, parcelle), _proforma(parcelle)):
        contraddizioni += controllo[0]
        dubbi += controllo[1]
    return contraddizioni, dubbi


__all__ = ["controlla"]
