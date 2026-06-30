import { parseResponse } from '@/api/http';

export type MachineCredentialUpsertRequest = {
  ssh_username?: string | null;
  ssh_password?: string | null;
  bmc_username?: string | null;
  bmc_password?: string | null;
};

export type MachineCredentialSummary = {
  resource_code: string;
  ssh_username: string | null;
  has_ssh_password: boolean;
  bmc_username: string | null;
  has_bmc_password: boolean;
};

export type MachineCredentialSecret = {
  resource_code: string;
  ssh_username: string | null;
  ssh_password: string | null;
  bmc_username: string | null;
  bmc_password: string | null;
};

export async function configureMachineCredentials(
  resourceCode: string,
  body: MachineCredentialUpsertRequest
): Promise<MachineCredentialSummary> {
  const response = await fetch(`/api/v1/machines/${resourceCode}/credentials`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<MachineCredentialSummary>(response);
}

export async function getMachineCredentials(resourceCode: string): Promise<MachineCredentialSecret> {
  const response = await fetch(`/api/v1/machines/${resourceCode}/credentials`, {
    credentials: 'include'
  });
  return parseResponse<MachineCredentialSecret>(response);
}
