"""Correlazione delle ricevute con identificativi esatti; nessun invio o firma.

Le prove sono lette dal MIME SQL una volta e conservate nei metadati della
PEC; il motore PEC le versa nell'archivio delle letture per le viste del fascicolo.
"""
from __future__ import annotations
import html
import re
from copy import copy
from typing import Any


def canonical(value: Any) -> str:
    return html.unescape(str(value or '')).strip().strip('<> ').lower()


def associa_ricevute_salvate(fascicolo: Any, messaggi: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Riusa gli identificativi del presidio PEC per l'archivio del fascicolo."""
    from pct.ragionamento.testo import rg_normale

    depositi = {d.id: d for d in fascicolo.depositi_pct}
    rg = rg_normale(f"{fascicolo.numero_rg}/{fascicolo.anno_rg}")
    if not rg or not depositi:
        return {}
    associati = {}
    ancore: dict[str, tuple[str, str, str, str]] = {}
    for m in messaggi:
        if not m.get("collegata") or m.get("event_type") != "pct_deposito":
            continue
        lifecycle = m.get("deposit_lifecycle") or {}
        fase = (lifecycle.get("current_stage") or {}).get("id")
        corr = lifecycle.get("correlation") or {}
        prova = lifecycle.get("receipt") or {}
        ref = m.get("archive_receipt_reference") or {}
        deposito = depositi.get(ref.get("deposito_id"))
        if (fase not in {"accettazione_deposito", "rifiuto_deposito"} or deposito is None
                or ref.get("fascicolo_id") != fascicolo.id or ref.get("strategy") != "idbusta_finale"
                or prova.get("outcome_code") is None or rg_normale(prova.get("numero_ruolo_certificato") or "") != rg):
            continue
        busta = str(corr.get("idbusta") or "")
        fonte = canonical(corr.get("source_message_id"))
        if busta and busta == deposito.id_deposito_esterno == ref.get("idbusta") and fonte and m.get("mime_sha256"):
            associati[m["id"]] = (deposito.id, busta)
            ancore[m["id"]] = (deposito.id, busta, fonte, m["mime_sha256"])

    for m in messaggi:
        if not m.get("collegata") or m.get("event_type") != "pct_deposito" or m["id"] in associati:
            continue
        lifecycle = m.get("deposit_lifecycle") or {}
        fase = (lifecycle.get("current_stage") or {}).get("id")
        corr = lifecycle.get("correlation") or {}
        prova = lifecycle.get("receipt") or {}
        ref = m.get("archive_receipt_reference") or {}
        impronta = m.get("mime_sha256")
        if not impronta:
            continue
        if (fase in {"accettazione_pec", "consegna_pec"}
                and ref.get("strategy") == "identificativo_xml_esito_ministeriale"
                and ref.get("fascicolo_id") == fascicolo.id and ref.get("mime_sha256") == impronta):
            ancora = ancore.get(ref.get("anchor_message_id"))
            if (ancora and ancora[0] == ref.get("deposito_id") and ancora[2] == canonical(ref.get("provider_message_id"))
                    and ancora[3] == ref.get("anchor_mime_sha256")):
                associati[m["id"]] = ancora[:2]
        if (fase == "esito_controlli_deposito" and prova.get("outcome_code") is not None
                and rg_normale(prova.get("numero_ruolo_certificato") or "") == rg):
            candidati = {(dep, busta) for dep, busta, fonte, _impronta in ancore.values()
                         if busta == corr.get("idbusta") and fonte == canonical(corr.get("source_message_id"))}
            if len(candidati) == 1:
                associati[m["id"]] = candidati.pop()
    return associati


def registra_ricevute(fascicolo: Any, registro: Any, tenant: str, messaggi: list[dict[str, Any]]) -> int:
    """Consegna al registro soltanto i riscontri nuovi o modificati."""
    from pct.archivio_letture.motore_pec import VERSIONE_MOTORE_PEC, fatto_esito_deposito

    associazioni = associa_ricevute_salvate(fascicolo, messaggi)
    if not associazioni:
        return 0
    oggetti = {o.oggetto_id: o for o in registro.oggetti(tenant, fascicolo.id)
               if o.tipo == "pec" and o.presente}
    fonti = [m for m in messaggi if m["id"] in oggetti and oggetti[m["id"]].impronta == m.get("mime_sha256")]
    reinvio = _reinvio_autocertificazione(fonti, associazioni)
    esistenti = {f.oggetto_id: f for f in registro.fatti(tenant, fascicolo.id, campo="esito_deposito", tipo="pec", motore="pec")}
    scritte = 0
    for messaggio in fonti:
        ident = messaggio["id"]
        if ident not in associazioni:
            continue
        oggetto = oggetti[ident]
        fatto = fatto_esito_deposito(messaggio, *associazioni[ident])
        if ident in reinvio:
            fatto.prove.append(reinvio[ident])
        prima = esistenti.get(ident)
        if prima and prima.sha256 == oggetto.impronta and prima.valore == fatto.valore and prima.prove == fatto.prove:
            continue
        scrittura = registro.registra_fatti(tenant, fascicolo.id, oggetto, "pec", [fatto],
                                             versione=VERSIONE_MOTORE_PEC, campo="esito_deposito")
        scritte += scrittura["nuovi"] + scrittura["aggiornati"]
    return scritte


def _reinvio_autocertificazione(
    fonti: list[dict[str, Any]], associazioni: dict[str, tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Riconosce la correzione documentata della richiesta di esenzione del giorno."""
    from pct.formatting import parse_datetime_rome

    richieste = [m for m in fonti if m.get("collegata") and any(
        e.get("fonte_evento") == "Comunicazione.xml" and e.get("richiesta_autocertificazione_cu")
        for e in m.get("eventi", [])
    )]
    if len(richieste) != 1:
        return {}
    richiesta, = richieste
    comunicata = parse_datetime_rome(richiesta.get("received_at"))
    if not comunicata:
        return {}
    rifiuti, accettazioni, consegne = [], [], []
    for m in fonti:
        if m["id"] not in associazioni:
            continue
        ciclo = m.get("deposit_lifecycle") or {}
        fase = (ciclo.get("current_stage") or {}).get("id")
        ricevuta = ciclo.get("receipt") or {}
        ref = m.get("archive_receipt_reference") or {}
        if fase == "consegna_pec" and ref.get("strategy") == "identificativo_xml_esito_ministeriale":
            consegne.append(m)
        nome = re.sub(r"[^a-z]+", " ", str(ricevuta.get("document_name") or "").casefold()).strip()
        if not re.fullmatch(r"autocertificazione della situazione reddituale(?: corretta)?", nome):
            continue
        esito = ricevuta.get("esito_ministeriale") or {}
        data = parse_datetime_rome(ricevuta.get("occurred_at"))
        if not data or data <= comunicata:
            continue
        motivo = str(ricevuta.get("description") or "").casefold()
        if fase == "rifiuto_deposito" and esito.get("codice_esito") == -1 and "dichiarazione dei redditi" in motivo:
            if data.date() == comunicata.date():
                rifiuti.append((m, data))
        if fase == "accettazione_deposito" and esito.get("codice_esito") == 2:
            accettazioni.append((m, data))
    if len(rifiuti) != 1:
        return {}
    ((rifiuto, data_rifiuto),) = rifiuti
    coppie = []
    for accettazione, data_esito in accettazioni:
        busta = associazioni[accettazione["id"]]
        if busta == associazioni[rifiuto["id"]]:
            continue
        for consegna in consegne:
            ref = consegna["archive_receipt_reference"]
            if associazioni[consegna["id"]] != busta or ref.get("anchor_message_id") != accettazione["id"]:
                continue
            data_consegna = parse_datetime_rome(ref.get("receipt_at"))
            if data_consegna and data_consegna.date() == comunicata.date() and data_rifiuto < data_consegna <= data_esito:
                coppie.append((accettazione, consegna))
    if len(coppie) != 1:
        return {}
    ((accettazione, consegna),) = coppie
    deposito_id, busta = associazioni[rifiuto["id"]]
    nuovo_deposito_id, nuova_busta = associazioni[accettazione["id"]]
    return {rifiuto["id"]: {
        "codice": "reinvio_autocertificazione_accettato", "deposito_id": deposito_id,
        "idbusta": busta, "nuovo_deposito_id": nuovo_deposito_id, "nuova_busta": nuova_busta,
        "fonti": {m["id"]: m["mime_sha256"] for m in (richiesta, accettazione, consegna)},
        "pec_accettazione": accettazione["id"], "pec_richiesta": richiesta["id"], "pec_consegna": consegna["id"],
        "pec_rifiuto": rifiuto["id"],
    }}


def depositi_da_archivio(fascicolo: Any) -> list[Any]:
    """Proiezione delle ricevute verificate sull'invio, senza modificare la busta."""
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from pct.formatting import format_datetime_it
    originali=list(getattr(fascicolo,'depositi_pct',[]) or [])
    copie={d.id:copy(d) for d in originali}
    if not originali:
        return []
    registro, tenant = registro_corrente(), tenant_corrente()
    fatti = registro.fatti(tenant, fascicolo.id, campo="esito_deposito", tipo="pec", motore="pec",
                           verifiche=("verificata", "corretta"))
    if not fatti:
        return originali
    correnti = {o.oggetto_id: o.impronta for o in registro.oggetti(tenant, fascicolo.id)
               if o.tipo == "pec" and o.presente}
    refs=[]
    for fatto in fatti:
        if not fatto.sha256 or correnti.get(fatto.oggetto_id) != fatto.sha256:
            continue
        for prova in fatto.prove:
            if prova.get('codice')=='correlazione_ricevuta':refs.append(prova)
            if prova.get("codice") == "reinvio_autocertificazione_accettato":
                deposito = copie.get(prova.get("deposito_id"))
                fonti = prova.get("fonti") or {}
                if deposito and len(fonti) == 3 and all(correnti.get(k) == v for k, v in fonti.items()):
                    deposito.reinvio_accettato = prova
    aliases={}
    for ref in refs:
        depid=ref.get('deposito_id'); busta=str(ref.get('idbusta') or '')
        if depid in copie and busta:aliases[busta]=depid
    for d in originali:
        if d.id_deposito_esterno in aliases and d.id!=aliases[d.id_deposito_esterno]:
            target=copie[aliases[d.id_deposito_esterno]]
            for field in ('ricevuta_cancelleria','ricevuta_controlli_automatici','esito_controlli','id_deposito_esterno'):
                value=getattr(d,field,'')
                if value:setattr(target,field,value)
            copie.pop(d.id,None)
    states={'accettazione_pec':'ACCETTATO_PEC','consegna_pec':'CONSEGNATO','esito_controlli_deposito':'WARN_CONTROLLI','accettazione_deposito':'ACCETTATO_CANCELLERIA','rifiuto_deposito':'RIFIUTATO_CANCELLERIA'}
    receipt_fields={'accettazione_pec':'ricevuta_accettazione','consegna_pec':'ricevuta_consegna','esito_controlli_deposito':'ricevuta_controlli_automatici','accettazione_deposito':'ricevuta_cancelleria','rifiuto_deposito':'ricevuta_cancelleria'}
    fasi = {'accettazione_pec': 'accettazione', 'consegna_pec': 'consegna', 'esito_controlli_deposito': 'controlli',
            'accettazione_deposito': 'cancelleria', 'rifiuto_deposito': 'cancelleria'}
    for ref in sorted(refs, key=lambda x: data_ricevuta(x.get('occurred_at'))):
        dep=copie.get(ref.get('deposito_id'))
        if not dep:continue
        stage=ref.get('stage')
        if stage in states:
            fonte = str(ref.get('message_id') or '').strip()
            if fonte:
                dep.fonti_ricevute = {**getattr(dep, 'fonti_ricevute', {}), fasi[stage]: fonte}
            stato = states[stage]
            code = ref.get('outcome_code')
            if stage == 'esito_controlli_deposito':
                stato = 'CONTROLLI_SUPERATI' if code == 1 else 'ERRORE_CONTROLLI' if isinstance(code, int) and code < 0 else 'WARN_CONTROLLI'
                dep.esito_controlli = str(code) if code is not None else ''
            # Un esito finale già acquisito non torna indietro per una RAC/RDAC
            # tardivamente importata o per una data assente nella ricevuta.
            if stage in {'accettazione_deposito', 'rifiuto_deposito'} or str(dep.stato) not in {'ACCETTATO_CANCELLERIA', 'RIFIUTATO_CANCELLERIA'}:
                dep.stato = stato
            if stage == 'consegna_pec':
                data = data_ricevuta(ref.get('occurred_at'))
                if data and fonte:
                    precedenti = getattr(dep, 'consegne_archivio', ())
                    dep.consegne_archivio = (*precedenti, (data, fonte))
            if stage == 'accettazione_deposito':
                dep.data_accettazione = data_ricevuta(ref.get('occurred_at'))
            field=receipt_fields[stage]
            if not getattr(dep,field,''):
                quando = data_ricevuta(ref.get('occurred_at'))
                setattr(dep,field,'\n'.join(['Esito: '+str(ref.get('label') or stage),'Data esito: '+format_datetime_it(quando), 'Fonte PEC: '+str(ref.get('message_id') or ''),'Message-ID deposito: '+str(ref.get('source_message_id') or '')]))
        if ref.get('idbusta'):dep.id_deposito_esterno=str(ref['idbusta'])
    return [copie[d.id] for d in originali if d.id in copie]


def data_ricevuta(value: Any) -> str:
    """Normalizza anche il vecchio campo italiano con ora ripetuta dal parser."""
    from pct.formatting import parse_datetime_rome
    raw = str(value or '').strip()
    match = re.match(r'^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})T', raw)
    parsed = parse_datetime_rome(match.group(1) if match else raw)
    if not parsed:
        return ''
    from datetime import timezone
    return parsed.astimezone(timezone.utc).isoformat()
