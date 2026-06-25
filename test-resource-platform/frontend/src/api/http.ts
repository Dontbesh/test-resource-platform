export async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.detail?.message ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function ensureSuccess(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.detail?.message ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }
}
