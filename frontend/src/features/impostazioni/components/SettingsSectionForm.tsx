import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Eye, EyeOff, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { SettingsField, SettingsSection, SecretState } from '../types'

type SettingsSectionChildren = ReactNode | ((values: Record<string, unknown>) => ReactNode)

function textValue(value: unknown): string {
  if (value === undefined || value === null) return ''
  return typeof value === 'boolean' ? (value ? '1' : '') : String(value)
}

function secretPlaceholder(raw: Record<string, unknown>, name: string): string {
  const item = raw[name]
  if (item && typeof item === 'object' && !Array.isArray(item) && 'placeholder' in item) {
    return String((item as SecretState).placeholder || '')
  }
  return ''
}

function renderFieldHelp(field: SettingsField) {
  if (!field.help && !field.helpLink) return null
  return (
    <small className="iu-settings-field__help">
      {field.help}
      {field.help && field.helpLink ? ' ' : null}
      {field.helpLink ? (
        <a href={field.helpLink.href} target="_blank" rel="noreferrer">
          {field.helpLink.label}
        </a>
      ) : null}
    </small>
  )
}

export function SettingsSectionForm({
  section,
  fields,
  initialValues,
  rawValues,
  canUpdate,
  saving,
  onSave,
  children,
}: {
  section: SettingsSection
  fields: SettingsField[]
  initialValues: Record<string, unknown>
  rawValues: Record<string, unknown>
  canUpdate: boolean
  saving: boolean
  onSave: (section: SettingsSection, values: Record<string, unknown>, files: Record<string, File | null>) => Promise<boolean>
  children?: SettingsSectionChildren
}) {
  const [values, setValues] = useState<Record<string, unknown>>(initialValues)
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setValues(initialValues)
    setFiles({})
    setVisibleSecrets({})
  }, [initialValues, section])

  const visibleValues = useMemo(() => values, [values])

  function updateValue(name: string, value: unknown) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  function renderPasswordField(field: SettingsField, id: string, label: ReactNode) {
    const isVisible = Boolean(visibleSecrets[field.name])
    return (
      <label className={cn('iu-settings-field', `is-${field.width || 'half'}`)} key={field.name}>
        {label}
        <span className="iu-settings-secret-field">
          <Input
            id={id}
            type={isVisible ? 'text' : 'password'}
            required={field.required}
            placeholder={secretPlaceholder(rawValues, field.name)}
            value={textValue(visibleValues[field.name])}
            disabled={!canUpdate}
            autoComplete="new-password"
            onChange={(event) => updateValue(field.name, event.currentTarget.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="iu-settings-secret-field__toggle"
            disabled={!canUpdate}
            aria-label={isVisible ? 'Nascondi valore inserito' : 'Mostra valore inserito'}
            title={isVisible ? 'Nascondi valore inserito' : 'Mostra valore inserito'}
            onClick={() => setVisibleSecrets((current) => ({ ...current, [field.name]: !isVisible }))}
          >
            {isVisible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
          </Button>
        </span>
        {renderFieldHelp(field)}
      </label>
    )
  }

  function renderField(field: SettingsField) {
    const id = `settings-${section}-${field.name}`
    const commonLabel = (
      <span>
        {field.label}
        {field.required ? <b aria-hidden="true"> *</b> : null}
      </span>
    )
    if (field.type === 'checkbox') {
      return (
        <label className={cn('iu-settings-field iu-settings-field--check', `is-${field.width || 'half'}`)} key={field.name}>
          <input
            id={id}
            type="checkbox"
            checked={Boolean(visibleValues[field.name])}
            disabled={!canUpdate}
            onChange={(event) => updateValue(field.name, event.currentTarget.checked)}
          />
          {commonLabel}
          {renderFieldHelp(field)}
        </label>
      )
    }
    if (field.type === 'select') {
      return (
        <label className={cn('iu-settings-field', `is-${field.width || 'half'}`)} key={field.name}>
          {commonLabel}
          <Select value={textValue(visibleValues[field.name])} onValueChange={(value) => updateValue(field.name, value)} disabled={!canUpdate}>
            <SelectTrigger className="iu-settings-select">
              <SelectValue placeholder="Seleziona" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {(field.options || []).map((option) => (
                  <SelectItem value={option.value} key={`${field.name}-${option.value}`}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          {renderFieldHelp(field)}
        </label>
      )
    }
    if (field.type === 'file') {
      return (
        <label className={cn('iu-settings-field', `is-${field.width || 'half'}`)} key={field.name}>
          {commonLabel}
          <Input
            id={id}
            type="file"
            accept={field.accept}
            disabled={!canUpdate}
            onChange={(event) => setFiles((current) => ({ ...current, [field.name]: event.currentTarget.files?.[0] || null }))}
          />
          {renderFieldHelp(field)}
        </label>
      )
    }
    if (field.type === 'password') {
      return renderPasswordField(field, id, commonLabel)
    }
    return (
      <label className={cn('iu-settings-field', `is-${field.width || 'half'}`)} key={field.name}>
        {commonLabel}
        <Input
          id={id}
          type={field.type || 'text'}
          required={field.required}
          min={field.min}
          max={field.max}
          placeholder={field.placeholder}
          value={textValue(visibleValues[field.name])}
          disabled={!canUpdate}
          onChange={(event) => updateValue(field.name, event.currentTarget.value)}
        />
        {renderFieldHelp(field)}
      </label>
    )
  }

  return (
    <form className="iu-settings-form" onSubmit={(event) => {
      event.preventDefault()
      void onSave(section, values, files)
    }}>
      <div className="iu-settings-form__grid">{fields.map(renderField)}</div>
      {typeof children === 'function' ? children(values) : children}
      <div className="iu-settings-form__actions">
        <Button type="submit" disabled={!canUpdate || saving}>
          <Save data-icon="inline-start" />
          {saving ? 'Salvataggio...' : 'Salva sezione'}
        </Button>
      </div>
    </form>
  )
}
