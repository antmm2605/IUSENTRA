import type { SupportCustomerViewState } from './types'

/**
 * Etichette e disponibilità dei comandi derivate dallo stato
 * (syncStartButtonUi / syncCustomerMicUi / syncCustomerLayout dello script legacy).
 */

export type StartButtonView = {
  kind: 'active' | 'ready' | 'starting' | 'waiting' | 'closed'
  label: string
  title: string
  disabled: boolean
}

export function startButtonView(state: SupportCustomerViewState): StartButtonView {
  if (state.supportStarted) {
    return {
      kind: 'active',
      label: 'Assistenza attiva',
      title: 'Assistenza avviata: puoi chiuderla con Termina sessione.',
      disabled: true,
    }
  }
  if (state.sessionClosed) {
    return {
      kind: 'closed',
      label: 'Sessione chiusa',
      title: "La sessione è conclusa: chiedi all'operatore un nuovo link di assistenza.",
      disabled: true,
    }
  }
  if (state.starting) {
    return { kind: 'starting', label: 'Avvio assistenza...', title: 'Avvio della condivisione in corso.', disabled: true }
  }
  if (state.operatorReadyForStart) {
    return {
      kind: 'ready',
      label: 'Avvia assistenza',
      title: 'Avvia la condivisione solo dopo la presa in carico del SUPERADMIN.',
      disabled: false,
    }
  }
  return {
    kind: 'waiting',
    label: 'Attendi operatore',
    title: 'Il SUPERADMIN deve prima prendere in carico la richiesta dalla console.',
    disabled: true,
  }
}

export function canToggleMicrophone(state: SupportCustomerViewState): boolean {
  return !state.sessionClosed && (state.micTrackCount > 0 || state.consent.audio)
}

export function micButtonLabel(state: SupportCustomerViewState): string {
  return state.micMuted ? 'Riattiva microfono' : 'Muta microfono'
}

export function fullscreenButtonLabel(state: SupportCustomerViewState): string {
  return state.fullscreen ? 'Esci schermo intero' : 'Schermo intero'
}

export function compactChatButtonLabel(state: SupportCustomerViewState): string {
  return state.chatCompact ? 'Chat estesa' : 'Chat compatta'
}

/** Invito ad avviare: serve finché l'assistenza non è partita (lo script legacy lo lasciava visibile). */
export function takeChargeVisible(state: SupportCustomerViewState): boolean {
  return !state.sessionClosed && state.operatorReadyForStart && !state.supportStarted
}

export function advancedBannerVisible(state: SupportCustomerViewState): boolean {
  return !state.sessionClosed && state.advancedRequested
}
