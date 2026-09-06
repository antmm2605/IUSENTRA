import { Button } from '../../ui/Button'
import type { ComponentProps } from 'react'

// I comandi nei sotto-pannelli non devono inviare il form del procedimento.
export function ActionButton(props: ComponentProps<typeof Button>) {
  return <Button type="button" tone="neutral" {...props} />
}
