import type { ReactNode } from 'react'
import './ui.css'

type LegacyOption = {
  value: string
  label: string
  description?: string
  enabled?: boolean
}

export type LegacyPostField = {
  name: string
  label: string
  type: 'text' | 'email' | 'password' | 'select' | 'checkbox' | 'hidden'
  required?: boolean
  autocomplete?: string
  minLength?: number
  value?: string
  placeholder?: string
  options?: LegacyOption[]
}

export type LegacyPostFormProps = {
  action: string
  method?: 'POST' | 'post'
  csrfField?: string
  title?: string
  description?: string
  submitLabel: string
  fields?: LegacyPostField[]
  disabled?: boolean
  children?: ReactNode
}

function csrfToken(): string {
  if (typeof document === 'undefined') return ''
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
}

function renderField(field: LegacyPostField) {
  if (field.type === 'hidden') {
    return <input key={field.name} type="hidden" name={field.name} value={field.value || ''} />
  }

  if (field.type === 'select') {
    return (
      <label className="iu-legacy-form__field" key={field.name}>
        <span>{field.label}</span>
        <select name={field.name} required={field.required}>
          {(field.options || []).map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    )
  }

  if (field.type === 'checkbox' && field.options?.length) {
    return (
      <fieldset className="iu-legacy-form__field iu-legacy-form__checks" key={field.name}>
        <legend>{field.label}</legend>
        <div className="iu-legacy-form__check-grid">
          {field.options.map((option) => (
            <label className="iu-legacy-form__check" key={option.value}>
              <input
                type="checkbox"
                name={field.name}
                value={option.value}
                defaultChecked={option.enabled !== false}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    )
  }

  if (field.type === 'checkbox') {
    return (
      <label className="iu-legacy-form__check" key={field.name}>
        <input type="checkbox" name={field.name} value={field.value || '1'} defaultChecked={field.value === '1'} />
        <span>{field.label}</span>
      </label>
    )
  }

  return (
    <label className="iu-legacy-form__field" key={field.name}>
      <span>{field.label}</span>
      <input
        type={field.type}
        name={field.name}
        required={field.required}
        minLength={field.minLength}
        autoComplete={field.autocomplete}
        placeholder={field.placeholder}
        defaultValue={field.value || ''}
      />
    </label>
  )
}

export function LegacyPostForm({
  action,
  method = 'POST',
  csrfField = '_csrf_token',
  title,
  description,
  submitLabel,
  fields = [],
  disabled = false,
  children,
}: LegacyPostFormProps) {
  const token = csrfToken()
  return (
    <form className="iu-legacy-form" action={action} method={method.toLowerCase()}>
      {token ? <input type="hidden" name={csrfField} value={token} /> : null}
      {title || description ? (
        <header className="iu-legacy-form__header">
          {title ? <h3>{title}</h3> : null}
          {description ? <p>{description}</p> : null}
        </header>
      ) : null}
      <div className="iu-legacy-form__fields">
        {fields.map(renderField)}
      </div>
      {children}
      <div className="iu-legacy-form__actions">
        <button className="iu-legacy-form__submit" type="submit" disabled={disabled}>
          {submitLabel}
        </button>
      </div>
    </form>
  )
}
