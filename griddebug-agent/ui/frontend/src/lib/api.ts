import { Network, Scenario, DiagnoseResponse, DiagnoseNLResponse, OverrideState, ReDiagnoseResponse } from '@/types/diagnostic';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchNetworks(): Promise<Network[]> {
  const res = await fetch(`${API_BASE}/networks`);
  if (!res.ok) throw new Error('Failed to fetch networks');
  const data = await res.json();
  return data.networks;
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) throw new Error('Failed to fetch scenarios');
  const data = await res.json();
  return data.scenarios;
}

/**
 * Stream diagnosis results via SSE — each pipeline arrives as a separate event.
 * Events: 'baseline', 'agentic', 'done'.
 */
export async function runDiagnosisStream(
  network: string,
  scenario: string,
  query: string | undefined,
  onEvent: (event: string, data: unknown) => void,
): Promise<void> {
  const body: { network: string; scenario: string; query?: string } = { network, scenario };
  if (query?.trim()) body.query = query.trim();

  const res = await fetch(`${API_BASE}/diagnose_stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error('Streaming diagnosis request failed');
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || ''; // keep incomplete chunk

    for (const part of parts) {
      if (!part.trim()) continue;
      let eventName = 'message';
      let dataStr = '';
      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) eventName = line.slice(7).trim();
        else if (line.startsWith('data: ')) dataStr = line.slice(6);
      }
      if (dataStr) {
        try {
          const data = JSON.parse(dataStr);
          onEvent(eventName, data);
        } catch { /* skip malformed */ }
      }
    }
  }
}

export async function runNLDiagnosis(network: string, description: string): Promise<DiagnoseNLResponse> {
  const res = await fetch(`${API_BASE}/diagnose_nl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ network, description }),
  });
  if (!res.ok) throw new Error('NL Diagnosis request failed');
  return res.json();
}

export async function runReDiagnosis(
  network: string,
  scenario: string,
  overrides: OverrideState,
  generatedCode?: string | null
): Promise<ReDiagnoseResponse> {
  const res = await fetch(`${API_BASE}/api/rediagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ network, scenario, overrides, generatedCode }),
  });
  if (!res.ok) throw new Error('Re-diagnosis request failed');
  return res.json();
}
