import { useEffect, useMemo, useState } from 'react'
import { CreditCard, Eye, EyeOff, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IusStatusBadge } from '@/components/iusentra'
import type { SecretState, SettingsPayload, SettingsSection } from '../types'
import './PaymentsSettingsPanel.css'

type Values = Record<string, unknown>

function asRecord(value: unknown): Values {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Values : {}
}

function toInitial(raw: Values): Values {
  return Object.fromEntries(Object.entries(raw).map(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value) && 'present' in value) return [key, '']
    return [key, value]
  }))
}

function text(value: unknown): string {
  if (value === undefined || value === null) return ''
  return typeof value === 'boolean' ? (value ? '1' : '') : String(value)
}

function placeholder(raw: Values, name: string): string {
  const item = raw[name]
  if (item && typeof item === 'object' && !Array.isArray(item) && 'placeholder' in item) {
    return String((item as SecretState).placeholder || '')
  }
  return ''
}

function ProviderSwitch({ name, label, values, disabled, onChange }: {
  name: string
  label: string
  values: Values
  disabled: boolean
  onChange: (name: string, value: unknown) => void
}) {
  return (
    <label className="iu-pay-check">
      <input type="checkbox" checked={Boolean(values[name])} disabled={disabled} onChange={(event) => onChange(name, event.currentTarget.checked)} />
      <span>{label}</span>
    </label>
  )
}

function Field({ name, label, values, disabled, onChange, textarea = false }: {
  name: string
  label: string
  values: Values
  disabled: boolean
  textarea?: boolean
  onChange: (name: string, value: unknown) => void
}) {
  const Control = textarea ? Textarea : Input
  return (
    <label className="iu-pay-field">
      <span>{label}</span>
      <Control value={text(values[name])} disabled={disabled} onChange={(event) => onChange(name, event.currentTarget.value)} />
    </label>
  )
}

function SecretField({ name, label, values, raw, visible, disabled, onToggle, onChange }: {
  name: string
  label: string
  values: Values
  raw: Values
  visible: boolean
  disabled: boolean
  onToggle: (name: string) => void
  onChange: (name: string, value: unknown) => void
}) {
  return (
    <label className="iu-pay-field">
      <span>{label}</span>
      <span className="iu-pay-secret">
        <Input
          type={visible ? 'text' : 'password'}
          value={text(values[name])}
          disabled={disabled}
          placeholder={placeholder(raw, name)}
          autoComplete="new-password"
          onChange={(event) => onChange(name, event.currentTarget.value)}
        />
        <Button type="button" variant="ghost" size="icon" disabled={disabled} aria-label={visible ? 'Nascondi valore inserito' : 'Mostra valore inserito'} onClick={() => onToggle(name)}>
          {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
        </Button>
      </span>
    </label>
  )
}

function ModeField({ name, label, values, disabled, onChange, options }: {
  name: string
  label: string
  values: Values
  disabled: boolean
  options: Array<{ value: string; label: string }>
  onChange: (name: string, value: unknown) => void
}) {
  return (
    <label className="iu-pay-field">
      <span>{label}</span>
      <Select value={text(values[name])} disabled={disabled} onValueChange={(value) => onChange(name, value)}>
        <SelectTrigger><SelectValue placeholder="Seleziona" /></SelectTrigger>
        <SelectContent><SelectGroup>{options.map((option) => <SelectItem value={option.value} key={option.value}>{option.label}</SelectItem>)}</SelectGroup></SelectContent>
      </Select>
    </label>
  )
}

export function PaymentsSettingsPanel({
  data,
  canUpdate,
  saving,
  onSave,
}: {
  data: SettingsPayload
  canUpdate: boolean
  saving: boolean
  onSave: (section: SettingsSection, values: Values, files?: Record<string, File | null>) => Promise<boolean>
}) {
  const raw = asRecord(data.pagamenti)
  const [values, setValues] = useState<Values>(() => toInitial(raw))
  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const stats = asRecord(raw.statistiche)
  const links = Array.isArray(raw.link_recenti) ? raw.link_recenti as Values[] : []
  const active = Array.isArray(raw.provider_attivi) ? raw.provider_attivi.length : 0
  const disabled = !canUpdate

  useEffect(() => {
    setValues(toInitial(raw))
    setVisible({})
  }, [data.pagamenti])

  const dirtyValues = useMemo(() => ({ ...values }), [values])
  const update = (name: string, value: unknown) => setValues((current) => ({ ...current, [name]: value }))
  const toggle = (name: string) => setVisible((current) => ({ ...current, [name]: !current[name] }))

  return (
    <form className="iu-pay-panel" onSubmit={(event) => {
      event.preventDefault()
      void onSave('pagamenti', dirtyValues, {})
    }}>
      <div className="iu-pay-metrics">
        <span><strong>{active}</strong> canali attivi</span>
        <span><strong>{text(stats.totale_link || 0)}</strong> link creati</span>
        <span><strong>{text(stats.importo_atteso || '0,00')}</strong> euro da incassare</span>
        <span><strong>{text(stats.importo_pagato || '0,00')}</strong> euro incassati</span>
      </div>

      <section className="iu-pay-group">
        <header><CreditCard aria-hidden="true" /><strong>Carte e pagamento online</strong><IusStatusBadge tone="info">riservato</IusStatusBadge></header>
        <div className="iu-pay-grid">
          <ProviderSwitch name="stripe_abilitato" label="Carte con Stripe" values={values} disabled={disabled} onChange={update} />
          <ModeField name="stripe_modo" label="Ambiente Stripe" values={values} disabled={disabled} onChange={update} options={[{ value: 'test', label: 'Prova' }, { value: 'live', label: 'Reale' }]} />
          <Field name="stripe_pk_test" label="Chiave pubblica prova" values={values} disabled={disabled} onChange={update} />
          <SecretField name="stripe_sk_test" label="Chiave riservata prova" values={values} raw={raw} visible={Boolean(visible.stripe_sk_test)} disabled={disabled} onToggle={toggle} onChange={update} />
          <Field name="stripe_pk_live" label="Chiave pubblica reale" values={values} disabled={disabled} onChange={update} />
          <SecretField name="stripe_sk_live" label="Chiave riservata reale" values={values} raw={raw} visible={Boolean(visible.stripe_sk_live)} disabled={disabled} onToggle={toggle} onChange={update} />
          <SecretField name="stripe_webhook_secret" label="Firma conferme Stripe" values={values} raw={raw} visible={Boolean(visible.stripe_webhook_secret)} disabled={disabled} onToggle={toggle} onChange={update} />
          <ProviderSwitch name="paypal_abilitato" label="PayPal" values={values} disabled={disabled} onChange={update} />
          <ModeField name="paypal_modo" label="Ambiente PayPal" values={values} disabled={disabled} onChange={update} options={[{ value: 'sandbox', label: 'Prova' }, { value: 'live', label: 'Reale' }]} />
          <Field name="paypal_client_id" label="Identificativo PayPal" values={values} disabled={disabled} onChange={update} />
          <SecretField name="paypal_client_secret" label="Chiave riservata PayPal" values={values} raw={raw} visible={Boolean(visible.paypal_client_secret)} disabled={disabled} onToggle={toggle} onChange={update} />
        </div>
      </section>

      <section className="iu-pay-group">
        <header><CreditCard aria-hidden="true" /><strong>Italia e bonifico</strong><IusStatusBadge tone="success">operativo</IusStatusBadge></header>
        <div className="iu-pay-grid">
          <ProviderSwitch name="satispay_abilitato" label="Satispay" values={values} disabled={disabled} onChange={update} />
          <ModeField name="satispay_modo" label="Ambiente Satispay" values={values} disabled={disabled} onChange={update} options={[{ value: 'sandbox', label: 'Prova' }, { value: 'production', label: 'Reale' }]} />
          <Field name="satispay_key_id" label="Identificativo Satispay" values={values} disabled={disabled} onChange={update} />
          <SecretField name="satispay_private_key" label="Chiave privata Satispay" values={values} raw={raw} visible={Boolean(visible.satispay_private_key)} disabled={disabled} onToggle={toggle} onChange={update} />
          <ProviderSwitch name="sumup_abilitato" label="SumUp" values={values} disabled={disabled} onChange={update} />
          <SecretField name="sumup_api_key" label="Chiave riservata SumUp" values={values} raw={raw} visible={Boolean(visible.sumup_api_key)} disabled={disabled} onToggle={toggle} onChange={update} />
          <Field name="sumup_merchant_code" label="Codice esercente SumUp" values={values} disabled={disabled} onChange={update} />
          <ProviderSwitch name="bonifico_abilitato" label="Bonifico bancario" values={values} disabled={disabled} onChange={update} />
          <Field name="bonifico_iban" label="IBAN" values={values} disabled={disabled} onChange={update} />
          <Field name="bonifico_intestazione" label="Intestazione conto" values={values} disabled={disabled} onChange={update} />
          <Field name="bonifico_banca" label="Banca" values={values} disabled={disabled} onChange={update} />
          <Field name="bonifico_note" label="Note per il cliente" values={values} disabled={disabled} textarea onChange={update} />
        </div>
      </section>

      <section className="iu-pay-history">
        <header><strong>Link parcella recenti</strong><span>{links.length ? 'Ultimi link creati' : 'Nessun link creato'}</span></header>
        {links.length ? links.map((link) => <p key={text(link.id)}><b>{text(link.descrizione || link.id_parcella)}</b><span>{text(link.importo)} {text(link.valuta || 'EUR')} - {text(link.stato)}</span></p>) : <p>Nessun link di pagamento registrato.</p>}
      </section>

      <div className="iu-settings-form__actions">
        <Button type="submit" disabled={!canUpdate || saving}>
          <Save data-icon="inline-start" />
          {saving ? 'Salvataggio...' : 'Salva pagamenti'}
        </Button>
      </div>
    </form>
  )
}
