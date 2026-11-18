import { useIsMutating, useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, BookOpenCheck, FileSearch, History, MessageSquarePlus, Send, ShieldCheck, Sparkles } from 'lucide-react';
import { useDeferredValue, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { AnswerCard } from '../components/AnswerCard';
import { Heading, Loading, Notice } from '../components/Primitives';
import { api } from '../services/api';
import { readAssistantSession, saveAssistantSession } from '../services/assistantSession';
import { positiveId, withSearch } from '../services/searchParams';
import type { Page, Question, QuestionInput } from '../types';

const ASK_KEY = ['question', 'submit'] as const;
const STARTERS = [
  'What are the course completion requirements?',
  'How do I submit a graded assessment?',
  'What are the attendance requirements?',
];

export function AssistantPage() {
  const [params] = useSearchParams();
  const saved = readAssistantSession();
  if (!params.size && saved.search) return <Navigate to={{ search: '?' + saved.search }} replace />;
  return <Conversation />;
}

function Conversation() {
  const [params, setParams] = useSearchParams();
  const search = params.toString();
  const course = positiveId(params.get('course'));
  const document = positiveId(params.get('document'));
  const thread = params.get('thread');
  const [text, setText] = useState(() => {
    const saved = readAssistantSession();
    return saved.search === search ? saved.draft : '';
  });
  const [failedInput, setFailedInput] = useState<QuestionInput>();
  const input = useRef<HTMLTextAreaElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const lastTurn = useRef<number | undefined>(undefined);
  const client = useQueryClient();
  const submitting = useIsMutating({ mutationKey: ASK_KEY }) > 0;
  const pendingInputs = useMutationState({
    filters: { mutationKey: ASK_KEY, status: 'pending' },
    select: (item) => item.state.variables as QuestionInput | undefined,
  });
  const pending = pendingInputs.find((item) => item?.conversation_id === thread && !!item);
  const conversationKey = ['history', 'conversation', thread];
  const courses = useQuery({ queryKey: ['courses'], queryFn: api.courses });
  const system = useQuery({ queryKey: ['system'], queryFn: api.system });
  const documents = useQuery({
    queryKey: ['documents', 'assistant', course],
    queryFn: async () => {
      const filters = { status: 'indexed', course_id: course ?? undefined, limit: 100 };
      const first = await api.documents(filters);
      const offsets = Array.from({ length: Math.max(0, Math.ceil(first.total / 100) - 1) }, (_, index) => (index + 1) * 100);
      const pages = await Promise.all(offsets.map((offset) => api.documents({ ...filters, offset })));
      return [...first.items, ...pages.flatMap((page) => page.items)];
    },
  });
  const conversation = useQuery({
    queryKey: conversationKey, enabled: !!thread,
    queryFn: () => api.history({ conversation_id: thread ?? '', limit: 100 }),
    refetchInterval: (query) => pending || query.state.data?.items.some((question) => question.status === 'processing') ? 700 : false,
  });

  const mutation = useMutation({
    mutationKey: ASK_KEY,
    mutationFn: api.ask,
    onSuccess: (answer, variables) => {
      const key = ['history', 'conversation', variables.conversation_id];
      client.setQueryData<Page<Question>>(key, (previous) => {
        const items = previous?.items ?? [];
        return {
          items: [answer, ...items.filter((item) => item.id !== answer.id)].sort((a, b) => b.id - a.id).slice(0, 100),
          total: (previous?.total ?? 0) + Number(!items.some((item) => item.id === answer.id)),
          limit: 100, offset: 0,
        };
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ['history'] });
      void client.invalidateQueries({ queryKey: ['overview'] });
      void client.invalidateQueries({ queryKey: ['audit'] });
    },
  });

  useEffect(() => { saveAssistantSession(search, text); }, [search, text]);
  const questions = [...(conversation.data?.items ?? [])].reverse();
  const latest = questions.at(-1);
  const latestId = latest?.id;
  const latestStatus = latest?.status;
  let draftError: string | undefined;
  const unavailable = !!document && !!documents.data && !documents.data.some((item) => item.id === document);
  if (failedInput && mutation.isError) draftError = 'Question could not be sent.';

  useEffect(() => {
    if (latestId === undefined || latestStatus === 'processing' || lastTurn.current === latestId) return;
    lastTurn.current = latestId;
    const panel = transcript.current;
    const turn = panel?.querySelector<HTMLElement>('[data-turn="' + latestId + '"]');
    if (panel && turn && panel.clientHeight < panel.scrollHeight) {
      panel.scrollTop += turn.getBoundingClientRect().top - panel.getBoundingClientRect().top - 16;
    }
  }, [latestId, latestStatus]);

  function updateRoute(next: URLSearchParams, draft = text, replace = true) {
    saveAssistantSession(next.toString(), draft);
    setParams(next, { replace });
  }

  function send(values: QuestionInput) {
    if (client.isMutating({ mutationKey: ASK_KEY })) return;
    input.current?.focus({ preventScroll: true });
    setText('');
    setFailedInput(undefined);
    updateRoute(withSearch(params, { thread: values.conversation_id }), '', !!thread);
    mutation.mutate(values, {
      onError: () => { setText(values.question); setFailedInput(values); },
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = text.trim();
    if (question.length < 3 || !/[\p{L}\p{N}]/u.test(question) || unavailable || documents.isPending || documents.isError) return;
    send({ question, course_id: course, document_id: document, conversation_id: thread ?? crypto.randomUUID() });
  }

  const deferredText = useDeferredValue(text.trim());
  const submitDisabled = submitting || documents.isPending || documents.isError || unavailable
    || text.trim().length < 3 || !/[\p{L}\p{N}]/u.test(text);
  return <>
    <Heading title="Knowledge Assistant" subtitle="Ask about your course material and check the page behind each answer."
      action={<button className="button secondary" disabled={(!thread && !search && !text) || submitting} onClick={() => {
        setText(''); setFailedInput(undefined); mutation.reset(); updateRoute(new URLSearchParams(), '', false); input.current?.focus();
      }}><MessageSquarePlus size={18} /> New conversation</button>} />
    <section className="assistant-layout" aria-label="Course question assistant">
      <aside className="assistant-side">
        <section className="panel scope-panel">
          <div className="scope-heading"><span className="scope-icon"><FileSearch size={20} /></span><div><h2>Search scope</h2><p>Choose the PDFs to search.</p></div></div>
          <div className="scope-fields">
            <div className="field"><label htmlFor="scope-course">Course</label>
              <select id="scope-course" value={course ?? ''} disabled={submitting || courses.isPending || courses.isError}
                onChange={(event) => updateRoute(withSearch(params, { course: event.target.value, document: null }))}>
                <option value="">All courses</option>{courses.data?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
            </div>
            <div className="field"><label htmlFor="scope-document">Document</label>
              <select id="scope-document" value={document ?? ''} disabled={submitting || documents.isPending || documents.isError}
                onChange={(event) => updateRoute(withSearch(params, { document: event.target.value }))}>
                <option value="">{documents.isPending ? 'Loading PDFs…' : 'All indexed PDFs'}</option>
                {!!document && !documents.data?.some((item) => item.id === document) &&
                  <option value={document}>{documents.isPending ? 'Loading selected PDF…' : 'Selected PDF unavailable'}</option>}
                {documents.data?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
            </div>
          </div>
          {(documents.isError || courses.isError) && <Notice error={documents.error ?? courses.error} retry={() => {
            if (documents.isError) void documents.refetch();
            if (courses.isError) void courses.refetch();
          }} />}
          {unavailable && <p role="alert">Choose an available PDF or search all indexed PDFs.</p>}
          {documents.data?.length === 0 && <p>No indexed PDFs in this scope. <Link className="text-button" to="/documents">Open library</Link></p>}
        </section>
        {system.data && !system.data.provider.configured && <div className="provider-note" role="status"><strong>OpenAI setup required</strong>
          <p>Configure the backend API key to generate answers from retrieved evidence.</p><Link className="text-button" to="/settings">Open system health <ArrowUpRight size={15} /></Link></div>}
        {system.data?.provider.name.startsWith('offline') && <div className="provider-note" role="status"><strong>Offline test fixture</strong><p>This test session uses a deterministic provider.</p></div>}
        <Link className="panel history-shortcut" to="/history"><History size={19} /><span><strong>Question history</strong><small>Open past answers and conversations</small></span><ArrowUpRight size={16} /></Link>
      </aside>
      <div className="assistant-main panel">
        <div className="chat-header"><BookOpenCheck size={19} aria-hidden="true" /><h2>{thread ? 'Conversation' : 'New conversation'}</h2></div>
        <div className="transcript" ref={transcript} role="region" aria-label="Conversation messages" tabIndex={0}>
          {thread && conversation.isPending && !pending && <Loading label="Loading conversation…" />}
          {conversation.isError && <Notice error={conversation.error} retry={() => void conversation.refetch()} />}
          {questions.length === 0 && !pending && (!thread || conversation.isSuccess) && <div className="chat-empty">
            <span className="chat-emblem"><Sparkles size={30} strokeWidth={1.6} /></span>
            <h3>What would you like to find?</h3>
            <p>Start with an assignment, a course requirement, or an attendance policy.</p>
            <div className="starter-list">{STARTERS.map((starter) => <button type="button" key={starter}
              onClick={() => { setText(starter); input.current?.focus(); }}>{starter}<ArrowUpRight size={16} /></button>)}</div>
          </div>}
          {questions.length > 0 && <div className="messages">
            {(conversation.data?.total ?? 0) > 100 && <Link className="text-button" to="/history">See older questions in history</Link>}
            {questions.map((question) => <div className="turn" key={question.id} data-turn={question.id}>
              <UserMessage text={question.question_text} />
              <AnswerCard question={question} onRetry={submitting ? undefined : () => send({
                question: question.question_text, course_id: question.course_id, document_id: question.document_id,
                conversation_id: thread ?? crypto.randomUUID(),
              })} />
            </div>)}
          </div>}
          {pending && !questions.some((item) => item.status === 'processing') && <div className="turn pending-turn">
            <UserMessage text={pending.question} /><Loading label="Asking question and searching for evidence…" />
          </div>}
        </div>
        {draftError && <Notice error={mutation.error} retry={failedInput && !submitting ? () => send(failedInput) : undefined} />}
        <form className="composer" onSubmit={submit}>
          <div className="composer-input"><label className="sr-only" htmlFor="question">Your question</label>
            <textarea id="question" ref={input} value={text} maxLength={1200} rows={2} placeholder="Ask a question about your course PDFs…"
              readOnly={submitting} aria-describedby="composer-help" onChange={(event) => setText(event.target.value)} onKeyDown={(event) => {
                if (!event.nativeEvent.isComposing && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }} />
            <button className="send" type="submit" disabled={submitDisabled} aria-label="Send question"><Send size={18} /> <span>Send</span></button>
          </div>
          <small id="composer-help"><span><ShieldCheck size={14} /> Ctrl or ⌘ + Enter to send</span><span>{text.length}/1200</span></small>
          <span className="sr-only" role="status">{deferredText && deferredText.length < 3 ? 'Enter at least three characters.' : ''}</span>
        </form>
      </div>
    </section>
  </>;
}

function UserMessage({ text }: { text: string }) {
  return <div className="user-message"><span>You</span><p>{text}</p></div>;
}

