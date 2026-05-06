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

export async function apiPostJson<T>(url: string, body: unknown, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    if (!response.ok) return fallback
    return (await response.json()) as T
  } catch {
    return fallback
  }
}
