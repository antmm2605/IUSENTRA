"""Il motore unico del ragionamento processuale: dalle fonti del fascicolo al modello della causa.

Sequenza (deterministica, nessuna lettura di file, nessun modello linguistico):
1. numero di ruolo: dal fascicolo, altrimenti dai fatti collaudati e dalle ricevute di deposito (G-15);
2. atti: natura dal catalogo, autore, data, ruolo, appartenenza alla causa, studio;
3. rito: codice oggetto PST confermato dagli atti;
4. posizione del cliente: dall'atto introduttivo o dal provvedimento che nomina il nostro difensore (G-10);
5. provvedimenti del giudice: udienze con modalità, termini con parte onerata, ordini;
6. eventi: notificazioni (con l'atto notificato), depositi, comunicazioni di cancelleria;
7. regole: termini assegnati, rito del lavoro, monitorio, sentenza;
8. controlli di coerenza e dubbi; 9. fase.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .atti import leggi_atti
from .coerenza import controlla
from .collaudo import verifica_conclusione
from .eventi import comunicazioni, depositi_eseguiti
from .fase import determina_fase
from .ingressi import FontiCausa
from .modello import Causa, Dubbio, Fonte
from .notifiche import leggi_notifiche
from .percorso import ricostruisci_percorso
from .provvedimenti import leggi_provvedimento
from .regole.contesto import Contesto
from .regole.economia import conclusione_contributo, conclusioni_economia
from .regole.lavoro import conclusioni_lavoro
from .regole.monitorio import conclusioni_monitorio
from .regole.sentenza import conclusioni_sentenza
from .regole.termini_assegnati import conclusioni_termini
from .rito import determina_rito
from .testo import pulito, rg_normale

VERSIONE = "2026.11.16.ragionamento.v20-fonti-liquidazione"
ROMA = ZoneInfo("Europe/Rome")


def _rg(fonti: FontiCausa) -> tuple[str, str]:
    dal_fascicolo = rg_normale(fonti.fascicolo.get("numero_rg"), fonti.fascicolo.get("anno_rg"))
    if dal_fascicolo:
        return dal_fascicolo, "fascicolo"
    letti = {rg_normale(f.get("valore")) for f in fonti.fatti
             if f.get("campo") == "numero_ruolo" and f.get("verifica") in {"verificata", "corretta"}}
    letti.update(rg_normale(d.get("numero_rg")) for d in fonti.depositi if d.get("stato") == "ACCETTATO_CANCELLERIA")
    letti.discard("")
    if len(letti) == 1:
        return next(iter(letti)), "letto negli atti e nelle ricevute di deposito"
    return "", "discordante" if letti else ""


def _posizione(atti, rito, depositi) -> str:
    causa = [a for a in atti if a.appartenenza == "causa"]
    if rito.codice == "volontaria_giurisdizione" and (any(d.accettato and d.documenti_ids for d in depositi) or any(a.dello_studio for a in causa)):
        return "attiva"  # nella volontaria giurisdizione non c'è controparte: chi deposita il ricorso è il ricorrente
    introduttivi = [a for a in causa if a.natura in {"atto_principale", "atto_esecutivo"}]
    if any(a.dello_studio for a in introduttivi):
        return "attiva"
    if introduttivi and all(a.autore == "controparte" for a in introduttivi):
        return "passiva"
    if any(a.autore == "giudice" and a.dello_studio for a in causa):
        return "attiva"
    return "ignota"


def _riscontri_notifiche_storiche(fonti: FontiCausa) -> dict[str, tuple[str, str]]:
    impronte = {str(d["id"]): str(d.get("sha256") or "").lower() for d in fonti.documenti}
    riscontri = {}
    for fatto in fonti.fatti:
        if fatto.get("campo") != "riscontro_notifica_pec_storica" or fatto.get("verifica") == "ignorata":
            continue
        invio = str(fatto.get("oggetto_id") or "")
        for prova in fatto.get("prove") or ():
            eml = prova.get("impronte_eml") or {}
            consegne = [str(ricevuta.get("documento_id") or "") for ricevuta in prova.get("consegne") or ()]
            accettazione = str(prova.get("accettazione_id") or "")
            riferimenti = {invio, accettazione, *consegne}
            accettazione_come_fonte = prova.get("originale_nella_ricevuta") is True and invio == accettazione
            riferimenti_attesi = len(consegne) + (1 if accettazione_come_fonte else 2)
            if not consegne or "" in riferimenti or len(riferimenti) != riferimenti_attesi or not riferimenti.issubset(eml):
                continue
            if any(not impronta or impronte.get(oid) != impronta for oid, impronta in eml.items()):
                continue
            allegati = set(prova.get("impronte_allegati") or ())
            for oid, impronta in impronte.items():
                if impronta and impronta in allegati:
                    riscontri.setdefault(oid, (invio, str(prova.get("accettazione_data") or "")[:10]))
    return riscontri


def ragiona(fonti: FontiCausa) -> Causa:
    oggi = fonti.oggi or datetime.now(ROMA).date()
    rg, origine_rg = _rg(fonti)
    avvocati = [pulito(a) for a in (fonti.studio.get("avvocati") or [])] + [pulito(fonti.fascicolo.get("avvocato_referente"))]
    atti = leggi_atti(fonti.documenti, fonti.fatti, rg_causa=rg, avvocati=[a for a in avvocati if a])
    rito = determina_rito(fonti.fascicolo, [a.etichetta for a in atti if a.appartenenza == "causa"])
    depositi = depositi_eseguiti(atti, fonti.depositi)
    posizione = _posizione(atti, rito, depositi)
    udienze, termini, ordini, errori = [], [], [], []
    viste_udienze, visti_termini = set(), set()
    for atto in atti:
        if atto.autore != "giudice" or atto.appartenenza != "causa" or not atto.testo:
            continue
        lettura = leggi_provvedimento(atto, rg)
        for udienza in lettura.udienze:
            if (udienza.data, udienza.modalita) not in viste_udienze:
                viste_udienze.add((udienza.data, udienza.modalita))
                udienze.append(udienza)
        for termine in lettura.termini:
            chiave = (termine.scadenza, termine.formula, termine.adempimento)
            if chiave not in visti_termini:
                visti_termini.add(chiave)
                termini.append(termine)
        for ordine in lettura.ordini:
            if not any(o.codice == ordine.codice and o.testo == ordine.testo for _a, o in ordini):
                ordini.append((atto, ordine))
        errori.extend(lettura.errori_materiali)
    ctx = Contesto(
        fascicolo_id=pulito(fonti.fascicolo.get("id")), rg=rg, ufficio=pulito(fonti.fascicolo.get("tribunale")), rito=rito,
        posizione=posizione, atti=atti, udienze=sorted(udienze, key=lambda u: u.data), termini=termini, ordini=ordini,
        notifiche=leggi_notifiche(atti), depositi=depositi, comunicazioni=comunicazioni(atti),
        oggi=oggi, fascicolo=dict(fonti.fascicolo), consegne_verificate=fonti.consegne_verificate,
        notifiche_storiche=_riscontri_notifiche_storiche(fonti),
    )
    conclusioni = conclusioni_termini(ctx) + conclusioni_lavoro(ctx) + conclusioni_monitorio(ctx) + conclusioni_sentenza(ctx)
    economiche, economia = conclusioni_economia(ctx, fonti.pagamenti, fonti.parcelle)
    conclusioni += economiche
    contributo = conclusione_contributo(ctx, fonti.fatti, fonti.pagamenti, stato_condiviso=fonti.contributo)
    if contributo:
        conclusioni.append(contributo)
    contraddizioni, dubbi = controlla(ctx, conclusioni, errori, pagamenti=fonti.pagamenti, parcelle=fonti.parcelle, scadenze=fonti.scadenze)
    depositi_collegati = {oid for d in depositi if d.accettato for oid in d.documenti_ids}
    for deposito in depositi:
        if deposito.stato_registro or not deposito.fonte_id or deposito.fonte_id in depositi_collegati:
            continue
        atto = ctx.atto(deposito.fonte_id)
        if atto:
            dubbi.append(Dubbio(
                "esito_deposito_da_correlare", "È presente una copia del messaggio di deposito.",
                "l'esito della cancelleria correlato tramite identificativo di invio o busta",
                Fonte(atto.id, atto.nome, deposito.titolo, deposito.data),
            ))
    if origine_rg == "discordante":
        dubbi.append(Dubbio("rg_discordante", "Le fonti riportano numeri di ruolo diversi.",
                            "la corrispondenza fra l'iscrizione nel registro e l'atto introduttivo"))
    elif not rg:
        dubbi.append(Dubbio("rg_mancante", "Il numero di ruolo non è nel fascicolo né negli atti letti.",
                            "la ricevuta di accettazione del deposito o la comunicazione di cancelleria"))
    if posizione == "ignota":
        dubbi.append(Dubbio("posizione_ignota", "Non si sa se il cliente sia attore o convenuto: i termini con parte onerata "
                            "restano da attribuire.", "l'atto introduttivo dello studio o della controparte"))
    for conclusione in conclusioni:
        conclusione.dubbi.extend(verifica_conclusione(conclusione))
        dubbi.extend(conclusione.dubbi)
    return Causa(
        fascicolo_id=ctx.fascicolo_id, rg=rg, ufficio=ctx.ufficio, ruolo_cliente=posizione, rito=rito, atti=atti,
        udienze=ctx.udienze, termini=termini, fase=determina_fase(ctx, conclusioni), conclusioni=conclusioni,
        contraddizioni=contraddizioni, dubbi=dubbi, economia={"origine_rg": origine_rg, "contributo_unificato": fonti.contributo, **economia}, oggi=oggi,
        impronta=fonti.impronta(), versione=VERSIONE, percorso=ricostruisci_percorso(ctx),
    )


__all__ = ["VERSIONE", "ragiona"]
