import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Database, ExternalLink, HeartPulse, Search, ShieldCheck, Workflow } from 'lucide-react';
import { useDeferredValue } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AnswerCard } from '../components/AnswerCard';
import { Cell, Empty, Heading, Loading, Modal, Notice, Pager, Status, date } from '../components/Primitives';
import { api } from '../services/api';
import { pageOffset, positiveId, withSearch } from '../services/searchParams';
import { eventLabel } from './Overview';

const LIMIT = 12;
const OUTCOMES = ['answered', 'abstained', 'provider_error', 'validation_error', 'processing_error', 'processing'];
const OUTCOME_LABELS = ['Answered', 'Abstained', 'Provider error', 'Validation error', 'Processing error', 'Processing'];
const AUDIT_TYPES = ['document.upload', 'document.index', 'document.reindex', 'document.retire', 'question.submit', 'question.retrieve', 'question.verify', 'question.complete', 'answer.feedback'];

function Trace({ id, onClose }: { id: number; onClose: () => void }) {
  const trace = useQuery({ queryKey: ['question', id], queryFn: () => api.question(id),
    refetchInterval: (query) => query.state.data?.status === 'processing' ? 1500 : false });
  const item = trace.data;
  return <Modal title="Question trace" onClose={onClose} wide>
    {trace.isPending && <Loading label="Loading question trace…" />}
    {trace.isError && <Notice error={trace.error} retry={() => void trace.refetch()} />}
    {item && <>
      <div className="trace-top"><h3>{item.question_text}</h3><p>Request <code>{item.request_id}</code></p>
        <div className="trace-links">
          <Link className="text-button" to={'/audit?request=' + item.request_id}>View correlated audit events <ArrowRight size={15} /></Link>
          {item.conversation_id && <Link className="text-button" to={'/assistant?thread=' + item.conversation_id +
            (item.course_id ? '&course=' + item.course_id : '') + (item.document_id ? '&document=' + item.document_id : '')}>Open conversation <ArrowRight size={15} /></Link>}
        </div>
      </div>
      <AnswerCard question={item} />
      {item.answer && <dl className="detail-grid">
        <div><dt>Provider</dt><dd>{item.answer.provider}</dd></div><div><dt>Model</dt><dd>{item.answer.model ?? '—'}</dd></div>
        <div><dt>Prompt version</dt><dd>{item.answer.prompt_version}</dd></div><div><dt>API outcome</dt><dd>{item.answer.api_outcome}</dd></div>
        <div><dt>Latency</dt><dd>{item.answer.latency_ms === null ? '—' : item.answer.latency_ms + ' ms'}</dd></div>
        <div><dt>Input / output tokens</dt><dd>{item.answer.input_tokens ?? '—'} / {item.answer.output_tokens ?? '—'}</dd></div>
      </dl>}
      <section className="trace-sources"><h4>Ranked retrieval</h4>
        {item.sources.length ? <ol>{item.sources.map((source) => <li key={source.chunk_id}>
          <strong>{source.document_title}</strong><small>Page {source.page_number} · Chunk {source.chunk_number} · Similarity {source.score.toFixed(3)}</small>
        </li>)}</ol> : <p>No ranked passages were stored for this question.</p>}
      </section>
    </>}
  </Modal>;
}

export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const search = (params.get('q') ?? '').slice(0, 150);
  const deferredSearch = useDeferredValue(search.trim());
  const status = params.get('status') ?? '';
  const offset = pageOffset(params, LIMIT);
  const rows = useQuery({
    queryKey: ['history', { status, search: deferredSearch, offset }],
    queryFn: () => api.history({ status, search: deferredSearch, offset, limit: LIMIT }),
    refetchInterval: (query) => query.state.data?.items.some((item) => item.status === 'processing') ? 1500 : false,
  });
  const id = positiveId(params.get('question'));
  const update = (changes: Record<string, string | number | null>, replace = true) =>
    setParams((current) => withSearch(current, changes), { replace });
  return <>
    <Heading title="Question History" subtitle="Review past questions, answers, and the evidence used to generate them." />
    <section className="panel table-panel" aria-label="Stored questions"><div className="filter-bar">
      <label className="search"><Search size={18} /><input aria-label="Search questions" placeholder="Search questions…" value={search} maxLength={150} onChange={(event) => update({ q: event.target.value, offset: null })} /></label>
      <select aria-label="Filter by question outcome" value={status} onChange={(event) => update({ status: event.target.value, offset: null })}>
        <option value="">All outcomes</option>{OUTCOMES.map((value, index) => <option value={value} key={value}>{OUTCOME_LABELS[index]}</option>)}
      </select>
    </div>
      {rows.isPending && <Loading />}
      {rows.isError && <Notice error={rows.error} retry={() => void rows.refetch()} />}
      {rows.data && (rows.data.items.length ? <div className="table-scroll"><table role="table" aria-label="Saved question traces">
        <thead role="rowgroup"><tr role="row"><th scope="col">Question</th><th scope="col">Outcome</th><th scope="col">Sources</th><th scope="col">Asked</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
        <tbody role="rowgroup">{rows.data.items.map((item) => <tr role="row" key={item.id}><Cell className="primary-cell"><strong>{item.question_text}</strong><small>{item.document_title ?? (item.course_id ? 'Course scope' : 'All courses')}</small></Cell>
          <Cell label="Outcome"><Status value={item.status === 'answered' && !item.answer?.verification_passed ? 'legacy_answer' : item.status} /></Cell><Cell label="Sources">{item.citations.length}</Cell><Cell label="Asked" className="time-cell">{date(item.created_at)}</Cell>
          <Cell className="action-cell"><button className="button secondary small" aria-label={'View trace for ' + item.question_text} onClick={() => update({ question: item.id }, false)}>View trace <ArrowRight size={16} /></button></Cell></tr>)}</tbody>
      </table></div> : <Empty title={search || status ? 'No matching questions' : 'No questions yet'} text={search || status ? 'Clear the search or try a different outcome.' : 'Your questions will appear here after you use the assistant.'}
        action={search || status ? undefined : <Link className="button primary small" to="/assistant">Open assistant <ArrowRight size={16} /></Link>} />)}
      {rows.data && <Pager offset={offset} total={rows.data.total} limit={LIMIT} onChange={(next) => update({ offset: next || null })} />}
    </section>
    {id && <Trace key={id} id={id} onClose={() => update({ question: null })} />}
  </>;
}

export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const offset = pageOffset(params, LIMIT);
  const eventType = params.get('event') ?? '';
  const requestId = params.get('request') ?? '';
  const rows = useQuery({
    queryKey: ['audit', { eventType, requestId, offset }],
    queryFn: () => api.audit({ event_type: eventType, request_id: requestId, offset, limit: LIMIT }),
  });
  const update = (changes: Record<string, string | number | null>) =>
    setParams((current) => withSearch(current, changes), { replace: true });
  return <>
    <Heading title="Audit Logs" subtitle="Inspect correlated document, question, and feedback events." action={<button className="button secondary" onClick={() => void rows.refetch()} disabled={rows.isFetching}>Refresh</button>} />
    <section className="panel table-panel" aria-label="Audit events"><div className="filter-bar">
      <select aria-label="Filter by event type" value={eventType} onChange={(event) => update({ event: event.target.value, offset: null })}>
        <option value="">All events</option>{AUDIT_TYPES.map((item) => <option key={item} value={item}>{eventLabel(item)}</option>)}
      </select>
      {requestId && <button className="button secondary small" onClick={() => update({ request: null, offset: null })}>Clear request filter</button>}
    </div>
      {requestId && <p className="request-filter">Request <code>{requestId}</code></p>}
      {rows.isPending && <Loading />}
      {rows.isError && <Notice error={rows.error} retry={() => void rows.refetch()} />}
      {rows.data && (rows.data.items.length ? <div className="table-scroll"><table role="table" aria-label="Workspace audit events">
        <thead role="rowgroup"><tr role="row"><th scope="col">Event</th><th scope="col">Outcome</th><th scope="col">Request ID</th><th scope="col">Time</th><th scope="col">Record</th></tr></thead>
        <tbody role="rowgroup">{rows.data.items.map((item) => <tr role="row" key={item.id}>
          <Cell className="primary-cell"><strong>{eventLabel(item.event_type)}</strong>{item.detail && <small>{item.detail}</small>}</Cell><Cell label="Outcome"><Status value={item.outcome} /></Cell>
          <Cell label="Request ID"><button className="text-button audit-id" title={item.request_id} onClick={() => update({ request: item.request_id, offset: null })}>{item.request_id.slice(0, 13)}…<span className="sr-only"> Filter by request {item.request_id}</span></button></Cell>
          <Cell label="Time" className="time-cell">{date(item.created_at)}</Cell>
          <Cell label="Record">{item.question_id ? <Link className="text-button" to={'/history?question=' + item.question_id}>Question {item.question_id}</Link> :
            item.document_id ? <Link className="text-button" to={'/documents?document=' + item.document_id}>Document {item.document_id}</Link> : '—'}</Cell>
        </tr>)}</tbody></table></div> : <Empty title="No audit events" text="Workspace actions appear here when they match your filters." />)}
      {rows.data && <Pager offset={offset} total={rows.data.total} limit={LIMIT} onChange={(next) => update({ offset: next || null })} />}
    </section>
  </>;
}

export function SettingsPage() {
  const system = useQuery({ queryKey: ['system'], queryFn: api.system });
  const data = system.data;
  return <>
    <Heading title="System Health" subtitle="Check the local backend, SQLite schema, retrieval policy, and OpenAI configuration."
      action={<button className="button secondary" onClick={() => void system.refetch()} disabled={system.isFetching}><HeartPulse size={18} /> Refresh status</button>} />
    {system.isPending && <Loading />}
    {system.isError && <Notice title="System health unavailable" error={system.error} retry={() => void system.refetch()} />}
    {data && <>
      <div className="settings-grid">
        <section className="panel settings-card"><div className="metric-icon mint"><Database size={19} /></div><h2>SQLite database</h2>
          <dl><div><dt>Connection</dt><dd>{data.database.status}</dd></div><div><dt>Schema version</dt><dd>{data.database.schema_version}</dd></div>
            <div><dt>Local learner</dt><dd>{data.learner.display_name}</dd></div></dl></section>
        <section className="panel settings-card"><div className="metric-icon lilac"><ShieldCheck size={19} /></div><h2>Answer provider</h2>
          <dl><div><dt>Provider</dt><dd>{data.provider.name}</dd></div><div><dt>Configuration</dt><dd>{data.provider.configured ? 'Configured' : 'Missing API key'}</dd></div>
            <div><dt>Model</dt><dd>{data.provider.model}</dd></div><div><dt>Timeout / retries</dt><dd>{data.provider.timeout_seconds}s / {data.provider.max_retries}</dd></div></dl>
          <p>Provider access is checked when a supported question is sent.</p></section>
        <section className="panel settings-card"><div className="metric-icon blue"><Workflow size={19} /></div><h2>Retrieval & indexing</h2>
          <dl><div><dt>Engine</dt><dd>{data.retrieval.engine}</dd></div><div><dt>Top passages / min. score</dt><dd>{data.retrieval.top_k} / {data.retrieval.min_score}</dd></div>
            <div><dt>Min. terms / overlap</dt><dd>{data.retrieval.min_query_terms} / {data.retrieval.min_query_overlap}</dd></div>
            <div><dt>Chunk / overlap</dt><dd>{data.retrieval.chunk_words} / {data.retrieval.chunk_overlap} words</dd></div>
            <div><dt>PDF limits</dt><dd>{data.upload.max_mb} MB / {data.upload.max_pages} pages</dd></div></dl></section>
      </div>
      <section className="panel local-system"><div><h2>Local configuration</h2><p>Update backend settings in the project’s <code>.env</code> file and restart FastAPI. This workspace contains synthetic course data.</p></div>
        <a className="button secondary small" href={__API_DOCS_URL__} target="_blank" rel="noreferrer">API documentation <ExternalLink size={15} /></a></section>
    </>}
  </>;
}

