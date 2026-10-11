const enc = new TextEncoder()
export const b64 = bytes => {
  const data = new Uint8Array(bytes); let text = ''
  for (let offset=0;offset<data.length;offset+=8192) text += String.fromCharCode(...data.subarray(offset,offset+8192))
  return btoa(text)
}
export const unb64 = value => Uint8Array.from(atob(value), c => c.charCodeAt(0))
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']'
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}'
  return JSON.stringify(value)
}
export async function hash(value) {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(canonical(value))))
  return Array.from(bytes, x => x.toString(16).padStart(2,'0')).join('')
}
export async function createCredential() {
  const pair = await crypto.subtle.generateKey({name:'ECDSA', namedCurve:'P-256'}, false, ['sign','verify'])
  return {privateKey:pair.privateKey, public_key:b64(await crypto.subtle.exportKey('spki',pair.publicKey))}
}
export async function sign(key, message) {
  return b64(await crypto.subtle.sign({name:'ECDSA', hash:'SHA-256'}, key, enc.encode(message)))
}
export async function derive(password, salt) {
  if (typeof password !== 'string' || password.length < 14) throw new Error('Usa una frase segreta di almeno 14 caratteri.')
  const material = await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey'])
  return crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt:unb64(salt),iterations:600000},material,
    {name:'AES-GCM',length:256},false,['encrypt','decrypt'])
}
export async function seal(key, scope, value) {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  return {iv:b64(iv), ciphertext:b64(await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:enc.encode(scope)},key,enc.encode(JSON.stringify(value))))}
}
export async function open(key, scope, value) {
  const data = await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(value.iv),additionalData:enc.encode(scope)},key,unb64(value.ciphertext))
  return JSON.parse(new TextDecoder().decode(data))
}
