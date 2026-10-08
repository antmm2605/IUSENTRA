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
    nome = str(getattr(cliente, 'nome_completo', '') or fascicolo.nome_cliente).strip()
    fatti = fatti_fascicolo(fascicolo, categoria='parte')
    fonti_nome = []
    confrontabili = False
    docs = {d.id:d for d in fascicolo.documenti}
    for fatto in fatti:
        parti = parti_lette([fatto])
        if len(parti) != 1 or parti[0].ruolo != 'assistito' or fatto.oggetto_id not in docs:
            continue
        confrontabili = True
        if not stesso_nome(parti[0].nome, nome):
            fonti_nome.append({'id':fatto.oggetto_id, 'sha256':fatto.sha256,
                               'valore':parti[0].nome, 'citazione':fatto.contesto[:300]})
    if nome and confrontabili:
        pubblica_discordanza_nome_cliente(fascicolo, nome, fonti_nome)
    voci = []
    if cf:
        docs = {d.id:d for d in fascicolo.documenti}
        sources = []
        values = set()
        for fatto in fatti:
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


def pubblica_discordanza_nome_cliente(fascicolo, nome_anagrafica, fonti):
    """Materializza un confronto provato; non modifica cliente o collegamenti.

    Le fonti vengono dai motori condivisi o da una riconvalida puntuale già
    verificata. L'assenza di fatti non invoca questa funzione e non supera
    una discordanza precedente. La GET della top bar resta soltanto SQL.
    """
    from pct.archivio_letture.parti_fascicolo import stesso_nome
    repo, tenant = repository()
    docs = {str(d.id):d for d in fascicolo.documenti}
    prove = {}
    for fonte in fonti:
        doc = docs.get(str(fonte.get('id') or ''))
        valore = str(fonte.get('valore') or '').strip()
        impronta = str(fonte.get('sha256') or '').strip()
        if doc is None or not valore or len(impronta) != 64:
            raise ValueError('Confronto del nome senza documento e impronta verificabili')
        if stesso_nome(valore, nome_anagrafica):
            continue
        prove[(doc.id, impronta, valore)] = {
            'id':doc.id, 'sha256':impronta, 'label':doc.nome, 'valore':valore,
            'href':f'/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza',
            'citazione':str(fonte.get('citazione') or '')[:300],
        }
    voci = []
    if prove:
        numero, anno = str(fascicolo.numero_rg or ''), str(fascicolo.anno_rg or '')
        voci.append({
            'chiave':f'{fascicolo.id_cliente}:nome', 'codice':'nome_cliente_atto',
            'titolo':'Nome e cognome discordanti', 'fascicoloId':fascicolo.id,
            'fascicolo':fascicolo.titolo, 'cliente':nome_anagrafica,
            'clienteId':fascicolo.id_cliente, 'rg':f'{numero}/{anno}' if numero and anno else 'da acquisire',
            'numeroFascicolo':str(getattr(fascicolo,'numero','') or ''),
            'valoreAnagrafica':nome_anagrafica,
            'valoriAtto':sorted({p['valore'] for p in prove.values()}),
            'fonti':sorted(prove.values(), key=lambda p:(p['id'],p['sha256'],p['valore'])),
            'nota':'Il nome negli originali non coincide con l’anagrafica. '
                   'Il collegamento automatico resta sospeso; nessun nome o documento viene corretto per somiglianza.',
        })
    repo.riconcilia(tenant, fascicolo.id, 'nome_cliente_atto', voci)


def riepilogo_discordanze(page=1):
    repo, tenant = repository()
    result = repo.aperte(tenant,page=page)
    from web.services.controllo_studio_letture import repository as letture
    from web.services.registro_letture_runtime import utente_corrente_id
    archivio = letture()
    viste = archivio.viste(utente_corrente_id())
    result['nonLette'] = int(archivio.non_viste(utente_corrente_id()))
    for voce in result['voci']:
        voce['giaLetta'] = viste.get((voce['fascicoloId'],voce['codice'],voce['chiave'])) == voce['revisione']
    result['ok'] = True
    return result
