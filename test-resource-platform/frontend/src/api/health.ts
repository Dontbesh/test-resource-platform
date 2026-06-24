export type DatabaseHealth = {
  status: 'ok' | 'unavailable';
  error: string | null;
};

export type HealthResponse = {
  status: 'ok';
  app: string;
  version: string;
  request_id: string;
  database: DatabaseHealth;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/v1/health');
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json() as Promise<HealthResponse>;
}
