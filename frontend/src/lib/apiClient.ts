export async function apiJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return fallback
    return (await response.json()) as T
  } catch {
    return fallback
  }
}
