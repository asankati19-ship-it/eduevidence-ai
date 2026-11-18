import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, CircleDashed, LoaderCircle, X } from 'lucide-react';
import { useId, useLayoutEffect, useRef, type ReactNode } from 'react';
import { ApiError } from '../services/api';

export const number = (value: number) => new Intl.NumberFormat().format(value);
export const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
export const size = (bytes: number) => bytes < 1024 ? bytes + ' B' : bytes < 1048576 ? (bytes / 1024).toFixed(1) + ' KB' : (bytes / 1048576).toFixed(1) + ' MB';

const STATUS: Record<string, string> = {
  indexed: 'Indexed', error: 'Indexing error', processing: 'Processing', retired: 'Removed',
  answered: 'Answered', abstained: 'Abstained', provider_error: 'Provider error',
  validation_error: 'Validation error', processing_error: 'Processing error',
  helpful: 'Helpful', not_helpful: 'Not helpful', sufficient: 'Evidence found',
  insufficient: 'Insufficient evidence', rejected: 'Rejected', accepted: 'Accepted',
  supported: 'Verified', legacy_answer: 'Earlier answer',
};

export function Status({ value, label }: { value: string; label?: string }) {
  const tone = ['indexed', 'answered', 'helpful', 'sufficient', 'supported'].includes(value) ? 'green' :
    ['error', 'provider_error', 'validation_error', 'processing_error', 'rejected', 'not_helpful'].includes(value) ? 'red' :
    ['abstained', 'processing', 'insufficient'].includes(value) ? 'amber' : 'neutral';
  return <span className={'status ' + tone}><span aria-hidden="true" />{label ?? STATUS[value] ?? value}</span>;
}

export function Heading({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}

export function Loading({ label = 'Loading workspace…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={19} />{label}</div>;
}

export function Notice({ error, children, retry, title }: { error?: unknown; children?: ReactNode; retry?: () => void; title?: string }) {
  const message = error instanceof Error ? error.message : 'The request could not be completed.';
  return <div className={'notice ' + (error ? 'notice-error' : '')} role={error ? 'alert' : 'status'}>
    {error ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
    <div>{title && <strong>{title}</strong>}{error ? message : children}{error instanceof ApiError && error.requestId && <small>Request {error.requestId}</small>}</div>
    {retry && <button type="button" className="button small secondary" onClick={retry}>Try again</button>}
  </div>;
}

export function Empty({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><CircleDashed size={24} /></div><h2>{title}</h2><p>{text}</p>{action}</div>;
}

export function Cell({ label, children, className }: { label?: string; children: ReactNode; className?: string }) {
  return <td role="cell" className={className}>
    {label && <span className="cell-label" aria-hidden="true">{label}</span>}
    <div className="cell-value">{children}</div>
  </td>;
}

export function Pager({ offset, total, limit, onChange }: { offset: number; total: number; limit: number; onChange: (offset: number) => void }) {
  if (total <= limit && offset === 0) return null;
  return <div className="pager" aria-label="Pagination">
    <span>{total ? Math.min(offset + 1, total) : 0}–{Math.min(offset + limit, total)} of {total}</span>
    <button className="icon-button" aria-label="Previous page" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}><ArrowLeft size={16} /></button>
    <button className="icon-button" aria-label="Next page" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}><ArrowRight size={16} /></button>
  </div>;
}

export function Modal({ title, children, onClose, wide = false, drawer = false, busy = false }: {
  title: string; children: ReactNode; onClose: () => void; wide?: boolean; drawer?: boolean; busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useLayoutEffect(() => {
    const dialog = ref.current;
    const previousFocus = document.activeElement;
    dialog?.showModal();
    return () => {
      if (dialog?.open) dialog.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, []);
  return <dialog ref={ref} className={'modal' + (wide ? ' modal-wide' : '') + (drawer ? ' nav-drawer' : '')} aria-labelledby={titleId}
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <div className="modal-head"><h2 id={titleId}>{title}</h2>
      <button className="icon-button" onClick={onClose} disabled={busy} aria-label={drawer ? 'Close navigation' : 'Close dialog'}><X size={20} /></button>
    </div>
    <div className="modal-body">{children}</div>
  </dialog>;
}

