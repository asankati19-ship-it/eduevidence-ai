import type { AuditEvent, Course, Document, Overview, Page, Question, QuestionInput, Rating, SystemStatus } from '../types';

export class ApiError extends Error {
  constructor(message: string, readonly code: string, readonly requestId?: string) {
    super(message);
  }
}

type Filters = Record<string, string | number | undefined>;
const query = (filters: Filters) => {
  const values = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') values.set(key, String(value));
  });
  return values.size ? '?' + values.toString() : '';
};

async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch('/api' + path, init);
  } catch (error) {
    if (init?.signal?.aborted) throw error;
    throw new ApiError('The local backend could not be reached. Check that it is running.', 'network');
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const issue = payload?.error?.issues?.[0];
    const message = issue?.message?.replace(/^Value error, /, '') ?? payload?.error?.message;
    throw new ApiError(message ?? 'The local backend could not complete the request.', payload?.error?.code ?? 'http_error', payload?.error?.request_id);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchResponse(path, init);
  if (response.status === 204) return undefined as T;
  return response.json();
}

const json = (body: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

export const api = {
  courses: () => request<Course[]>('/courses'),
  documents: (filters: Filters = {}) => request<Page<Document>>('/documents' + query(filters)),
  document: (id: number) => request<Document>('/documents/' + id),
  page: (id: number, page: number) => '/api/documents/' + id + '/pages/' + page,
  pagePreview: async (id: number, page: number, signal?: AbortSignal) =>
    (await fetchResponse('/documents/' + id + '/pages/' + page, { signal })).blob(),
  upload: (body: FormData) => request<Document>('/documents/upload', { method: 'POST', body }),
  reindex: (id: number) => request<Document>('/documents/' + id + '/reindex', { method: 'POST' }),
  remove: (id: number) => request<void>('/documents/' + id, { method: 'DELETE' }),
  ask: (body: QuestionInput) => request<Question>('/questions', json(body)),
  question: (id: number) => request<Question>('/questions/' + id),
  history: (filters: Filters = {}) => request<Page<Question>>('/questions/history' + query(filters)),
  feedback: (id: number, rating: Rating) => request<{ answer_id: number; rating: Rating }>('/answers/' + id + '/feedback', json({ rating })),
  overview: () => request<Overview>('/analytics/overview'),
  audit: (filters: Filters = {}) => request<Page<AuditEvent>>('/audit/events' + query(filters)),
  system: () => request<SystemStatus>('/system/status'),
};

