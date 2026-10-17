export const STUDIO_NAV_GROUPS = [
  { key: 'gestione', label: 'Gestione e contabilità' },
  { key: 'documenti', label: 'Documenti e atti' },
  { key: 'ricerca', label: 'Ricerca giuridica' },
  { key: 'lex', label: 'Strumenti Lex' },
] as const

export type StudioNavGroup = typeof STUDIO_NAV_GROUPS[number]['key']

export type StudioNavEntry = { label: string; href: string; group?: string; keywords?: string }

function normalized(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it').replace(/[^a-z0-9]+/g, ' ').trim()
}

export function filterStudioNavigation<T extends StudioNavEntry>(items: readonly T[], query: string): T[] {
  const tokens = normalized(query).split(/\s+/).filter(Boolean)
  return items.filter(item => {
    const group = STUDIO_NAV_GROUPS.find(group => group.key === item.group)?.label || ''
    const text = normalized(`${item.label} ${item.href} ${item.keywords || ''} ${group}`)
    return tokens.every(token => text.includes(token))
  })
}
