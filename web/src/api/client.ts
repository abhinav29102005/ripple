import * as schemas from './schemas';

const rawBase = (import.meta.env.VITE_API_BASE ?? '').trim();
export const API_BASE = rawBase.replace(/\/+$/, '');

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
}



export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  path: string,
  schema: { safeParse: (val: unknown) => { success: true; data: T } | { success: false; error: any } },
  options?: RequestInit
): Promise<T> {
  const url = getApiUrl(path);
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errBody: unknown;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text();
    }
    throw new ApiError(`Request to ${url} failed with status ${res.status}`, res.status, errBody);
  }

  const json = await res.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    console.error(`Validation error on ${url}:`, parsed.error);
    throw new ApiError(`Response validation error for ${url}: ${parsed.error.message}`, 500, parsed.error);
  }

  return parsed.data;
}

export const api = {
  getHealth: () => request('/api/health', schemas.HealthResponseSchema),

  getTasks: () => request('/api/tasks', schemas.TasksResponseSchema),

  getAgents: () => request('/api/agents', schemas.AgentsResponseSchema),

  getBlastRadius: (retractionId: string) =>
    request(`/api/graph/blast/${retractionId}`, schemas.BlastResponseSchema),

  getRankings: (tenant: string, retractionId: string) =>
    request(`/api/tenants/${tenant}/rankings?retraction_id=${retractionId}`, schemas.RankingsResponseSchema),

  getExplain: (tenant: string, rankingId: string, reviewId: string) =>
    request(`/api/tenants/${tenant}/explain/${rankingId}/${reviewId}`, schemas.ExplainResponseSchema),

  getMemory: (tenant: string) =>
    request(`/api/tenants/${tenant}/memory`, schemas.MemoryResponseSchema),

  loadDemoScenario: (tenant: string, retractionId: string) =>
    fetch(getApiUrl(`/api/tenants/${tenant}/load-demo?retraction_id=${retractionId}`), { method: 'POST' }).then(r => r.json()),

  recordEpisode: (tenant: string, payload: {
    session_id?: string | null;
    kind: 'dismiss' | 'escalate';
    reason: string;
    weight_bucket: string;
    flips: boolean;
    ext_review: string;
    ext_retraction: string;
    notes?: string;
  }) =>
    fetch(getApiUrl(`/api/tenants/${tenant}/episodes`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => r.json()),

  submitRetraction: (payload: {
    retraction_id: string;
    trial_id: string;
    reason: string;
    reason_category?: string;
    notice_url?: string;
  }) =>
    fetch(getApiUrl('/api/retractions'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => r.json()),

  sendChat: (payload: { tenant: string; message: string; session_id?: string | null }) =>
    request('/api/chat', schemas.ChatResponseSchema, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  runAnalyst: (payload: { tenant: string; retraction_id: string; prompt?: string }) =>
    request('/api/analyst', schemas.AnalystResponseSchema, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getBenchLatest: () => request('/api/bench/latest', schemas.BenchResponseSchema),
  getChaosLatest: () => request('/api/bench/chaos', schemas.ChaosResponseSchema),
};
