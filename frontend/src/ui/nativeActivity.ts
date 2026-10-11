import { getActivities, subscribeActivities } from './activity'
import './activity.css'

/** The HTML reader uses the same owners and presentation as React, without React. */
export function installNativeActivityStatus(): () => void {
  const status = document.createElement('div')
  status.className = 'iu-activity-status'
  status.setAttribute('role', 'status')
  status.setAttribute('aria-live', 'polite')
  status.setAttribute('aria-atomic', 'true')
  const spinner = document.createElement('span')
  spinner.className = 'iu-activity-spinner'
  spinner.setAttribute('aria-hidden', 'true')
  const label = document.createElement('span')
  status.append(spinner, label)
  let showTimer: number | undefined
  let slowTimer: number | undefined
  const render = () => {
    window.clearTimeout(showTimer)
    window.clearTimeout(slowTimer)
    const first = getActivities()[0]
    if (!first) { status.remove(); return }
    const paint = () => {
      label.textContent = first.label
      if (Date.now() - first.startedAt >= 15000) {
        const slow = document.createElement('small')
        slow.textContent = 'L’operazione sta richiedendo più tempo. Attendo la risposta.'
        label.appendChild(slow)
      }
      ;(document.fullscreenElement || document.body).appendChild(status)
    }
    if (Date.now() - first.startedAt >= 180) paint()
    else { status.remove(); showTimer = window.setTimeout(paint, 180 - (Date.now() - first.startedAt)) }
    slowTimer = window.setTimeout(paint, Math.max(0, 15000 - (Date.now() - first.startedAt)))
  }
  const unsubscribe = subscribeActivities(render)
  document.addEventListener('fullscreenchange', render)
  render()
  const dispose = (event?: PageTransitionEvent) => {
    if (event?.persisted) return
    unsubscribe()
    window.clearTimeout(showTimer)
    window.clearTimeout(slowTimer)
    document.removeEventListener('fullscreenchange', render)
    window.removeEventListener('pagehide', dispose)
    status.remove()
  }
  window.addEventListener('pagehide', dispose)
  return () => dispose()
}
