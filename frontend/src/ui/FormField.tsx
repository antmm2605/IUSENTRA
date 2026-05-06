import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import './ui.css'

type BaseProps = {
  label: string
  htmlFor: string
  help?: string
  error?: string
  children: ReactNode
}

export function FormField({ label, htmlFor, help, error, children }: BaseProps) {
  return (
    <div className="iu-form-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {help ? <span className="iu-form-field__help">{help}</span> : null}
      {error ? <span className="iu-form-field__error">{error}</span> : null}
    </div>
  )
}

export function TextInput({
  label,
  help,
  error,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; help?: string; error?: string; id: string }) {
  return (
    <FormField label={label} htmlFor={id} help={help} error={error}>
      <input id={id} {...props} />
    </FormField>
  )
}

export function SelectField({
  label,
  help,
  error,
  id,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; help?: string; error?: string; id: string }) {
  return (
    <FormField label={label} htmlFor={id} help={help} error={error}>
      <select id={id} {...props}>{children}</select>
    </FormField>
  )
}

export function TextareaField({
  label,
  help,
  error,
  id,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; help?: string; error?: string; id: string }) {
  return (
    <FormField label={label} htmlFor={id} help={help} error={error}>
      <textarea id={id} {...props} />
    </FormField>
  )
}
