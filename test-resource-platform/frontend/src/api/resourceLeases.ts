import { parseResponse } from '@/api/http';
import type { MachineResourcePublic } from '@/api/resourceInventory';
import type { UserPublic } from '@/api/auth';

export type LeaseStatus = 'ACTIVE' | 'RELEASED' | 'EXPIRED';

export type ResourceLeaseCreateRequest = {
  resource_code: string;
  duration_minutes: number;
  purpose: string;
};

export type ResourceLeaseExtendRequest = {
  duration_minutes: number;
};

export type ResourceLeasePublic = {
  id: number;
  lease_id: string;
  machine: MachineResourcePublic;
  user: UserPublic;
  purpose: string;
  status: LeaseStatus;
  started_at: string;
  expires_at: string;
  released_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LeaseEventType = 'CREATED' | 'EXTENDED' | 'RELEASED' | 'EXPIRED' | 'FORCE_RELEASED';

export type ResourceLeaseEventPublic = {
  id: number;
  lease_id: string;
  event_type: LeaseEventType;
  actor_user: UserPublic;
  target_user: UserPublic;
  occurred_at: string;
  previous_expires_at: string | null;
  new_expires_at: string | null;
};

export async function createResourceLease(
  body: ResourceLeaseCreateRequest
): Promise<ResourceLeasePublic> {
  const response = await fetch('/api/v1/leases', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<ResourceLeasePublic>(response);
}

export async function listMyLeases(): Promise<ResourceLeasePublic[]> {
  const response = await fetch('/api/v1/leases/my', {
    credentials: 'include'
  });
  return parseResponse<ResourceLeasePublic[]>(response);
}

export async function releaseResourceLease(leaseId: string): Promise<ResourceLeasePublic> {
  const response = await fetch(`/api/v1/leases/${leaseId}/release`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<ResourceLeasePublic>(response);
}

export async function extendResourceLease(
  leaseId: string,
  body: ResourceLeaseExtendRequest
): Promise<ResourceLeasePublic> {
  const response = await fetch(`/api/v1/leases/${leaseId}/extend`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<ResourceLeasePublic>(response);
}

export async function forceReleaseResourceLease(leaseId: string): Promise<ResourceLeasePublic> {
  const response = await fetch(`/api/v1/leases/${leaseId}/force-release`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<ResourceLeasePublic>(response);
}

export async function listLeaseEvents(
  afterId?: number,
  limit = 100
): Promise<ResourceLeaseEventPublic[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (afterId !== undefined) {
    params.set('after_id', String(afterId));
  }
  const response = await fetch(`/api/v1/lease-events?${params.toString()}`, {
    credentials: 'include'
  });
  return parseResponse<ResourceLeaseEventPublic[]>(response);
}
