import { ensureSuccess, parseResponse } from '@/api/http';

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
  await ensureSuccess(response);
}
