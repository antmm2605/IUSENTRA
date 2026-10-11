import React, {useEffect,useRef,useState} from 'react'
import {createCredential} from './crypto.mjs'
import {assertLease,createVault,listVaults,unlock,removeVault} from './vault.mjs'
import {request,proof,synchronize} from './sync.mjs'
import {DevicePanel} from './DevicePanel.jsx'
import {NotesPanel} from './NotesPanel.jsx'
import './offline.css'
export function OfflineWorkspace() {
  const [context,setContext] = useState(null), [records,setRecords] = useState([]), [vault,setVault] = useState(null)
  const [label,setLabel] = useState(''), [password,setPassword] = useState(''), [selected,setSelected] = useState('')
  const [message,setMessage] = useState(''), [busy,setBusy] = useState(false), [leaseValid,setLeaseValid] = useState(false)
  const [,render] = useState(0), release = useRef(null), active = useRef(null), running = useRef(false)
  const refresh = () => render(value => value+1)
  const run = async action => {
    if (running.current) return
    running.current=true;setBusy(true);setMessage('')
    try { await action() } catch (error) {setMessage(error.message); if (!active.current?.key) setLeaseValid(false)}
    finally {running.current=false;setBusy(false)}
  }
  const reload = async () => {setContext(await request('/context'));setRecords(await listVaults())}
  const lock = () => {release.current?.();release.current=null;active.current=null;setVault(null);setLeaseValid(false);setPassword('')}
  const hold = async record => {
    if (!navigator.locks) throw new Error('Usa un browser aggiornato per il lavoro offline.')
    await new Promise((resolve,reject) => {
      navigator.locks.request('iusentra-offline-session:'+record.scope,{ifAvailable:true},async acquired => {
        if (!acquired) {reject(new Error('Questo archivio è già aperto in un’altra scheda.'));return}
        await new Promise(done => {release.current=done;resolve()})
      }).catch(reject)
    })
  }
  const update = async () => {
    let current
    try {current = await request('/context')} catch (error) {if (error.status === 403) lock();throw error}
    if (current.tenant !== active.current.record.tenant || current.actor !== active.current.record.actor) {lock();throw new Error('Accedi con l’identità associata a questo archivio.')}
    setContext(current)
    assertLease({lease_until:Number.MAX_SAFE_INTEGER,last_seen:active.current.state.last_seen})
    const device = current.devices.find(item => item.id === active.current.record.id)
    if (device?.status === 'pending') {
      if (!device.proven) await request(`/devices/${device.id}/prove`,{proof:await proof(active.current,'enroll',current.csrf)},current.csrf)
      setLeaseValid(false);setMessage('Computer in attesa di approvazione. Confronta il codice con l’amministratore.');return
    }
    await synchronize(active.current,current);assertLease(active.current.state);setLeaseValid(true);refresh()
    setMessage('Sincronizzazione confermata. Le modifiche con conflitti richiedono una scelta.')
  }
  useEffect(() => {
    listVaults().then(setRecords).catch(() => setMessage('Archivio locale non disponibile.'))
    request('/context').then(setContext).catch(() => setMessage('Per registrare o aggiornare questo computer, accedi a IUSENTRA online.'))
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {})
    return () => release.current?.()
  },[])
  useEffect(() => {
    const online = () => {if (active.current) run(update)}
    window.addEventListener('online',online)
    let activity = Date.now()
    const touch = () => {activity=Date.now()}
    window.addEventListener('pointerdown',touch);window.addEventListener('keydown',touch)
    const timer = setInterval(() => {
      if (active.current && Date.now()-activity > 300000) {lock();setMessage('Archivio bloccato dopo cinque minuti di inattività.')}
      else if (active.current && leaseValid) {
        try {assertLease(active.current.state)} catch (error) {setLeaseValid(false);setMessage(error.message)}
      }
    },10000)
    return () => {clearInterval(timer);window.removeEventListener('online',online);window.removeEventListener('pointerdown',touch);window.removeEventListener('keydown',touch)}
  },[leaseValid])
  const register = async () => {
    if (!context) throw new Error('Accedi online prima di registrare il computer.')
    // Derivation validates the passphrase before creating a server request.
    const credential = await createCredential()
    const {derive,b64} = await import('./crypto.mjs');await derive(password,b64(crypto.getRandomValues(new Uint8Array(16))))
    const registration = await request('/devices',{label,public_key:credential.public_key},context.csrf)
    const scope = `${registration.tenant}:${registration.actor}:${registration.id}`
    const created = await createVault({...registration,scope,label},credential,password)
    await request(`/devices/${created.record.id}/prove`,{proof:await proof(created,'enroll',context.csrf)},context.csrf)
    setPassword('');await reload();setSelected(scope);setMessage('Registrazione verificata. Fai approvare il computer confrontando il codice.')
  }
  const unlockSelected = async () => {
    const record = records.find(item => item.scope===selected)
    if (!record) throw new Error('Seleziona un archivio registrato.')
    await hold(record)
    try {
      const current = await unlock(record,password);active.current=current;setVault(current);setPassword('')
      if (navigator.onLine) await update()
      else {assertLease(current.state);setLeaseValid(true)}
    } catch (error) {lock();throw error}
  }
  return <main className="offline-workspace" aria-busy={busy}>
    <header><h1>IUSENTRA · Lavoro offline</h1><a href="/app-v2">Torna al gestionale online</a></header>
    <p>Solo i computer approvati conservano note e documenti cifrati. La modalità ordinaria resta online. Questa prima area comprende note personali e allegati di testo, non l’intero archivio.</p>
    {message && <p role="status" className="offline-message">{message}</p>}
    <fieldset disabled={busy}>
      {!vault ? <section><h2>Apri archivio autorizzato</h2>
        <label>Computer registrato<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Seleziona</option>{records.map(record => <option key={record.scope} value={record.scope}>{record.label}</option>)}</select></label>
        <label>Frase segreta locale<input type="password" autoComplete="off" minLength={14} value={password} onChange={e => setPassword(e.target.value)} /></label>
        <button onClick={() => run(unlockSelected)} disabled={!selected}>Sblocca archivio</button>
        <button onClick={() => run(async () => {if (!window.confirm('Rimuovere la copia locale? Le modifiche non sincronizzate andranno perse.')) return;await removeVault(selected);setRecords(await listVaults())})} disabled={!selected}>Rimuovi copia locale</button>
        {context && <><h2>Registra questo computer</h2><label>Nome del computer<input maxLength={80} value={label} onChange={e => setLabel(e.target.value)} /></label>
          <p>Usa una frase segreta di almeno 14 caratteri nel campo sopra. Non viene inviata al server. La registrazione conserva solo la credenziale; i dati arrivano dopo l’approvazione.</p>
          <button onClick={() => run(register)} disabled={!label || password.length<14}>Richiedi autorizzazione</button></>}
      </section>:<section><h2>{vault.record.label}</h2><p>Modifiche in attesa: {vault.state.queue.length}</p>
        {leaseValid && <p>Autorizzazione offline fino al {new Date(vault.state.lease_until*1000).toLocaleString('it-IT',{timeZone:'Europe/Rome'})}.</p>}
        <button onClick={() => run(update)}>Sincronizza</button><button onClick={lock}>Blocca archivio</button>
        <details><summary>Codice di verifica del computer</summary><p className="offline-code">{vault.record.fingerprint}</p></details>
      </section>}
      {vault && leaseValid && <NotesPanel vault={vault} run={run} refresh={refresh} />}
      {context && <DevicePanel context={context} reload={reload} run={run} />}
    </fieldset>
  </main>
}
