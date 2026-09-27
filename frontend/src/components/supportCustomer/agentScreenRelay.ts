import type { LocalSupportAgent } from './localAgent'
import { errorMessage, errorName } from './mediaCapture'
import type { SupportRealtimeMessage } from './types'

/**
 * Schermo e controllo PC tramite agente locale (Local Signer o agente
 * IUSENTRA Assistenza): armo/disarmo, cattura periodica dei fotogrammi inoltrati
 * all'operatore come `screen_frame`, esecuzione dei comandi `remote_control`.
 *
 * Porta startAgentScreenShare, captureAndRelayAgentScreen, _restartAgentScreenTimer,
 * _agentScreenQuality, _agentScreenIntervalMs, ensureLocalControlAgent,
 * ensureLocalScreenShareAgent, disarmLocalControlAgent ed executeRemoteCommand.
 */

const AGENT_ARM_TTL_SECONDS = 3600

type AgentScreenRelayOptions = {
  agent: LocalSupportAgent
  publicId: string
  token: string
  send: (message: SupportRealtimeMessage) => boolean
  onStatus: (text: string) => void
  onNotice: (text: string) => void
  isClosed: () => boolean
}

/** Qualità adattiva: alta durante il controllo PC (fluidità prioritaria), normale altrimenti. */
export function agentScreenQuality(controlArmed: boolean): { max_width: number; quality: number } {
  return controlArmed ? { max_width: 2400, quality: 80 } : { max_width: 1920, quality: 72 }
}

/** Intervallo di cattura adattivo: più veloce durante il controllo remoto. */
export function agentScreenIntervalMs(controlArmed: boolean): number {
  return controlArmed ? 350 : 600
}

export class AgentScreenRelay {
  private screenArmed = false
  private controlArmed = false
  private timer: number | null = null
  private readonly options: AgentScreenRelayOptions

  constructor(options: AgentScreenRelayOptions) {
    this.options = options
  }

  get isScreenArmed(): boolean {
    return this.screenArmed
  }

  get isControlArmed(): boolean {
    return this.controlArmed
  }

  private credentials() {
    return { session_id: this.options.publicId, token: this.options.token }
  }

  async captureAndRelay(): Promise<void> {
    if (this.options.isClosed() || !this.screenArmed) return
    try {
      const frame = await this.options.agent.fetchAgent('/screenshot', {
        ...this.credentials(),
        ...agentScreenQuality(this.controlArmed),
      })
      this.options.onStatus('Schermo condiviso tramite agente locale')
      this.options.send({
        type: 'screen_frame',
        image: frame.image,
        width: frame.width,
        height: frame.height,
        preview_width: frame.preview_width,
        preview_height: frame.preview_height,
        captured_at: frame.captured_at,
      })
    } catch (error) {
      console.error(error)
      this.options.onStatus(`Errore condivisione schermo: ${errorMessage(error)}`)
    }
  }

  stopTimer(): void {
    if (this.timer !== null) window.clearInterval(this.timer)
    this.timer = null
  }

  /** Riavvia la cattura con l'intervallo corrente (cambia quando si arma il controllo). */
  restartTimer(): void {
    this.stopTimer()
    if (!this.options.isClosed() && this.screenArmed) {
      this.timer = window.setInterval(() => {
        void this.captureAndRelay()
      }, agentScreenIntervalMs(this.controlArmed))
    }
  }

  async ensureScreenShare(): Promise<void> {
    this.options.onStatus('Verifico agente IUSENTRA Assistenza sul PC')
    const status = await this.options.agent.fetchAgent('/status')
    if (!status.ok) throw new Error('Agente IUSENTRA Assistenza non disponibile sul PC.')
    await this.options.agent.fetchAgent('/arm', {
      ...this.credentials(),
      ttl_seconds: AGENT_ARM_TTL_SECONDS,
      control: false,
    })
    this.screenArmed = true
  }

  async ensureControl(): Promise<void> {
    this.options.onStatus('Verifico Local Signer o agente IUSENTRA Assistenza sul PC')
    const status = await this.options.agent.fetchAgent('/status')
    if (!status.ok) throw new Error('Local Signer o agente IUSENTRA Assistenza non disponibile sul PC.')
    await this.options.agent.fetchAgent('/arm', {
      ...this.credentials(),
      ttl_seconds: AGENT_ARM_TTL_SECONDS,
      control: true,
    })
    this.controlArmed = true
    this.options.onStatus('Controllo PC autorizzato su questo dispositivo')
    // Qualità e frequenza di cattura aumentano durante il controllo remoto.
    this.restartTimer()
  }

  /** Fallback della condivisione: schermo inviato dall'agente locale a fotogrammi. */
  async start(originalError?: unknown): Promise<void> {
    await this.ensureScreenShare()
    await this.captureAndRelay()
    this.restartTimer()
    this.options.onStatus('Schermo condiviso tramite agente locale')
    if (errorName(originalError) === 'NotAllowedError') {
      this.options.onNotice("Il browser ha bloccato la condivisione schermo: sto usando l'agente locale autorizzato.")
    }
  }

  async disarm(): Promise<void> {
    this.stopTimer()
    if (!this.screenArmed && !this.controlArmed) return
    this.screenArmed = false
    this.controlArmed = false
    try {
      await this.options.agent.fetchAgent('/disarm', this.credentials())
    } catch (error) {
      console.error(error)
    }
  }

  /** Comando `remote_control` dell'operatore: eseguito sull'agente, con conferma `remote_control_ack`. */
  async executeRemoteCommand(message: SupportRealtimeMessage): Promise<void> {
    const commandId = typeof message.id === 'string' || typeof message.id === 'number' ? message.id : `${Date.now()}`
    try {
      if (!this.controlArmed) await this.ensureControl()
      const result = await this.options.agent.fetchAgent('/execute', {
        ...this.credentials(),
        command: message.command && typeof message.command === 'object' ? message.command : {},
      })
      this.options.send({ type: 'remote_control_ack', id: commandId, ok: true, result })
      this.options.onStatus('Comando PC eseguito')
    } catch (error) {
      const text = errorMessage(error)
      this.options.send({ type: 'remote_control_ack', id: commandId, ok: false, error: text })
      this.options.onStatus(`Errore controllo PC: ${text}`)
    }
  }
}
