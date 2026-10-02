"""Verificatori di confronto: pubblicazione dopo la lettura, GET solo SQL."""
from __future__ import annotations
import hashlib
import json
from pct.discordanze_letture_repository import RegistroDiscordanze
from web.services.registro_letture_runtime import registro_corrente, tenant_corrente


def repository():
    tenant = tenant_corrente()
    if not tenant or tenant in {'single-studio','default'}:
        raise RuntimeError('Studio non identificato per la verifica delle discordanze')
    return RegistroDiscordanze(registro_corrente()), tenant


def verifica_discordanze_fascicolo(fascicolo):
    from pct.archivio_letture.parti_fascicolo import parti_lette, stesso_nome
    from web.helpers import get_clienti
    from web.services.archivio_letture_runtime import fatti_fascicolo
    repo, tenant = repository()
    client_id = str(getattr(fascicolo,'id_cliente','') or '')
    cliente = get_clienti().get(client_id) if client_id else None
    cf = str(getattr(cliente,'codice_fiscale','') or '').strip().upper()
    voci = []
    if cf:
        docs = {d.id:d for d in fascicolo.documenti}
        sources = []
        values = set()
        for fatto in fatti_fascicolo(fascicolo,categoria='parte'):
            parti = parti_lette([fatto])
            if len(parti) != 1 or parti[0].ruolo != 'assistito' or not stesso_nome(parti[0].nome,fascicolo.nome_cliente):
                continue
            actual = parti[0].codice_fiscale
            if not actual or actual == cf:
                continue
            doc = docs.get(fatto.oggetto_id)
            if not doc:
                continue
            values.add(actual)
            sources.append({'id':doc.id,'sha256':fatto.sha256,'label':doc.nome,
                            'href':f'/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza',
                            'valore':actual,'citazione':fatto.contesto[:300]})
        unique = {(s['id'],s['sha256'],s['valore']):s for s in sources}
        if unique:
            voci.append({'chiave':client_id,'codice':'cf_cliente_atto','titolo':'Codice fiscale discordante',
                         'fascicoloId':fascicolo.id,'fascicolo':fascicolo.titolo,
                         'cliente':fascicolo.nome_cliente,'clienteId':client_id,
                         'rg':f'{fascicolo.numero_rg}/{fascicolo.anno_rg}',
                         'numeroFascicolo':str(getattr(fascicolo,'numero','') or ''),
                         'valoreAnagrafica':cf,'valoriAtto':sorted(values),
                         'fonti':sorted(unique.values(),key=lambda s:s['id']),
                         'nota':'I valori non coincidono. Confronta il documento originale con la scheda cliente; il software non corregge automaticamente nessuno dei due.'})
    # L'assenza del cliente/CF non dimostra che una discordanza precedente
    # sia stata risolta: conserva l'avviso finché è possibile rifare il confronto.
    if cf:
        repo.riconcilia(tenant,fascicolo.id,'cf_cliente_atto',voci)


def riepilogo_discordanze(page=1):
    repo, tenant = repository()
    result = repo.aperte(tenant,page=page)
    result['ok'] = True
    return result
