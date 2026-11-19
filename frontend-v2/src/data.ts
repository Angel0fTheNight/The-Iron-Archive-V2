export type Agent = {
  id: string;
  name: string;
  role: string;
  status: "Ativo" | "Em revisão" | "Em espera" | "Não disponível";
  task: string;
  detail: string;
  progress: number;
};

export type Job = {
  id: number;
  episode_id: number;
  role: string;
  kind: string;
  status: string;
  attempts: number;
  created_at: string;
  updated_at: string;
  error: string | null;
  slug: string;
  title: string;
  goal: string;
  output_available: boolean;
};

export type Episode = {
  id: number;
  slug: string;
  title: string;
  goal: string;
  created_at: string;
};

export type Role = {
  role: string;
  label: string;
  kind: string;
};

export type Event = {
  id: number;
  job_id: number;
  event: string;
  at: string;
  role?: string;
  episode_id?: number;
  tone?: "green" | "gold" | "muted" | "blue";
};

export type Doctor = {
  python: string;
  paths: Record<string, { path: string; exists: boolean }>;
  tools: Record<string, string | null>;
  comfyui: { reachable: boolean; enabled: boolean; status?: number; error?: string } | null;
  hermes_mode: string;
};

export type ApiError = {
  error: string;
  message?: string;
  details?: string;
};

const BASE = "/api";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as ApiError;
    throw new Error(err.error || `Erro ${res.status} ao buscar ${path}`);
  }
  return res.json();
}

export const api = {
  episodes: () => getJSON<{ episodes: Episode[] }>("/episodes"),
  jobs: (episode?: number) => {
    const qs = episode !== undefined ? `?episode=${episode}` : "";
    return getJSON<{ jobs: Job[] }>(`/jobs${qs}`);
  },
  job: (id: number) => getJSON<{ job: Job; events: Event[]; output_available: boolean; output_meta: any }>(`/jobs/${id}`),
  jobOutput: (id: number) => fetch(`${BASE}/jobs/${id}/output`, { cache: "no-store" }),
  roles: () => getJSON<{ roles: Role[] }>("/roles"),
  logs: (limit = 100) => getJSON<{ events: Event[] }>(`/logs?limit=${limit}`),
  doctor: () => getJSON<Doctor>("/doctor"),
};

export type DataState<T> = { data: T | null; loading: boolean; error: string | null };

export function createDataState<T>(): DataState<T> {
  return { data: null, loading: true, error: null };
}

export const initialData = {
  agents: [] as Agent[],
  pipeline: [] as any[],
  approvals: [] as any[],
  activity: [] as any[],
  navigation: [] as any[],
  episodes: [] as Episode[],
  jobs: [] as Job[],
  roles: [] as Role[],
  events: [] as Event[],
  doctor: null as Doctor | null,
};
