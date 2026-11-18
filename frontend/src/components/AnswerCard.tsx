import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, BookOpenCheck, Check, Copy, FileText, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useState } from 'react';
import { api } from '../services/api';
import type { Citation, Question, Rating } from '../types';
import { Loading, Modal, Notice, Status, date } from './Primitives';
import { AnswerMarkdown } from './AnswerMarkdown';
import { PagePreview } from './PagePreview';

function Evidence({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const query = useQuery({ queryKey: ['document', citation.document_id], queryFn: () => api.document(citation.document_id) });
  const lengthyName = Math.max(citation.document_title.length, citation.original_filename.length) > 76;
  return <Modal title="Source evidence" onClose={onClose} wide>
    <div className="evidence-heading">
      <div className="file-icon"><FileText size={21} aria-hidden="true" /></div>
      <div><h3 className={lengthyName ? 'long-source-name' : undefined}>{citation.document_title}</h3>
        {lengthyName ? <details className="name-details"><summary>Full document name and filename</summary>
          <p>{citation.document_title}</p><p>{citation.original_filename}</p>
        </details> : <p>{citation.original_filename}</p>}
        <div className="source-meta"><span>Page {citation.page_number}</span><span>Chunk {citation.chunk_number}</span><span>Revision {citation.revision}</span></div>
      </div>
    </div>
    <div className="evidence-layout">
      <section className="evidence-copy" aria-label="Supporting evidence text">
        <h4>Supporting quote</h4><blockquote>{citation.evidence_quote}</blockquote>
        <details className="excerpt"><summary>Read full retrieved passage</summary><p>{citation.content}</p></details>
      </section>
      <div>
        {query.isPending && <Loading label="Loading document metadata…" />}
        {query.isError && <Notice error={query.error} retry={() => void query.refetch()} />}
        {query.data && <PagePreview documentId={citation.document_id} initialPage={citation.page_number} pageCount={query.data.page_count} locked />}
      </div>
    </div>
  </Modal>;
}

export function AnswerCard({ question, onRetry }: { question: Question; onRetry?: () => void }) {
  const client = useQueryClient();
  const [citation, setCitation] = useState<Citation>();
  const [copyStatus, setCopyStatus] = useState<'copied' | 'failed'>();
  const answer = question.answer;
  const rating = useMutation({
    mutationFn: ({ id, value }: { id: number; value: Rating }) => api.feedback(id, value),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['question', question.id] });
      void client.invalidateQueries({ queryKey: ['history'] });
      void client.invalidateQueries({ queryKey: ['audit'] });
      void client.invalidateQueries({ queryKey: ['overview'] });
    },
  });
  async function copy() {
    if (!answer?.body) return;
    const refs = question.citations.map((source) => '[' + source.original_filename + ' — Page ' + source.page_number + ' — Chunk ' + source.chunk_number + ']');
    try {
      await navigator.clipboard.writeText([answer.body, ...refs].join('\n\n'));
      setCopyStatus('copied');
    } catch {
      setCopyStatus('failed');
    }
  }
  const feedback = rating.data?.rating ?? answer?.rating;
  const unsuccessful = ['provider_error', 'validation_error', 'processing_error'].includes(question.status);
  const legacy = question.status === 'answered' && !answer?.verification_passed;
  return <article className={'answer-card ' + (unsuccessful ? 'answer-error' : '')} aria-label="Assistant response">
    <header><span className="assistant-icon"><BookOpenCheck size={20} aria-hidden="true" /></span>
      <div><strong>EduEvidence AI</strong><small>{date(question.created_at)}</small></div>
      <span role="status"><Status value={legacy ? 'legacy_answer' : question.status} label={answer?.error_code === 'timeout' ? 'API timeout' :
        answer?.error_code === 'missing_credentials' ? 'Missing credentials' : undefined} /></span>
    </header>
    {answer ? <>
      {answer.body && (legacy ? <details className="excerpt">
        <summary>View stored answer from earlier validation</summary>
        <p>Ask the question again to apply the current evidence checks.</p>
        <AnswerMarkdown body={answer.body} />
      </details> : <AnswerMarkdown body={answer.body} />)}
      {answer.reason && <p className="answer-reason" role={unsuccessful ? 'alert' : undefined}>{answer.reason}</p>}
      {question.citations.length > 0 && <section className="citation-section" aria-label={legacy ? 'Saved citations' : 'Verified citations'}>
        <h3>Source evidence <span>{question.citations.length}</span></h3>
        <ul className="citation-list">{question.citations.map((source) => <li key={source.chunk_id}>
          <button className="citation" onClick={() => setCitation(source)} aria-haspopup="dialog">
            <span className="citation-icon"><FileText size={17} aria-hidden="true" /></span>
            <span><strong>{source.document_title}</strong><small>Page {source.page_number} · Chunk {source.chunk_number}</small></span>
            <ArrowUpRight size={15} aria-hidden="true" />
          </button>
        </li>)}</ul>
      </section>}
      {!legacy && (answer.body || ['answered', 'abstained'].includes(answer.status) || (answer.retryable && onRetry)) && <div className="answer-actions">
        {answer.body && <button className="icon-button labelled" onClick={() => void copy()}>{copyStatus === 'copied' ? <Check size={17} /> : <Copy size={17} />} Copy answer</button>}
        {['answered', 'abstained'].includes(answer.status) && <div className="rating-actions" role="group" aria-label="Rate this answer">
          <button className="icon-button" aria-label="Helpful" title="Helpful" aria-pressed={feedback === 'helpful'} disabled={rating.isPending || feedback === 'helpful'}
            onClick={() => rating.mutate({ id: answer.id, value: 'helpful' })}><ThumbsUp size={17} /></button>
          <button className="icon-button" aria-label="Not helpful" title="Not helpful" aria-pressed={feedback === 'not_helpful'} disabled={rating.isPending || feedback === 'not_helpful'}
            onClick={() => rating.mutate({ id: answer.id, value: 'not_helpful' })}><ThumbsDown size={17} /></button>
        </div>}
        {answer.retryable && onRetry && <button className="button secondary small" onClick={onRetry}><RefreshCw size={16} /> Retry question</button>}
        {copyStatus && <span className="copy-status" role="status">{copyStatus === 'copied' ? 'Answer copied.' : 'Clipboard unavailable. Select the answer text to copy it.'}</span>}
        {rating.isSuccess && !rating.isPending && <span className="copy-status" role="status">Feedback saved.</span>}
      </div>}
      {rating.isError && <Notice error={rating.error} retry={() => { if (rating.variables) rating.mutate(rating.variables); }} />}
    </> : <Loading label={question.sources.length ? 'Generating an answer…' : 'Searching for evidence…'} />}
    {citation && <Evidence key={citation.chunk_id} citation={citation} onClose={() => setCitation(undefined)} />}
  </article>;
}

