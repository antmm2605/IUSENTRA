import {hash,sign} from './crypto.mjs'
import {assertLease,persist,removeVault} from './vault.mjs'
export async function request(path,body,csrf='') {
  const response = await fetch('/api/v1/offline'+path,{method:body ? 'POST':'GET',cache:'no-store',credentials:'same-origin',
    headers:{'Accept':'application/json',...(body ? {'Content-Type':'application/json','X-CSRF-Token':csrf}:{})},
    ...(body ? {body:JSON.stringify(body)}:{})})
  let data
  try { data = await response.json() } catch { throw new Error('Accedi a IUSENTRA online prima di sincronizzare.') }
  if (!response.ok || data.ok !== true) {
    const error = new Error(data.message || 'Aggiornamento non confermato.'); error.status = response.status; throw error
  }
  return data
}
export async function proof(vault,purpose,csrf) {
  const challenge = await request(`/devices/${vault.record.id}/challenge`,{purpose},csrf)
  return {challenge:challenge.challenge,signature:await sign(vault.record.privateKey,challenge.message)}
}
export function reconcile(state, response) {
  const notes = {...state.notes}, queue = [...state.queue]
  for (const change of response.changes) notes[change.id] = change
  for (const result of response.results) {
    const index = queue.findIndex(op => op.command === result.command)
    if (index < 0) throw new Error('Conferma della modifica non riconosciuta.')
    if (result.status === 'accepted') queue.splice(index,1)
    else if (result.status === 'conflict') queue[index] = {...queue[index],conflict:result.current || {version:0,deleted:true}}
    else throw new Error('Esito della modifica non riconosciuto.')
  }
  if (response.authorized_ids) {
    const allowed = new Set(response.authorized_ids)
    for (const id of Object.keys(notes)) if (!allowed.has(id)) delete notes[id]
  }
  return {...state,notes,queue,cursor:response.cursor,lease_until:response.lease_until,cases:response.cases || state.cases || [],can_write:response.can_write ?? state.can_write}
}
export async function synchronize(vault,context) {
  if (context.tenant !== vault.record.tenant || context.actor !== vault.record.actor) throw new Error('Questo archivio appartiene a un’altra identità o studio.')
  // One writer across tabs. Lost-response retry retains the original command.
  if (!navigator.locks) throw new Error('Questo browser non supporta la protezione delle modifiche locali.')
  return navigator.locks.request('iusentra-offline:'+vault.record.scope,async () => {
    try {
      let more = true, pages = 0
      while (more && pages++ < 20) {
        const operations = vault.state.queue.filter(op => !op.conflict).slice(0,50).map(({conflict,...op}) => op)
        const intent = {cursor:vault.state.cursor,operations}
        const result = await request(`/devices/${vault.record.id}/sync`,{intent,proof:await proof(vault,'sync:'+await hash(intent),context.csrf)},context.csrf)
        if (result.device !== vault.record.id || result.tenant !== context.tenant || result.actor !== context.actor) throw new Error('Archivio di aggiornamento non riconosciuto.')
        await persist(vault,reconcile(vault.state,result))
        more = result.has_more || vault.state.queue.some(op => !op.conflict)
      }
      return vault.state
    } catch (error) {
      if (error.status === 403) {
        await removeVault(vault.record.scope)
        vault.state = {notes:{},queue:[],lease_until:0,cursor:0,last_seen:Date.now()}
        vault.key = null
        throw new Error('Accesso revocato o non consentito. Archivio locale rimosso da questo browser.')
      }
      throw error
    }
  })
}
export async function saveNote(vault,payload,id=crypto.randomUUID(),deleted=false) {
  assertLease(vault.state)
  if (!vault.state.can_write) throw new Error('Permesso di modifica richiesto.')
  if (vault.state.queue.some(op => op.id === id)) throw new Error('Sincronizza o riconcilia la modifica in attesa prima di modificare ancora questa nota.')
  if (!payload.fascicolo_id || !payload.title?.trim() || payload.title.length>200 || payload.text.length>32000) throw new Error('Completa fascicolo, titolo e testo entro i limiti indicati.')
  if (payload.attachment && (payload.attachment.name.length>120 || new TextEncoder().encode(payload.attachment.text).length>65536)) throw new Error('Documento troppo grande o nome troppo lungo.')
  const op = {command:crypto.randomUUID(),id,base:vault.state.notes[id]?.version || 0,deleted,payload}
  await persist(vault,{...vault.state,queue:[...vault.state.queue,op]})
}
export async function resolveConflict(vault,command,keepLocal) {
  assertLease(vault.state)
  const op = vault.state.queue.find(item => item.command === command)
  if (!op?.conflict) throw new Error('Conflitto non disponibile.')
  let queue = vault.state.queue.filter(item => item.command !== command)
  if (keepLocal) {
    if (op.conflict.deleted) throw new Error('La nota è stata eliminata: crea una nuova nota per conservare la bozza.')
    const {conflict,...original} = op
    queue = [...queue,{...original,base:conflict.version,command:crypto.randomUUID()}]
  }
  await persist(vault,{...vault.state,queue})
}
