import type { UserPublic, UserRole } from '@/api/auth';
import { ensureSuccess, parseResponse } from '@/api/http';

export type CreateUserRequest = {
  username: string;
  password: string;
  role: UserRole;
};

export type ResetPasswordRequest = {
  password: string;
};

export async function listUsers(): Promise<UserPublic[]> {
  const response = await fetch('/api/v1/users', {
    credentials: 'include'
  });
  return parseResponse<UserPublic[]>(response);
}

export async function createUser(body: CreateUserRequest): Promise<UserPublic> {
  const response = await fetch('/api/v1/users', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<UserPublic>(response);
}

export async function disableUser(userId: number): Promise<UserPublic> {
  const response = await fetch(`/api/v1/users/${userId}/disable`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<UserPublic>(response);
}

export async function resetUserPassword(
  userId: number,
  body: ResetPasswordRequest
): Promise<void> {
  const response = await fetch(`/api/v1/users/${userId}/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  await ensureSuccess(response);
}
