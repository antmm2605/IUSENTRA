import { apiJson } from '@/lib/apiClient'

export type FeatureFlagKey =
  | 'routes.appV2.docsPanel'
  | 'routes.appV2.commsDeposits'
  | 'routes.appV2.uploadClassification'
  | 'routes.appV2.deadlines'
  | 'routes.appV2.agenda'
  | 'routes.appV2.caseFiles'
  | 'notifications.mobilePush'

type FeatureFlagsPayload = {
  ok: boolean
  flags: Partial<Record<FeatureFlagKey, boolean>>
}

const emptyFeatureFlags: FeatureFlagsPayload = { ok: false, flags: {} }
let featureFlagsCache: Partial<Record<FeatureFlagKey, boolean>> | null = null

function bootstrapFlags(): Partial<Record<FeatureFlagKey, boolean>> {
  if (typeof document === 'undefined') return {}
  const element = document.getElementById('iusentra-react-bootstrap')
  if (!element?.textContent) return {}
  try {
    const parsed = JSON.parse(element.textContent) as { featureFlags?: Partial<Record<FeatureFlagKey, boolean>> }
    return parsed.featureFlags && typeof parsed.featureFlags === 'object' ? parsed.featureFlags : {}
  } catch {
    return {}
  }
}

export async function loadFeatureFlags(): Promise<Partial<Record<FeatureFlagKey, boolean>>> {
  if (featureFlagsCache) return featureFlagsCache
  const initial = bootstrapFlags()
  if (Object.keys(initial).length > 0) {
    featureFlagsCache = initial
    return featureFlagsCache
  }
  const payload = await apiJson<FeatureFlagsPayload>('/api/v1/ui/feature-flags', emptyFeatureFlags)
  featureFlagsCache = payload.flags || {}
  return featureFlagsCache
}

export async function isFeatureFlagEnabled(flag: FeatureFlagKey): Promise<boolean> {
  const flags = await loadFeatureFlags()
  return flags[flag] === true
}

export function isFeatureFlagEnabledSync(flag: FeatureFlagKey): boolean {
  const flags = featureFlagsCache || bootstrapFlags()
  return flags[flag] === true
}
