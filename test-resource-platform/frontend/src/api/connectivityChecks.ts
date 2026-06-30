import { parseResponse } from '@/api/http';

export type ConnectivityCheckStatus = 'REACHABLE' | 'UNREACHABLE';
export type ConnectivityTarget = 'SSH' | 'BMC_HTTPS';

export type ConnectivityCheckResult = {
  target: ConnectivityTarget;
  host: string;
  port: number;
  status: ConnectivityCheckStatus;
  latency_ms: number | null;
  error: string | null;
};

export type MachineConnectivityCheckResponse = {
  resource_code: string;
  checks: ConnectivityCheckResult[];
};

export async function runMachineConnectivityCheck(
  resourceCode: string
): Promise<MachineConnectivityCheckResponse> {
  const response = await fetch(`/api/v1/machines/${resourceCode}/connectivity-checks`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<MachineConnectivityCheckResponse>(response);
}
