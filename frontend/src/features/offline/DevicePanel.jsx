import React, {useState} from 'react'
import {request} from './sync.mjs'
export function DevicePanel({context,reload,run}) {
  const [verification,setVerification] = useState({})
  const [events,setEvents] = useState(null)
  return <section><h2>Computer dello studio</h2>
    <p>Prima di approvare, confronta il codice con quello mostrato sul computer da autorizzare. Il nome del computer da solo non ne prova l’identità.</p>
    {!context.devices.length && <p>Nessun computer registrato.</p>}
    {context.devices.map(device => <article key={device.id}>
      <h3>{device.label}</h3><p>{({pending:'In attesa di approvazione',approved:'Approvato',revoked:'Revocato'})[device.status]}</p>
      <details><summary>Codice di verifica</summary><p className="offline-code">{device.fingerprint}</p></details>
      {context.admin && device.status === 'pending' && <>
        <label>Codice verificato sul computer<input value={verification[device.id] || ''} onChange={e => setVerification({...verification,[device.id]:e.target.value})} /></label>
        <button disabled={!device.proven || verification[device.id] !== device.fingerprint} onClick={() => run(async () => {
          await request(`/devices/${device.id}/approve`,{fingerprint:verification[device.id]},context.csrf); await reload()
        })}>Approva computer</button>
        {!device.proven && <p>La prova di registrazione deve ancora essere eseguita dal computer.</p>}
      </>}
      {device.status !== 'revoked' && <button onClick={() => run(async () => {
        if (!window.confirm('Revocare questo computer? Non potrà più sincronizzare. Se scollegato, la copia già autorizzata resta accessibile fino alla scadenza.')) return
        await request(`/devices/${device.id}/revoke`,{},context.csrf); await reload()
      })}>Revoca</button>}
    </article>)}
    {context.admin && <><button onClick={() => run(async () => setEvents((await request('/audit')).events))}>Consulta registro</button>
      {events && <ul>{events.map((event,index) => <li key={index}>{new Date(event.at*1000).toLocaleString('it-IT',{timeZone:'Europe/Rome'})} · {({
        'device.registered':'Registrazione richiesta','device.proven':'Registrazione verificata','device.approve':'Computer approvato','device.revoke':'Computer revocato',
        'notes.sync':'Note sincronizzate','note.saved':'Nota salvata','note.deleted':'Nota eliminata'})[event.action] || 'Operazione registrata'}</li>)}</ul>}
    </>}
  </section>
}
