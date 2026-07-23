import { parseResponse } from '@/api/http';

export interface AssistantMessageResponse {
  text: string;
}

export async function sendAssistantMessage(text: string): Promise<AssistantMessageResponse> {
  const response = await fetch('/api/v1/assistant/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text })
  });
  return parseResponse<AssistantMessageResponse>(response);
}
