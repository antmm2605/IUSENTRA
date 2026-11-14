import { useEffect, useState } from 'react'
import { CampoData } from '../ui/CampoData'
import type { PayloadSito, PercorsiSito } from './tipi'

/** Moduli del sito pubblico: inviati con un POST classico allo stesso indirizzo, funzionano anche senza JavaScript. */
export function ModuloContatto({ percorsi }: { percorsi: PercorsiSito }) {
  return (
    <form method="post" action={percorsi.contatti} className="studio-site-form">
      <div className="row g-3">
        <div className="col-md-6"><label className="form-label" htmlFor="contatto-nome">Nome e cognome</label><input className="form-control" id="contatto-nome" name="full_name" required/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="contatto-email">Email</label><input className="form-control" id="contatto-email" name="email" type="email" required/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="contatto-telefono">Telefono</label><input className="form-control" id="contatto-telefono" name="phone"/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="contatto-oggetto">Oggetto</label><input className="form-control" id="contatto-oggetto" name="subject"/></div>
        <div className="col-12"><label className="form-label" htmlFor="contatto-messaggio">Messaggio</label><textarea className="form-control" id="contatto-messaggio" name="message" rows={5} required/></div>
        <div className="col-12">
          <div className="form-check">
            <input className="form-check-input" type="checkbox" value="1" id="contactPrivacy" name="privacy_accepted" required/>
            <label className="form-check-label" htmlFor="contactPrivacy">Confermo l'informativa privacy e autorizzo il trattamento dei dati per il riscontro alla richiesta.</label>
          </div>
        </div>
        <div className="col-12"><button className="btn btn-primary" type="submit">Invia richiesta</button></div>
      </div>
    </form>
  )
}

type Fascia = { value?: string; label?: string; time?: string }

/** Richiesta di appuntamento: le fasce libere si leggono dopo la scelta di sede e data. */
export function ModuloPrenotazione({ payload, percorsi }: { payload: PayloadSito; percorsi: PercorsiSito }) {
  const [sede, setSede] = useState('')
  const [data, setData] = useState('')
  const [fasce, setFasce] = useState<Fascia[] | null>(null)
  const [stato, setStato] = useState('Seleziona prima sede e data')
  useEffect(() => {
    if (!sede || !data) { setFasce(null); setStato('Seleziona prima sede e data'); return undefined }
    const controllo = new AbortController()
    setStato('Caricamento delle fasce disponibili…')
    fetch(`${percorsi.slot}?office_id=${encodeURIComponent(sede)}&data=${encodeURIComponent(data)}`, { signal: controllo.signal, headers: { Accept: 'application/json' } })
      .then((risposta) => risposta.json() as Promise<{ slots?: Fascia[] }>)
      .then((dati) => { const voci = dati.slots || []; setFasce(voci); setStato(voci.length ? 'Seleziona una fascia' : 'Nessuna fascia disponibile in questa data') })
      .catch(() => { if (!controllo.signal.aborted) { setFasce([]); setStato('Fasce non disponibili: riprova o contatta lo studio') } })
    return () => controllo.abort()
  }, [sede, data, percorsi.slot])
  return (
    <form method="post" action={percorsi.prenota} className="studio-site-form">
      <div className="row g-3">
        <div className="col-md-6"><label className="form-label" htmlFor="prenota-nome">Nome e cognome</label><input className="form-control" id="prenota-nome" name="customer_name" required/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="prenota-email">Email</label><input className="form-control" id="prenota-email" name="customer_email" type="email" required/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="prenota-telefono">Telefono</label><input className="form-control" id="prenota-telefono" name="customer_phone"/></div>
        <div className="col-md-6"><label className="form-label" htmlFor="prenota-oggetto">Oggetto</label><input className="form-control" id="prenota-oggetto" name="subject" placeholder="Es. prima consulenza, esame documenti, parere"/></div>
        <div className="col-md-6">
          <label className="form-label" htmlFor="prenota-sede">Sede</label>
          <select className="form-select" id="prenota-sede" name="office_id" required value={sede} onChange={(evento) => setSede(evento.target.value)}>
            <option value="">Seleziona una sede</option>
            {payload.offices.map((voce) => <option key={voce.id} value={String(voce.id)}>{voce.name}</option>)}
          </select>
        </div>
        <div className="col-md-6">
          <label className="form-label" htmlFor="prenota-data">Data</label>
          <CampoData id="prenota-data" name="requested_date" required value={data} onChange={setData} classeTesto="form-control"/>
        </div>
        <div className="col-md-6">
          <label className="form-label" htmlFor="prenota-fascia">Fascia disponibile</label>
          <select className="form-select" id="prenota-fascia" name="requested_time" required>
            <option value="">{stato}</option>
            {(fasce || []).map((fascia, numero) => {
              const valore = fascia.value || fascia.time || ''
              return <option key={numero} value={valore}>{fascia.label || valore}</option>
            })}
          </select>
        </div>
        <div className="col-12"><label className="form-label" htmlFor="prenota-note">Note</label><textarea className="form-control" id="prenota-note" rows={4} name="notes" placeholder="Inserisci brevemente il contesto della richiesta"/></div>
        <div className="col-12">
          <div className="form-check">
            <input className="form-check-input" type="checkbox" id="bookingPrivacy" name="privacy_accepted" value="1" required/>
            <label className="form-check-label" htmlFor="bookingPrivacy">Confermo l'informativa privacy e autorizzo l'uso dei dati per la gestione della richiesta appuntamento.</label>
          </div>
        </div>
        <div className="col-12"><button className="btn btn-primary btn-lg" type="submit">Invia richiesta appuntamento</button></div>
      </div>
    </form>
  )
}
