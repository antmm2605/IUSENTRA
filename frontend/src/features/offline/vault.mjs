import {b64,derive,seal,open} from './crypto.mjs'
let database
async function db() {
  if (!database) database = await new Promise((resolve,reject) => {
    const req = indexedDB.open('iusentra-approved-offline-v1',1)
    req.onupgradeneeded = () => req.result.createObjectStore('vaults',{keyPath:'scope'})
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return database
}
export async function store(action, value) {
  const connection = await db()
  return new Promise((resolve,reject) => {
    const tx = connection.transaction('vaults',action === 'getAll' ? 'readonly':'readwrite')
    const req = tx.objectStore('vaults')[action](value)
    tx.oncomplete = () => resolve(req.result)
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('Salvataggio locale interrotto.'))
  })
}
export const listVaults = () => store('getAll')
export const removeVault = scope => store('delete',scope)
export function assertLease(state, now=Date.now()) {
  if (!state.lease_until || now >= state.lease_until*1000 || now < state.last_seen-300000) {
    throw new Error('Autorizzazione offline scaduta. Collegati e accedi nuovamente a IUSENTRA.')
  }
}
export async function unlock(record,password) {
  const key = await derive(password,record.salt)
  let state = {cursor:0,notes:{},queue:[],lease_until:0,last_seen:Date.now()}
  if (record.encrypted) {
    try { state = await open(key,record.scope,record.encrypted) }
    catch { throw new Error('Frase segreta errata o archivio locale danneggiato.') }
  }
  return {record,key,state}
}
export async function createVault(metadata,credential,password) {
  const record = {...metadata,privateKey:credential.privateKey,salt:b64(crypto.getRandomValues(new Uint8Array(16)))}
  const vault = await unlock(record,password)
  // Registration metadata only. No study records before server approval.
  await store('put',record)
  return vault
}
export async function persist(vault,state) {
  const next = {...state,last_seen:Math.max(state.last_seen || 0,Date.now())}
  const record = {...vault.record,encrypted:await seal(vault.key,vault.record.scope,next)}
  // One IndexedDB transaction: queue, data, cursor and lease commit together.
  await store('put',record)
  vault.record = record; vault.state = next
  return next
}
