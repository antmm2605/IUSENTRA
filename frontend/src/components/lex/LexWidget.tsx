import { useEffect } from 'react'

/**
 * Widget flottante di Lex nelle pagine React (prima `components/pct_ai_widget.html` incluso dalla shell).
 * Il markup (id, classi, attributi data-*) è il contratto del controllore `static/js/pct-lex-assistant.js`,
 * che resta l'unico a gestire conversazione, allegati, voce, trascinamento e ridimensionamento: questo
 * componente lo monta una volta, in una radice React propria, e poi non lo ridisegna più.
 */
export const EVENTO_LEX_WIDGET_MONTATO = 'iusentra:lex-widget-montato'

const URL_ASSISTENTE = {
  chat: '/api/assistente/chat',
  stato: '/api/assistente/stato',
  contesto: '/api/assistente/context',
  riscaldamento: '/api/assistente/warmup',
  allegati: '/api/assistente/attachments',
  documento: '/api/assistente/documento',
}

function modalitaAi(): 'local' | 'remote' {
  return ['localhost', '127.0.0.1'].includes(window.location.hostname) ? 'local' : 'remote'
}

export function LexWidget({ versione = '' }: { versione?: string }) {
  const icona = `/static/img/lex-mark.png?v=${encodeURIComponent(versione)}`
  useEffect(() => {
    // Il controllore si avvia al DOMContentLoaded; se il widget arriva dopo, lo avvia questo evento.
    window.dispatchEvent(new CustomEvent(EVENTO_LEX_WIDGET_MONTATO))
  }, [])
  return (
    <div
      id="pct-ai-widget"
      className="pct-ai-widget"
      data-ai-mode={modalitaAi()}
      data-chat-url={URL_ASSISTENTE.chat}
      data-status-url={URL_ASSISTENTE.stato}
      data-server-context-url={URL_ASSISTENTE.contesto}
      data-warmup-url={URL_ASSISTENTE.riscaldamento}
      data-server-attachments-url={URL_ASSISTENTE.allegati}
      data-export-document-url={URL_ASSISTENTE.documento}
      data-local-signer-url="http://127.0.0.1:27272"
      data-page-path={window.location.pathname}
      data-page-endpoint=""
      data-local-signer-download-page={`${window.location.origin}/impostazioni?tab=firma`}
      data-local-signer-setup-windows="/polisWeb/local-signer/setup/windows"
      data-local-signer-setup-macos="/polisWeb/local-signer/setup/macos"
      data-local-signer-setup-linux="/polisWeb/local-signer/setup/linux"
      data-lex-icon-url={icona}
      data-storage-key="iusentra-pct-ai-layout-v1"
    >
      <button id="pct-ai-fab" className="pct-ai-fab" type="button" title="Apri l'assistente Lex" aria-label="Apri l'assistente Lex" aria-expanded="false">
        <span className="pct-ai-fab__halo" aria-hidden="true"/>
        <span className="pct-ai-fab__icon">
          <img src={icona} alt="" aria-hidden="true" className="pct-ai-brand-mark pct-ai-brand-mark--fab"/>
        </span>
        <span className="visually-hidden">Apri l'assistente Lex</span>
      </button>

      <section id="pct-ai-panel" className="pct-ai-panel" hidden role="dialog" aria-label="Lex, l'assistente" aria-modal="false">
        <header id="pct-ai-header" className="pct-ai-header" data-pct-ai-drag-handle="true" title="Trascina il pannello per spostarlo">
          <div className="pct-ai-header__brand">
            <div className="pct-ai-header__icon">
              <img src={icona} alt="" aria-hidden="true" className="pct-ai-brand-mark pct-ai-brand-mark--header"/>
            </div>
            <div className="pct-ai-header__copy">
              <div className="pct-ai-header__meta">
                <span id="pct-ai-model-badge" className="pct-ai-model-badge">Verifica modello</span>
                <span id="pct-ai-voice-badge" className="pct-ai-model-badge">Voce pronta</span>
                <span className="pct-ai-drag-hint"><i className="bi bi-grip-horizontal"/> Trascina</span>
              </div>
            </div>
          </div>
          <div className="pct-ai-header__actions">
            <button id="pct-ai-fullscreen" className="pct-ai-hbtn" type="button" title="Apri Lex a tutto schermo" aria-label="Apri Lex a tutto schermo">
              <i className="bi bi-arrows-fullscreen"/>
            </button>
            <button id="pct-ai-close" className="pct-ai-hbtn" type="button" title="Chiudi assistente" aria-label="Chiudi assistente">
              <i className="bi bi-x-lg"/>
            </button>
          </div>
        </header>

        <div id="pct-ai-ctx" className="pct-ai-ctx" hidden>
          <i className="bi bi-folder2-open"/>
          <span id="pct-ai-ctx-label"/>
        </div>

        <div id="pct-ai-messages" className="pct-ai-messages">
          <div className="pct-ai-msg pct-ai-msg--assistant">
            <div className="pct-ai-avatar pct-ai-avatar--ai">
              <img src={icona} alt="" aria-hidden="true" className="pct-ai-brand-mark pct-ai-brand-mark--avatar"/>
            </div>
            <div className="pct-ai-bubble">
              <p className="mb-0">Ciao, sono Lex.</p>
            </div>
          </div>
        </div>

        <footer className="pct-ai-footer">
          <div id="pct-ai-attachments" className="pct-ai-attachments" hidden/>
          <div className="pct-ai-composer">
            <div className="pct-ai-input-wrap">
              <textarea id="pct-ai-input" className="pct-ai-input" placeholder="Scrivi a Lex…" aria-label="Scrivi a Lex" rows={1}/>
            </div>
            <div className="pct-ai-toolbar" aria-label="Strumenti rapidi Lex">
              <label htmlFor="pct-ai-upload" className="pct-ai-tool-btn pct-ai-tool-btn--upload" title="Carica documenti nel contesto di Lex" aria-label="Carica documenti nel contesto di Lex">
                <i className="bi bi-file-earmark-arrow-up"/>
                <span>Carica documenti</span>
              </label>
              <input id="pct-ai-upload" className="pct-ai-upload-input" type="file" multiple accept=".pdf,.docx,.txt,.md,.json,.html,.htm,.csv"/>
              <button id="pct-ai-mic" className="pct-ai-tool-btn" type="button" title="Detta la richiesta a Lex" aria-label="Detta la richiesta a Lex">
                <i className="bi bi-mic-fill"/>
                <span>Microfono</span>
              </button>
              <button id="pct-ai-free-web" className="pct-ai-tool-btn" type="button" title="Cerca anche sulle pagine web pubbliche, solo per le prossime domande" aria-label="Cerca anche sulle pagine web pubbliche" aria-pressed="false">
                <i className="bi bi-globe2"/>
                <span>Cerca sul web</span>
              </button>
              <button id="pct-ai-export" className="pct-ai-tool-btn" type="button" title="Scarica il riepilogo della conversazione" aria-label="Scarica il riepilogo della conversazione">
                <i className="bi bi-download"/>
              </button>
              <button id="pct-ai-voice-toggle" className="pct-ai-tool-btn" type="button" title="Attiva o disattiva la risposta vocale" aria-label="Attiva o disattiva la risposta vocale">
                <i className="bi bi-volume-up-fill"/>
              </button>
              <button id="pct-ai-clear" className="pct-ai-tool-btn" type="button" title="Nuova conversazione" aria-label="Nuova conversazione">
                <i className="bi bi-arrow-counterclockwise"/>
              </button>
              <button id="pct-ai-send" className="pct-ai-send-btn" type="button" title="Invia domanda" aria-label="Invia domanda">
                <i className="bi bi-send-fill"/>
              </button>
            </div>
          </div>
          <div className="pct-ai-quickbar" aria-label="Comandi rapidi e stato Lex">
            <span className="pct-ai-quickbar__label">Comandi rapidi</span>
            <div id="pct-ai-presets" className="pct-ai-presets" aria-label="Superfici operative di Lex"/>
            <div id="pct-ai-status" className="pct-ai-status-bar" role="status">Assistente pronto.</div>
            <button id="pct-ai-reset-position" className="pct-ai-tool-btn" type="button" title="Ripristina posizione e dimensioni predefinite" aria-label="Ripristina posizione e dimensioni predefinite">
              <i className="bi bi-arrow-down-right-square"/>
            </button>
          </div>
          <button id="pct-ai-resize-handle" className="pct-ai-resize-handle" type="button" title="Ridimensiona la finestra di Lex" aria-label="Ridimensiona la finestra di Lex">
            <i className="bi bi-arrows-angle-expand"/>
          </button>
        </footer>
      </section>
    </div>
  )
}

export default LexWidget
