export function withSearch(params: URLSearchParams, changes: Record<string, string | number | null>) {
  const next = new URLSearchParams(params);
  for (const [name, value] of Object.entries(changes)) {
    if (value === null || value === '') next.delete(name);
    else next.set(name, String(value));
  }
  return next;
}

export function pageOffset(params: URLSearchParams, limit: number) {
  const value = Number(params.get('offset'));
  return Number.isSafeInteger(value) && value > 0 ? Math.floor(value / limit) * limit : 0;
}

export function positiveId(value: string | null) {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

