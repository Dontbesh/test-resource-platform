import { parseResponse } from '@/api/http';
import type { MachineResourcePublic } from '@/api/resourceInventory';
import type { UserPublic } from '@/api/auth';

export type LeaseStatus = 'ACTIVE' | 'RELEASED' | 'EXPIRED';

export type ResourceLeaseCreateRequest = {
  resource_code: string;
  duration_minutes: number;
  purpose: string;
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
