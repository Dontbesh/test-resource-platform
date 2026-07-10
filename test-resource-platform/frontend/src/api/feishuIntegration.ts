import { parseResponse } from '@/api/http';

export type FeishuPlatformType = 'FEISHU' | 'LARK';
export type FeishuSetupStatus = 'PENDING' | 'COMPLETED' | 'DENIED' | 'EXPIRED' | 'ERROR';
export type FeishuAppStatus = 'CONFIGURED' | 'CONNECTED' | 'DISCONNECTED' | 'ERROR';

export type FeishuSetupBeginResponse = {
  id: number;
  device_code: string;
  qr_url: string;
  interval: number;
  expires_in: number;
  expires_at: string;
};

export type FeishuSetupPollResponse = {
  status: FeishuSetupStatus;
  base_url: string;
  app_id: string | null;
  app_secret: string | null;
  platform: FeishuPlatformType | null;
  owner_open_id: string | null;
  slow_down: boolean;
  error: string | null;
};

export type FeishuSetupSaveRequest = {
  name: string | null;
  platform_type: FeishuPlatformType;
  app_id: string;
  app_secret: string;
  owner_open_id: string | null;
  tenant_brand: string | null;
};

export type FeishuAppPublic = {
  id: number;
  name: string;
  platform_type: FeishuPlatformType;
  app_id: string;
  owner_open_id: string | null;
  tenant_brand: string | null;
  bot_open_id: string | null;
  status: FeishuAppStatus;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type FeishuUserBindingPublic = {
  id: number;
  feishu_app_id: number;
  open_id: string;
  display_name: string | null;
  platform_user: {
    id: number;
    username: string;
    role: string;
    is_active: boolean;
  };
  created_at: string;
};

export type FeishuUserBindingCreateRequest = {
  open_id: string;
  platform_username: string;
  display_name: string | null;
};

export async function beginFeishuSetup(): Promise<FeishuSetupBeginResponse> {
  const response = await fetch('/api/v1/integrations/feishu/setup/begin', {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<FeishuSetupBeginResponse>(response);
}

export async function pollFeishuSetup(
  deviceCode: string,
  baseUrl?: string
): Promise<FeishuSetupPollResponse> {
  const response = await fetch('/api/v1/integrations/feishu/setup/poll', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify({ device_code: deviceCode, base_url: baseUrl ?? null })
  });
  return parseResponse<FeishuSetupPollResponse>(response);
}

export async function saveFeishuSetup(body: FeishuSetupSaveRequest): Promise<FeishuAppPublic> {
  const response = await fetch('/api/v1/integrations/feishu/setup/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<FeishuAppPublic>(response);
}

export async function listFeishuApps(): Promise<FeishuAppPublic[]> {
  const response = await fetch('/api/v1/integrations/feishu/apps', {
    credentials: 'include'
  });
  return parseResponse<FeishuAppPublic[]>(response);
}

export async function checkFeishuAppConnection(appId: number): Promise<FeishuAppPublic> {
  const response = await fetch(`/api/v1/integrations/feishu/apps/${appId}/check-connection`, {
    method: 'POST',
    credentials: 'include'
  });
  return parseResponse<FeishuAppPublic>(response);
}

export async function listFeishuUserBindings(appId: number): Promise<FeishuUserBindingPublic[]> {
  const response = await fetch(`/api/v1/integrations/feishu/apps/${appId}/bindings`, {
    credentials: 'include'
  });
  return parseResponse<FeishuUserBindingPublic[]>(response);
}

export async function createFeishuUserBinding(
  appId: number,
  body: FeishuUserBindingCreateRequest
): Promise<FeishuUserBindingPublic> {
  const response = await fetch(`/api/v1/integrations/feishu/apps/${appId}/bindings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return parseResponse<FeishuUserBindingPublic>(response);
}

export async function deleteFeishuUserBinding(bindingId: number): Promise<void> {
  const response = await fetch(`/api/v1/integrations/feishu/bindings/${bindingId}`, {
    method: 'DELETE',
    credentials: 'include'
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const errorMessage = body?.detail?.message ?? `Request failed: ${response.status}`;
    throw new Error(errorMessage);
  }
}
