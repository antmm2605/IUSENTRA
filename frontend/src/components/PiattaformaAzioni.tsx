import { useId, useState, type FormEvent } from 'react'
import type { AzionePf, CampoPf, ValoriAzione } from '../piattaformaData'
import { Button } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Modal } from '../ui/Modal'

export type EseguiAzione = (azione: AzionePf, values: ValoriAzione) => Promise<void>

function valoriIniziali(fields: CampoPf[]): ValoriAzione {
  return Object.fromEntries(fields.map((campo) => [campo.name, campo.value]))
}

function tonoPulsante(azione: AzionePf) {
  return azione.tone === 'neutral' ? 'neutral' : azione.tone
}

export function CampoAzione({ campo, value, onChange }: { campo: CampoPf; value: string | boolean; onChange: (value: string | boolean) => void }) {
  const id = `pf-campo-${campo.name}-${useId().replace(/:/g, '')}`
  if (campo.kind === 'checkbox') {
    return (
      <label className="iu-pf-field is-checkbox" htmlFor={id}>
        <input id={id} type="checkbox" checked={value === true} onChange={(event) => { const checked = event.currentTarget.checked; onChange(checked) }} />
        <span>{campo.label}</span>
        {campo.help ? <small>{campo.help}</small> : null}
      </label>
    )
  }
  return (
    <label className="iu-pf-field" htmlFor={id}>
      <span>{campo.label}{campo.required ? ' *' : ''}</span>
      {campo.kind === 'select' ? (
        <select id={id} value={String(value)} required={campo.required} onChange={(event) => { const next = event.currentTarget.value; onChange(next) }}>
          {campo.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : campo.kind === 'textarea' ? (
        <textarea id={id} value={String(value)} required={campo.required} placeholder={campo.placeholder} rows={4} onChange={(event) => { const next = event.currentTarget.value; onChange(next) }} />
      ) : (
        <input
          id={id}
          type={campo.kind}
          value={String(value)}
          required={campo.required}
          placeholder={campo.placeholder}
          autoComplete={campo.kind === 'password' ? 'new-password' : undefined}
          onChange={(event) => { const next = event.currentTarget.value; onChange(next) }}
        />
      )}
      {campo.help ? <small>{campo.help}</small> : null}
    </label>
  )
}

function CampiAzione({ fields, values, onChange }: { fields: CampoPf[]; values: ValoriAzione; onChange: (name: string, value: string | boolean) => void }) {
  return (
    <div className="iu-pf-fields">
      {fields.map((campo) => (
        <CampoAzione key={campo.name} campo={campo} value={values[campo.name] ?? ''} onChange={(value) => onChange(campo.name, value)} />
      ))}
    </div>
  )
}

/** Pulsante di un'azione: chiede conferma o apre i campi da compilare, poi la esegue. */
export function PulsanteAzione({ azione, disabled, onRun, compact = false }: { azione: AzionePf; disabled: boolean; onRun: EseguiAzione; compact?: boolean }) {
  const [aperta, setAperta] = useState(false)
  const [values, setValues] = useState<ValoriAzione>(() => valoriIniziali(azione.fields))

  function avvia() {
    if (azione.fields.length || azione.confirm) {
      setValues(valoriIniziali(azione.fields))
      setAperta(true)
      return
    }
    void onRun(azione, {})
  }

  async function invia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAperta(false)
    await onRun(azione, values)
  }

  return (
    <>
      <Button type="button" tone={tonoPulsante(azione)} className={compact ? 'iu-pf-action is-compact' : 'iu-pf-action'} disabled={disabled} onClick={avvia} title={azione.detail || undefined}>
        {azione.label}
      </Button>
      {azione.fields.length ? (
        <Modal title={azione.label} open={aperta} onClose={() => setAperta(false)}>
          <form className="iu-pf-action-form" onSubmit={invia}>
            {azione.detail ? <p>{azione.detail}</p> : null}
            {azione.confirm ? <p className="iu-pf-confirm">{azione.confirm}</p> : null}
            <CampiAzione fields={azione.fields} values={values} onChange={(name, value) => setValues((prev) => ({ ...prev, [name]: value }))} />
            <div className="iu-modal__actions">
              <Button tone="neutral" type="button" onClick={() => setAperta(false)}>Annulla</Button>
              <Button type="submit" tone={azione.tone === 'danger' ? 'danger' : 'primary'}>Conferma</Button>
            </div>
          </form>
        </Modal>
      ) : (
        <ConfirmDialog
          title={azione.label}
          message={azione.confirm}
          open={aperta}
          onCancel={() => setAperta(false)}
          onConfirm={() => { setAperta(false); void onRun(azione, {}) }}
        />
      )}
    </>
  )
}

/** Modulo in pagina che invia un'azione con i valori dei campi. */
export function ModuloAzione({ azione, fields, disabled, onRun }: { azione: AzionePf; fields: CampoPf[]; disabled: boolean; onRun: EseguiAzione }) {
  const [values, setValues] = useState<ValoriAzione>(() => valoriIniziali(fields))

  async function invia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onRun(azione, values)
  }

  return (
    <form className="iu-pf-action-form" onSubmit={invia}>
      <CampiAzione fields={fields} values={values} onChange={(name, value) => setValues((prev) => ({ ...prev, [name]: value }))} />
      <div>
        <Button type="submit" tone="primary" disabled={disabled}>{azione.label}</Button>
      </div>
    </form>
  )
}
