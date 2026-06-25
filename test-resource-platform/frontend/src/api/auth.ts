export type UserRole = 'ADMIN' | 'TSE' | 'TE';

export type UserPublic = {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
};

export type LoginRequest = {
  username: string;
  password: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.detail?.message ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function login(body: LoginRequest): Promise<UserPublic> {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<UserPublic>(response);
}

export async function fetchCurrentUser(): Promise<UserPublic> {
  const response = await fetch('/api/v1/auth/me', {
    credentials: 'include'
  });
  return parseResponse<UserPublic>(response);
}

export async function logout(): Promise<void> {
  const response = await fetch('/api/v1/auth/logout', {
    method: 'POST',
    credentials: 'include'
  });
  if (!response.ok) {
    throw new Error(`Logout failed: ${response.status}`);
  }
}
