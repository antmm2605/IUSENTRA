import type { OrganismDetail } from './types'

const MODULE_KINDS = new Set(['istanza', 'modulistica', 'adesione', 'procura', 'privacy', 'proroga', 'proposta', 'verbale', 'incarico', 'regolamento', 'tariffe'])
const publicAddress = (value: string) => {
  try {
    const url = new URL(value)
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return null
    url.hash = ''
    return url
  } catch { return null }
}

export function publicModule(target: string, resources: OrganismDetail['risorse']) {
  const address = publicAddress(target)
  if (!address || !/\.(?:pdf|docx?)(?:\?|$)/i.test(address.href)) return { file: false, resource: null }
  const resource = resources.find(item => MODULE_KINDS.has(item.kind) && publicAddress(item.url)?.href === address.href) || null
  return { file: true, resource }
}
