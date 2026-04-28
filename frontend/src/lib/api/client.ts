type JsonRecord = Record<string, unknown>;

function csrfToken(): string {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
  return meta?.content || "";
}

export async function apiGet<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function apiPost<T>(url: string, body: JsonRecord, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}
