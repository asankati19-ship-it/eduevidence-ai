const KEY = 'eduevidence.assistant.v1';
const EMPTY = { search: '', draft: '' };

export function readAssistantSession() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY) ?? 'null');
    return typeof stored?.search === 'string' && typeof stored?.draft === 'string'
      ? { search: stored.search, draft: stored.draft.slice(0, 1200) }
      : EMPTY;
  } catch {
    return EMPTY;
  }
}

export function saveAssistantSession(search: string, draft: string) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ search, draft }));
  } catch {
    // The current conversation URL still works when browser storage is unavailable.
  }
}

