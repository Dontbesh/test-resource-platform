import { parseResponse } from '@/api/http';

export type ResourceType = 'PHYSICAL' | 'VIRTUAL';
export type ResourceAdminStatus = 'ACTIVE' | 'MAINTENANCE' | 'DISABLED';
export type ConnectivityStatus = 'UNKNOWN' | 'REACHABLE' | 'UNREACHABLE';
export type MachineOccupancyStatus = 'FREE' | 'OCCUPIED';

export type ResourcePoolPublic = {
  id: number;
  name: string;
  description: string | null;
  location: string | null;
  network_zone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ResourcePoolCreateRequest = {
  name: string;
  description?: string | null;
  location?: string | null;
  network_zone?: string | null;
};

export type MachineResourcePublic = {
  id: number;
  resource_code: string;
  name: string;
  resource_type: ResourceType;
  pool_id: number;
  host_machine_id: number | null;
  admin_status: ResourceAdminStatus;
  connectivity_status: ConnectivityStatus;
  is_critical: boolean;
  owner: string | null;
  architecture: string | null;
  os_name: string | null;
  ip_address: string | null;
  mac_address: string | null;
  bmc_address: string | null;
  tags: string[];
  occupancy_status: MachineOccupancyStatus;
  leased_by_username: string | null;
  active_lease_id: string | null;
  created_at: string;
  updated_at: string;
};

export type MachineResourceCreateRequest = {
  resource_code: string;
  name: string;
  resource_type: ResourceType;
  pool_id: number;
  host_machine_id?: number | null;
  is_critical?: boolean;
  owner?: string | null;
  architecture?: string | null;
  os_name?: string | null;
  ip_address?: string | null;
  mac_address?: string | null;
  bmc_address?: string | null;
  tags?: string[];
};

export async function listResourcePools(): Promise<ResourcePoolPublic[]> {
  const response = await fetch('/api/v1/resource-pools', {
    credentials: 'include'
  });
  return parseResponse<ResourcePoolPublic[]>(response);
}

export async function createResourcePool(
  body: ResourcePoolCreateRequest
): Promise<ResourcePoolPublic> {
  const response = await fetch('/api/v1/resource-pools', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<ResourcePoolPublic>(response);
}

export async function disableResourcePool(poolId: number): Promise<ResourcePoolPublic> {
  const response = await fetch(`/api/v1/resource-pools/${poolId}/disable`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<ResourcePoolPublic>(response);
}

export async function enableResourcePool(poolId: number): Promise<ResourcePoolPublic> {
  const response = await fetch(`/api/v1/resource-pools/${poolId}/enable`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<ResourcePoolPublic>(response);
}

export async function listMachines(): Promise<MachineResourcePublic[]> {
  const response = await fetch('/api/v1/machines', {
    credentials: 'include'
  });
  return parseResponse<MachineResourcePublic[]>(response);
}

export async function createMachine(
  body: MachineResourceCreateRequest
): Promise<MachineResourcePublic> {
  const response = await fetch('/api/v1/machines', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<MachineResourcePublic>(response);
}

export async function disableMachine(resourceCode: string): Promise<MachineResourcePublic> {
  const response = await fetch(`/api/v1/machines/${resourceCode}/disable`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<MachineResourcePublic>(response);
}

export async function enableMachine(resourceCode: string): Promise<MachineResourcePublic> {
  const response = await fetch(`/api/v1/machines/${resourceCode}/enable`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<MachineResourcePublic>(response);
}
