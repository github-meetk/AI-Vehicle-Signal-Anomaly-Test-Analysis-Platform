const API = '/api';

export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export interface DashboardSummary {
  signals_analyzed: number;
  scenarios: number;
  anomalies: number;
  high_critical_anomalies: number;
  detection_precision: number | null;
  detection_recall: number | null;
  data_quality_score: number | null;
}

export interface Scenario {
  id: string;
  scenario_type: string;
  fault_type: string;
  expected_anomaly: boolean;
  quality_score: number;
  injection_time: number | null;
}

export interface Anomaly {
  id: string;
  scenario_id: string;
  signal: string;
  anomaly_type: string;
  start_time: number;
  severity: string;
  observed_value: number;
  expected_range: { min: number; max: number };
  detection_method: string;
  evidence: Record<string, unknown>;
  confidence: number;
}

export interface Investigation {
  investigation_id: string;
  result: {
    anomaly_id: string;
    summary: string;
    observations: string[];
    supporting_evidence: Array<{ signal: string; description: string; value?: number }>;
    possible_causes: string[];
    related_requirements: string[];
    recommended_followup_tests: string[];
    confidence: number;
  };
  trace: Array<{ tool: string; status: string; latency_ms: number }>;
}

export const api = {
  dashboard: () => fetchApi<DashboardSummary>('/dashboard/summary'),
  evaluation: () => fetchApi<{ detection_metrics: Array<Record<string, number | string>>; ai_evaluation: Record<string, unknown> }>('/dashboard/evaluation'),
  dataQuality: () => fetchApi<Record<string, unknown>>('/dashboard/data-quality'),
  scenarios: () => fetchApi<Scenario[]>('/scenarios'),
  generateScenario: (body: Record<string, unknown>) =>
    fetchApi<Record<string, unknown>>('/scenarios/generate', { method: 'POST', body: JSON.stringify(body) }),
  anomalies: (scenarioId?: string) =>
    fetchApi<Anomaly[]>(`/anomalies${scenarioId ? `?scenario_id=${scenarioId}` : ''}`),
  anomaly: (id: string) => fetchApi<Anomaly>(`/anomalies/${id}`),
  anomalySignals: (id: string) => fetchApi<Record<string, unknown>>(`/anomalies/${id}/signals`),
  investigate: (id: string) =>
    fetchApi<Investigation>(`/anomalies/${id}/investigate`, { method: 'POST' }),
  signalData: (scenarioId: string, signals: string) =>
    fetchApi<Array<Record<string, number>>>(`/signals/data/${scenarioId}?signals=${signals}`),
  requirements: () => fetchApi<Array<Record<string, unknown>>>('/requirements'),
  tests: () => fetchApi<Array<Record<string, unknown>>>('/tests'),
};
