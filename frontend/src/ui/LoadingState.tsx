import './ui.css'

export function LoadingState({
  title = 'Caricamento in corso',
  message = 'Stiamo recuperando i dati reali dello studio.',
}: {
  title?: string
  message?: string
}) {
  return (
    <section className="iu-loading-state" aria-live="polite" aria-busy="true">
      <div className="iu-loading-state__body">
        <span className="iu-loading-state__spinner" aria-hidden="true" />
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
    </section>
  )
}
