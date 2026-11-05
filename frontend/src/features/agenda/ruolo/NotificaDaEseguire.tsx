/** Che cosa notificare, a chi, come e che cosa depositare dopo, con le norme (pct/notifiche_obblighi). */

export type SchedaNotifica = {
  atti: string
  destinatari: string
  aCuraDi: string
  come: Array<{ testo: string; norme: string[] }>
  avvertenze: string[]
  dopo: string[]
  norme: Array<{ id: string; norma: string; url: string }>
  preparaHref: string
}

export function NotificaDaEseguire({ scheda, aperta = false }: { scheda?: SchedaNotifica; aperta?: boolean }) {
  if (!scheda || !scheda.atti) return null
  return (
    <details className="iu-ruolo-notifica" open={aperta}>
      <summary>{aperta ? 'Atti, destinatari e norme' : 'Notifica da eseguire: atti, destinatari e norme'}</summary>
      <dl>
        <dt>Atti</dt><dd>{scheda.atti}</dd>
        <dt>Destinatari</dt><dd>{scheda.destinatari}</dd>
        <dt>A cura di</dt><dd>{scheda.aCuraDi}</dd>
      </dl>
      {scheda.come.length ? (
        <>
          <h4>Come si notifica</h4>
          <ol>{scheda.come.map((passo) => <li key={passo.testo}>{passo.testo}</li>)}</ol>
        </>
      ) : null}
      {scheda.avvertenze.length ? <ul className="iu-ruolo-notifica__avvertenze">{scheda.avvertenze.map((a) => <li key={a}>{a}</li>)}</ul> : null}
      {scheda.dopo.length ? (
        <>
          <h4>Dopo la notifica</h4>
          <ul>{scheda.dopo.map((passo) => <li key={passo}>{passo}</li>)}</ul>
        </>
      ) : null}
      {scheda.norme.length ? (
        <p className="iu-ruolo-notifica__norme">
          {scheda.norme.map((n, i) => (
            <span key={n.id}>{i ? ' · ' : ''}<a href={n.url} target="_blank" rel="noreferrer">{n.norma}</a></span>
          ))}
        </p>
      ) : null}
      {scheda.preparaHref ? <div className="iu-ruolo-azioni"><a className="is-principale" href={scheda.preparaHref}>Prepara la notifica</a></div> : null}
    </details>
  )
}
