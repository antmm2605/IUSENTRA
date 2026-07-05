import {
  BookOpenCheck,
  FilePlus2,
  FileSearch,
  FileText,
  Mail,
  PenLine,
  SearchCheck,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './EditorProfessionalePage.css'

const workbenchActions = [
  {
    title: 'Editor libero',
    text: 'Apre subito un foglio vuoto con timbro studio, formattazione, import e salvataggio nel fascicolo.',
    href: '/template-atti/editor',
    icon: FilePlus2,
    tone: 'primary' as const,
  },
  {
    title: 'Redazione atti',
    text: 'Crea e corregge atti, bozze e modelli collegati ai fascicoli.',
    href: '/redazione-atti',
    icon: PenLine,
    tone: 'neutral' as const,
  },
  {
    title: 'Modelli atti',
    text: 'Apre il catalogo dei template e dei percorsi di compilazione.',
    href: '/template-atti/catalogo',
    icon: BookOpenCheck,
    tone: 'neutral' as const,
  },
  {
    title: 'Documenti fascicolo',
    text: 'Consulta, visualizza, firma e scarica i documenti collegati.',
    href: '/fascicoli',
    icon: FileText,
    tone: 'neutral' as const,
  },
  {
    title: 'Ricerca documenti',
    text: 'Cerca atti, allegati, email, PEC e contenuti indicizzati nello studio.',
    href: '/global-search?tipo=documenti',
    icon: FileSearch,
    tone: 'neutral' as const,
  },
]

const readerFormats = ['PDF', 'PDF.P7M', 'XML', 'XML.P7M', 'EML', 'TXT']

export function EditorProfessionalePage() {
  return (
    <Page
      title="Editor professionale"
      subtitle="Scrittura, controllo, ricerca, allegati firmati e Lex nello stesso spazio operativo."
      actions={
        <>
          <ButtonLink href="/template-atti/editor" tone="primary"><FilePlus2 size={15} /> Editor libero</ButtonLink>
          <ButtonLink href="/redazione-atti" tone="neutral"><PenLine size={15} /> Redazione atti</ButtonLink>
          <ButtonLink href="/global-search?tipo=documenti" tone="neutral"><FileSearch size={15} /> Cerca documenti</ButtonLink>
        </>
      }
    >
      <section className="iu-editor-pro-hero" aria-label="Funzioni editor professionale">
        <article>
          <Badge tone="success"><ShieldCheck size={13} /> Studio protetto</Badge>
          <h2>Area operativa documenti</h2>
          <p>
            Redigi, controlla e apri i documenti dello studio mantenendo separata la
            Redazione Atti quando serve il modulo specifico degli atti.
          </p>
        </article>
        <div className="iu-editor-pro-quick">
          <span><SearchCheck size={16} /> Controllo contenuti</span>
          <span><Mail size={16} /> PEC ed email</span>
          <span><Sparkles size={16} /> Lex editor</span>
        </div>
      </section>

      <Panel title="Strumenti principali" subtitle="Azioni rapide per il lavoro documentale quotidiano.">
        <div className="iu-editor-pro-actions">
          {workbenchActions.map((action) => {
            const Icon = action.icon
            return (
              <article key={action.title}>
                <div>
                  <Icon size={18} />
                  <strong>{action.title}</strong>
                  <span>{action.text}</span>
                </div>
                <ButtonLink href={action.href} tone={action.tone}>Apri</ButtonLink>
              </article>
            )
          })}
        </div>
      </Panel>

      <Panel title="Lettore documenti legali" subtitle="Anteprima diretta per fascicoli, PEC ed email ordinaria.">
        <div className="iu-editor-pro-reader">
          <div>
            <strong>Formati presidiati</strong>
            <p>Il download conserva l'originale; l'anteprima mostra il contenuto leggibile quando il formato lo consente.</p>
          </div>
          <div aria-label="Formati leggibili">
            {readerFormats.map((format) => <Badge tone="primary" key={format}>{format}</Badge>)}
          </div>
        </div>
      </Panel>
    </Page>
  )
}

export default EditorProfessionalePage
