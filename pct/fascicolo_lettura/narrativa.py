"""La lettura in italiano, nell'ordine in cui un avvocato la vuole sentire.

Prima chi e che cosa, poi che cosa è stato fatto, poi a che punto siamo e che
cosa resta da fare. Ogni frase nasce da un dato del fascicolo: dove il dato
manca, la lettura dice che manca, invece di riempire il vuoto.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_it, elenco, plurale, pulisci
from .documenti import ETICHETTE_SEZIONE
from .notifiche import descrivi as descrivi_notifica

MASSIMO_EVENTI = 12
URGENZE = {0: "subito", 1: "entro pochi giorni", 2: "prossimamente", 3: "di governo"}


def _riga(etichetta: str, valore: str) -> str:
    return f"- {etichetta}: {valore}" if pulisci(valore) else ""


def quadro(lettura: dict[str, Any]) -> list[str]:
    testata = lettura["intestazione"]
    righe = ["Quadro della pratica"]
    riferimenti = [pezzo for pezzo in (testata["numero"], f"RG {testata['rg']}" if testata["rg"] else "", testata["titolo"]) if pezzo]
    righe.append(_riga("Fascicolo", " · ".join(riferimenti)))
    righe.append(_riga("Assistito", testata["cliente"]))
    righe.append(_riga("Controparte", testata["controparte"]))
    for ruolo, nomi in testata["parti"].items():
        righe.append(_riga(ruolo.capitalize(), elenco(nomi)))
    ufficio = " · ".join(pezzo for pezzo in (testata["ufficio"], f"sez. {testata['sezione']}" if testata["sezione"] else "", f"giudice {testata['giudice']}" if testata["giudice"] else "") if pezzo)
    righe.append(_riga("Ufficio", ufficio))
    righe.append(_riga("Materia", " · ".join(pezzo for pezzo in (testata["area"], testata["rito"]) if pezzo)))
    righe.append(_riga("Valore", testata["valore_causa"]))
    righe.append(_riga("Stato dichiarato", testata["stato"]))
    return [riga for riga in righe if riga]


def di_cosa_tratta(lettura: dict[str, Any]) -> list[str]:
    oggetto = lettura["oggetto"]
    righe = ["Di che cosa tratta"]
    if oggetto["oggetto_dichiarato"]:
        righe.append(f"- Oggetto: {oggetto['oggetto_dichiarato']}")
    domanda = oggetto.get("domanda")
    if domanda:
        righe.append(f"- Domanda, dal testo di «{domanda['etichetta']}»{' del ' + data_it(domanda['data']) if domanda['data'] else ''}: «{domanda['petitum']}»")
    elif oggetto["atti_principali"]:
        righe.append(f"- Atti principali presenti: {elenco([voce['etichetta'] for voce in oggetto['atti_principali'][:4]])}; il testo non è indicizzato, quindi la domanda non può essere citata.")
    if len(righe) == 1:
        righe.append("- L'oggetto non è indicato nel fascicolo e nessun atto principale è catalogato: la materia va dichiarata.")
    return righe


def cosa_e_stato_fatto(lettura: dict[str, Any]) -> list[str]:
    eventi = lettura["cronologia"]
    righe = ["Che cosa è stato fatto"]
    if not eventi:
        righe.append("- Nessuna attività, deposito o notifica risulta registrata nel fascicolo.")
        return righe
    for evento in eventi[-MASSIMO_EVENTI:]:
        quando = evento["data_it"] or "senza data"
        esito = f" — {evento['esito']}" if evento["esito"] else ""
        dettaglio = f" ({evento['dettaglio']})" if evento["dettaglio"] and evento["dettaglio"] != evento["titolo"] else ""
        righe.append(f"- {quando} · {evento['titolo']}{esito}{dettaglio}")
    if len(eventi) > MASSIMO_EVENTI:
        righe.append(f"- … e altri {len(eventi) - MASSIMO_EVENTI} eventi precedenti.")
    return righe


def depositi_e_notifiche(lettura: dict[str, Any]) -> list[str]:
    depositi = lettura["depositi"]
    notifiche = lettura["notifiche"]
    righe = ["Depositi e notifiche"]
    if depositi["totale"]:
        importati = depositi.get("importati") or []
        acquisiti = f", {len(importati)} atti acquisiti dal fascicolo d'ufficio" if importati else ""
        righe.append(f"- Depositi telematici: {depositi['totale']} ({len(depositi['perfezionati'])} accettati dalla cancelleria, {len(depositi['in_corso'])} in corso, {len(depositi['falliti'])} da ripetere{acquisiti}).")
        for deposito in [voce for voce in depositi["tutti"] if not voce.get("importato")][-4:]:
            ricevute = f"; ricevute: {elenco(deposito['ricevute'])}" if deposito["ricevute"] else "; nessuna ricevuta registrata"
            righe.append(f"  · {deposito['data'] or 'senza data'} {deposito['atto']}: {deposito['fase']}" + ("" if deposito["perfezionato"] else f", {deposito['attesa']}") + ricevute + ".")
    else:
        righe.append("- Nessun deposito telematico registrato.")
    if notifiche["totale"]:
        righe.append(f"- Notifiche: {notifiche['totale']} ({len(notifiche['perfezionate'])} perfezionate, {len(notifiche['aperte'])} aperte, {len(notifiche['fallite'])} non andate a buon fine).")
        for notifica in notifiche["tutte"][-4:]:
            fase = f" [fase: {notifica['fase_procedurale']}]" if notifica.get("fase_procedurale") else ""
            righe.append(f"  · {descrivi_notifica(notifica)}{fase}.")
    else:
        righe.append("- Nessuna notifica registrata.")
    pec = lettura.get("pec") or {}
    if pec.get("totale"):
        corrispondenze = pec.get("per_corrispondenza") or {}
        dettaglio = ", ".join(
            f"{numero} {etichetta}" for chiave, etichetta, numero in (
                ("collegamento", "collegate", corrispondenze.get("collegamento", 0)),
                ("rg", "per numero di ruolo", corrispondenze.get("rg", 0)),
                ("cliente", "per nome dell'assistito", corrispondenze.get("cliente", 0)),
            ) if numero
        )
        righe.append(f"- PEC del presidio che riguardano la pratica: {pec['totale']} ({dettaglio}); {len(pec['da_controllare'])} da controllare, {len(pec['termini_da_registrare'])} termini e {len(pec['udienze_da_registrare'])} udienze estratti ma non ancora registrati.")
        ultima = pec.get("ultima")
        if ultima:
            righe.append(f"  · Ultima PEC: {ultima['data']} «{ultima['oggetto']}»" + (f" da {ultima['mittente']}" if ultima["mittente"] else "") + ".")
    else:
        righe.append("- Nessuna PEC del presidio risulta collegata alla pratica, né per numero di ruolo né per nome dell'assistito.")
    return righe


def documentazione(lettura: dict[str, Any]) -> list[str]:
    documenti = lettura["documenti"]
    righe = ["Documentazione"]
    if not documenti["totale"]:
        righe.append("- Il fascicolo non contiene documenti.")
        return righe
    conteggi = ", ".join(f"{numero} {ETICHETTE_SEZIONE.get(sezione, sezione)}" for sezione, numero in documenti["conteggi"].items())
    righe.append(f"- {plurale(documenti['totale'], 'documento', 'documenti')}: {conteggi}.")
    chiave = [
        ("Atto introduttivo", documenti.get("atto_introduttivo")),
        ("Ultimo atto di parte", documenti.get("ultimo_atto_di_parte")),
        ("Ultimo provvedimento", documenti.get("ultimo_provvedimento")),
        ("Ultima comunicazione", documenti.get("ultima_comunicazione")),
        ("Procura", documenti.get("procura")),
    ]
    for etichetta, documento in chiave:
        if documento:
            righe.append(f"- {etichetta}: {documento['etichetta']}" + (f" del {documento['data_it']}" if documento["data_it"] else "") + f" ({documento['nome']}).")
    if documenti["da_verificare"]:
        quanti = len(documenti["da_verificare"])
        righe.append(f"- Da verificare: {plurale(quanti, 'documento non ancora catalogato', 'documenti non ancora catalogati')} dal contenuto ({elenco([voce['nome'] for voce in documenti['da_verificare'][:3]])}{'…' if quanti > 3 else ''}).")
    return righe


def conformita_ed_economico(lettura: dict[str, Any]) -> list[str]:
    righe: list[str] = []
    conformita = lettura["conformita"]
    if conformita:
        generale = dict(conformita.get("general") or {})
        etichetta = pulisci(conformita.get("readiness_label") or generale.get("label"))
        if etichetta:
            righe.append("Conformità")
            righe.append(f"- {etichetta} ({int(generale.get('blocking_count') or 0)} blocchi, {int(generale.get('warning_count') or 0)} avvisi).")
    economico = lettura.get("economico") or {}
    if economico.get("presente"):
        righe.append("Quadro economico")
        pezzi = [
            f"{etichetta} {economico[chiave]}"
            for chiave, etichetta in (("preventivato_it", "preventivato"), ("conferito_it", "conferito"), ("fatturato_it", "fatturato"), ("incassato_it", "incassato"), ("saldo_aperto_it", "saldo aperto"))
            if economico.get(chiave)
        ]
        righe.append("- " + (elenco(pezzi, "e") if pezzi else "nessun importo registrato: preventivo e conferimento non risultano collegati") + ".")
        liquidazione = economico.get("liquidazione") or {}
        if economico.get("liquidato"):
            esito = {"incassata": "bonificata sul conto dello studio", "parziale": f"incassata solo in parte ({economico.get('incassato_it')})", "non_incassata": "non ancora bonificata sul conto dello studio"}.get(economico.get("liquidazione_incasso", ""), "")
            righe.append(f"- Liquidazione del giudice: {economico['liquidato_it']}" + (f" (sentenza del {liquidazione['data']})" if liquidazione.get("data") else "") + (f", {liquidazione['stato_etichetta'].lower()} nel presidio" if liquidazione.get("stato_etichetta") else "") + (f"; {esito}" if esito else "") + ".")
        if economico.get("bonifici"):
            righe.append(f"- Bonifici ricevuti: {len(economico['bonifici'])} per {economico['incassato_bonifico_it']} (" + elenco([f"{voce['numero'] or 'senza numero'} il {voce['pagata_il'] or 'data non registrata'}" for voce in economico["bonifici"][:3]]) + ").")
        if float(economico.get("anticipazioni_da_recuperare") or 0) > 0:
            righe.append(f"- Anticipazioni da recuperare: {economico['anticipazioni_da_recuperare_it']}.")
        if economico.get("parcelle_scadute"):
            righe.append(f"- Parcelle scadute: {len(economico['parcelle_scadute'])} per {economico['importo_scaduto_it']} ({elenco([voce['numero'] or 'senza numero' for voce in economico['parcelle_scadute'][:3]])}).")
        if not economico.get("ha_incarico"):
            righe.append("- Preventivo e conferimento d'incarico non risultano collegati al fascicolo.")
    return righe


def a_che_punto_siamo(lettura: dict[str, Any]) -> list[str]:
    fase = lettura["fase"]
    righe = ["A che punto siamo", f"- {fase['descrizione'][:1].upper() + fase['descrizione'][1:]}."]
    if fase["prove"]:
        righe.append(f"- Lo dicono: {elenco(fase['prove'])}.")
    if fase["prossima_udienza"]:
        righe.append(f"- Prossima udienza: {fase['prossima_udienza']}.")
    for incoerenza in fase["incoerenze"]:
        righe.append(f"- Attenzione: {incoerenza}.")
    return righe


def prossimi(lettura: dict[str, Any]) -> list[str]:
    passi = lettura["prossimi_passi"]
    stato = lettura.get("stato_passi") or {}
    righe = ["Prossimi passaggi"]
    if not stato.get("attivi", True):
        righe.append(f"- {stato.get('motivo') or 'Nessun passaggio da eseguire.'}")
        return righe
    if stato.get("motivo"):
        righe.append(f"- {stato['motivo']}")
    if not passi:
        righe.append("- Nessun adempimento risulta aperto: il fascicolo è allineato.")
        return righe
    for indice, passo in enumerate(passi, start=1):
        quando = f" [{URGENZE.get(passo['urgenza'], '')}{', entro il ' + passo['entro'] if passo['entro'] else ''}]"
        motivo = f" — {passo['motivo']}" if passo["motivo"] else ""
        norma = f" ({passo['norma']})" if passo.get("norma") else ""
        righe.append(f"{indice}. {passo['azione']}{quando}{motivo}{norma}.")
    return righe


ESITI_DEPOSITI = {
    "nessun_deposito_in_corso": "nessun deposito in attesa di ricevute",
    "pec_non_configurata": "casella PEC dello studio non configurata: le ricevute non possono essere lette automaticamente",
    "controllate": "ricevute controllate",
    "polling_fallito": "controllo delle ricevute non riuscito",
}


def verifiche_automatiche(lettura: dict[str, Any]) -> list[str]:
    verifiche = lettura.get("verifiche") or {}
    righe = ["Verifiche automatiche dei presìdi"]
    if verifiche.get("in_corso"):
        righe.append("- In corso: i presìdi stanno controllando ricevute, PEC, notifiche e documenti.")
    if not verifiche.get("eseguita_il"):
        if not verifiche.get("in_corso"):
            righe.append("- Non ancora eseguite: partono all'apertura del fascicolo e si ripetono ogni quindici minuti.")
    else:
        righe.append(f"- Eseguite il {verifiche.get('eseguita_il_it') or verifiche.get('eseguita_il')}.")
        esiti = verifiche.get("esiti") or {}
        pec = esiti.get("pec") or {}
        if pec:
            righe.append(f"- Presidio PEC: {pec.get('esaminate', 0)} messaggi esaminati, {pec.get('collegate', 0)} collegati automaticamente al fascicolo, {len(pec.get('da_confermare') or [])} da confermare.")
        notifiche = esiti.get("notifiche") or {}
        if notifiche:
            righe.append(f"- Presidio notifiche: {notifiche.get('esaminati', 0)} presidi esaminati, {notifiche.get('riallineati', 0)} riallineati alle prove del fascicolo.")
        depositi = esiti.get("depositi") or {}
        if depositi:
            dettaglio = ESITI_DEPOSITI.get(str(depositi.get("esito") or ""), str(depositi.get("esito") or ""))
            if depositi.get("esito") == "controllate":
                dettaglio += f": {depositi.get('controllati', 0)} depositi controllati, {depositi.get('aggiornati', 0)} aggiornati"
            righe.append(f"- Presidio depositi: {dettaglio}.")
        documenti = esiti.get("documenti") or {}
        if documenti:
            if documenti.get("esito") == "tutti_letti":
                righe.append(f"- Presidio documentale: tutti i {documenti.get('documenti', 0)} documenti letti e catalogati.")
            else:
                acquisire = f", {documenti['da_acquisire']} censiti dal portale da acquisire" if documenti.get("da_acquisire") else ""
                righe.append(f"- Presidio documentale: {documenti.get('letti', 0)} documenti letti su {documenti.get('documenti', 0)}, {documenti.get('indicizzati', 0)} indicizzati ora, {documenti.get('errori', 0)} non leggibili{acquisire}.")
        for nome, errore in (verifiche.get("errori") or {}).items():
            righe.append(f"- Verifica {nome} non completata: {errore}.")
    lacune_conoscenza = (lettura.get("conoscenza") or {}).get("lacune") or []
    for voce in lacune_conoscenza:
        righe.append(f"- Conoscenza da completare: {voce['descrizione']}")
    return righe


def lacune(lettura: dict[str, Any]) -> list[str]:
    voci = lettura["lacune"]
    if not voci:
        return []
    return ["Lacune da colmare", *[f"- {voce}." for voce in voci]]


SEZIONI = {
    "quadro": quadro,
    "oggetto": di_cosa_tratta,
    "cronologia": cosa_e_stato_fatto,
    "depositi_notifiche": depositi_e_notifiche,
    "documenti": documentazione,
    "conformita_economico": conformita_ed_economico,
    "fase": a_che_punto_siamo,
    "prossimi_passi": prossimi,
    "verifiche": verifiche_automatiche,
    "lacune": lacune,
}
ORDINE_SEZIONI = tuple(SEZIONI)


def componi(lettura: dict[str, Any], sezioni: tuple[str, ...] = ORDINE_SEZIONI) -> str:
    """Il testo delle sole sezioni richieste, nell'ordine canonico."""
    blocchi = [SEZIONI[nome](lettura) for nome in ORDINE_SEZIONI if nome in sezioni]
    return "\n\n".join("\n".join(blocco) for blocco in blocchi if blocco)


def narrativa(lettura: dict[str, Any]) -> str:
    return componi(lettura)


__all__ = ["MASSIMO_EVENTI", "ORDINE_SEZIONI", "SEZIONI", "URGENZE", "componi", "narrativa"]
