import { useState } from 'react'
import type { FonteStesuraLex } from '../../redazioneAttiData'

function Fonte({ fonte }: { fonte: FonteStesuraLex }) {
  const [aperta, setAperta] = useState(false)
  return <details className="iu-rg-lex__verifiche" onToggle={(event) => setAperta(event.currentTarget.open)}>
    <summary>[{fonte.n}] {fonte.etichetta}</summary>
    {aperta ? <div className="iu-rg-lex__blocco">
      <pre className="iu-rg-lex__fonte-testo">{fonte.testo}</pre>
      {fonte.url.startsWith('https://') ? <a href={fonte.url} target="_blank" rel="noopener noreferrer">Consulta anche la fonte ufficiale</a> : null}
    </div> : null}
  </details>
}

export function FontiStesuraLex({ fonti, letture }: { fonti: FonteStesuraLex[]; letture?: { totale: number; perParti: number } }) {
  if (!fonti.length) return null
  return <section aria-label="Testi normativi della stesura">
    <h5>Testi delle fonti</h5>
    {letture?.totale ? <p className="iu-rg-hint">Testi forniti a Lex: {letture.totale}.{letture.perParti ? ` Per ${letture.perParti} testi lunghi è stata usata la lettura per parti, conservando gli originali.` : ''}</p> : null}
    {fonti.map((fonte) => <Fonte key={fonte.n} fonte={fonte} />)}
  </section>
}
