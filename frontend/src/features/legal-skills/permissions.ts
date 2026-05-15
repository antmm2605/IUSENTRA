export function readLegalSkillsPermissions(): Set<string> {
  const element = document.getElementById('iusentra-react-bootstrap')
  if (!element?.textContent) return new Set()
  try {
    const parsed = JSON.parse(element.textContent) as { permissions?: string[] }
    return new Set(Array.isArray(parsed.permissions) ? parsed.permissions : [])
  } catch {
    return new Set()
  }
}

export function can(permission: string): boolean {
  return readLegalSkillsPermissions().has(permission)
}
