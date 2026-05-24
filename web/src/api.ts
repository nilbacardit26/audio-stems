import type {
  BrowseResponse,
  PresetsResponse,
  RuntimeStatus,
  SearchResult,
  SeparationForm,
  SeparationJob,
} from './types';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  });
  const data = (await response.json()) as T | { error?: string };
  if (!response.ok) {
    const errorBody = data as { error?: string };
    throw new Error(errorBody.error || response.statusText);
  }
  return data as T;
}

export function getPresets() {
  return request<PresetsResponse>('/api/presets');
}

export function getRuntime() {
  return request<RuntimeStatus>('/api/runtime');
}

export async function searchMedia(query: string) {
  const params = new URLSearchParams({ query });
  const response = await request<{ results: SearchResult[] }>(`/api/search?${params}`);
  return response.results;
}

export function browseFolder(path?: string) {
  const params = path ? `?${new URLSearchParams({ path })}` : '';
  return request<BrowseResponse>(`/api/browse${params}`);
}

export function createJob(form: SeparationForm) {
  return request<SeparationJob>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(form),
  });
}

export function getJob(id: string) {
  return request<SeparationJob>(`/api/jobs/${id}`);
}
