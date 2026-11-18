import { useQuery } from '@tanstack/react-query';
import { Activity, ArrowDownRight, ArrowRight, BookOpenCheck, CheckCircle2, FileCheck2, Files, Layers3, MessageSquareText, ShieldCheck, ThumbsDown, ThumbsUp, UploadCloud } from 'lucide-react';
import type { ComponentType } from 'react';
import { Link } from 'react-router-dom';
import { Empty, Heading, Loading, Notice, Status, date, number } from '../components/Primitives';
import { api } from '../services/api';
import type { AuditEvent, Overview } from '../types';

const EVENTS: Record<string, string> = {
  'document.upload': 'PDF upload', 'document.index': 'Document indexed',
  'document.reindex': 'Reindex requested', 'document.retire': 'Document removed',
  'question.submit': 'Question submitted', 'question.retrieve': 'Evidence ranked', 'question.verify': 'Answer verification',
  'question.complete': 'Question completed', 'answer.feedback': 'Feedback submitted',
};
export const eventLabel = (event: string) => EVENTS[event] ?? event;

function Metric({ label, value, detail, icon: Icon, tone }: {
  label: string; value: number; detail: string; icon: ComponentType<{ size: number }>; tone: string;
}) {
  return <article className="metric panel"><div className={'metric-icon ' + tone}><Icon size={20} /></div>
    <div className="metric-label">{label}</div><strong className="metric-number">{number(value)}</strong>
    <p>{detail}</p>
  </article>;
}

function Trend({ trend }: { trend: Overview['trend'] }) {
  const max = Math.max(1, ...trend.map((point) => point.total));
  const dayLabel = (day: string) => new Intl.DateTimeFormat(undefined, { weekday: 'short', timeZone: 'UTC' }).format(new Date(day));
  return <section className="panel trend-panel"><div className="panel-heading">
    <div><h2>Question activity</h2><p>Last 7 days · UTC</p></div><Activity size={19} />
  </div>
    <div className="chart-legend"><span><i aria-hidden="true" /> Questions</span><span><i aria-hidden="true" /> Answered</span></div>
    <ul className="chart" role="list" aria-label="Questions and answers by day">
      {trend.map((point) => <li key={point.day} aria-label={point.day + ': ' + point.total + ' questions, ' + point.answered + ' answered'}>
        <div className="bars" title={point.day + ' · ' + point.total + ' questions · ' + point.answered + ' answered'}>
          <div className="bar count" style={{ height: (point.total / max * 100) + '%' }} />
          <div className="bar answered" style={{ height: (point.answered / max * 100) + '%' }} />
        </div><span>{dayLabel(point.day)}</span>
      </li>)}
    </ul>
    {!trend.some((point) => point.total > 0) && <p className="chart-note">No questions in this period.</p>}
  </section>;
}

function Recent({ activity }: { activity: AuditEvent[] }) {
  return <section className="panel recent-panel"><div className="panel-heading">
    <div><h2>Recent activity</h2><p>Latest workspace events</p></div><Link to="/audit" className="text-button">View audit <ArrowRight size={15} /></Link>
  </div>
    {activity.length ? <ul className="activity-list">{activity.slice(0, 4).map((item) => {
      const Icon = item.event_type.startsWith('document.') ? FileCheck2 : item.event_type === 'answer.feedback' ? ThumbsUp : MessageSquareText;
      return <li key={item.id}>
        <div className="activity-icon"><Icon size={17} /></div>
        <div><strong>{item.event_type === 'document.index' && item.outcome === 'error' ? 'Indexing failed' : eventLabel(item.event_type)}</strong><small>{date(item.created_at)}</small></div>
        <Status value={item.outcome} />
      </li>;
    })}</ul> : <Empty title="No activity yet" text="Uploads, questions, and feedback will appear here." />}
  </section>;
}

function FeedbackSummary({ data, showLink = true }: { data: Overview; showLink?: boolean }) {
  return <section className="panel feedback-summary">
    <div className="panel-heading"><div><h2>Learner feedback</h2><p>{number(data.feedback.total)} {data.feedback.total === 1 ? 'rating' : 'ratings'} recorded</p></div>{showLink && <Link to="/analytics" className="text-button">Analytics <ArrowRight size={15} /></Link>}</div>
    <div className="feedback-totals"><span><ThumbsUp size={17} /> <strong>{number(data.feedback.helpful)}</strong> Helpful</span>
      <span><ThumbsDown size={17} /> <strong>{number(data.feedback.not_helpful)}</strong> Not helpful</span></div>
  </section>;
}

function LibraryReadiness({ counts }: { counts: Overview['documents'] }) {
  return <section className="panel readiness">
    <div className="panel-heading"><div><h2>Library readiness</h2><p>PDFs available to the assistant</p></div>
      <span className="metric-icon mint"><Files size={19} /></span></div>
    <div className="readiness-count"><strong>{number(counts.indexed)}</strong> of {number(counts.total)} indexed</div>
    <meter min={0} max={Math.max(1, counts.total)} value={counts.indexed} aria-label="Indexed documents" />
    <div className="readiness-foot"><span>{number(counts.processing)} indexing · {number(counts.errors)} with errors</span>
      <Link to="/documents" className="text-button">Open library <ArrowRight size={15} /></Link></div>
  </section>;
}

export function OverviewPage() {
  const metrics = useQuery({ queryKey: ['overview'], queryFn: api.overview,
    refetchInterval: (query) => query.state.data?.documents.processing ? 1000 : false });
  const data = metrics.data;
  return <>
    <Heading title="Overview" subtitle="Track your course library, question activity, and learner feedback."
      action={<Link className="button secondary" to="/documents?upload=1"><UploadCloud size={18} /> Upload a PDF</Link>} />
    <div className="overview-intro">
      <section className="hero">
        <span className="hero-symbol" aria-hidden="true"><BookOpenCheck size={24} strokeWidth={1.65} /></span>
        <h2>Trusted answers.<br />Verified sources.</h2>
        <p>Ask a question about your course PDFs and jump straight to the supporting page.</p>
        <Link className="button hero-primary" to="/assistant">Open assistant <ArrowRight size={17} /></Link>
      </section>
      {data ? <LibraryReadiness counts={data.documents} /> : <section className="panel readiness">
        <h2>Library readiness</h2>
        {metrics.isPending && <Loading label="Checking the library…" />}
        {metrics.isError && <Notice title="Metrics unavailable" error={metrics.error} retry={() => void metrics.refetch()} />}
      </section>}
    </div>
    <div className="section-title"><h2>Workspace metrics</h2></div>
    {metrics.isPending && <Loading label="Loading live metrics…" />}
    {data && metrics.isError && <Notice title="Metrics refresh failed" error={metrics.error} retry={() => void metrics.refetch()} />}
    {data && <>
      <div className="metric-grid">
        <Metric label="Documents" value={data.documents.total} detail={data.documents.indexed + ' indexed · ' + data.documents.errors + ' with errors'} icon={Files} tone="mint" />
        <Metric label="Indexed chunks" value={data.documents.chunks} detail={data.documents.processing + ' documents processing'} icon={Layers3} tone="blue" />
        <Metric label="Questions asked" value={data.questions.total} detail={data.questions.abstained + ' abstained'} icon={MessageSquareText} tone="lilac" />
        <Metric label="Verified answers" value={data.questions.verified} detail={data.questions.provider_errors + ' provider errors'} icon={CheckCircle2} tone="mint" />
      </div>
      <div className="dashboard-grid"><Trend trend={data.trend} /><Recent activity={data.activity} /></div>
      <FeedbackSummary data={data} />
    </>}
  </>;
}

export function AnalyticsPage() {
  const metrics = useQuery({ queryKey: ['overview'], queryFn: api.overview });
  const data = metrics.data;
  return <>
    <Heading title="Feedback & Analytics" subtitle="Review question outcomes and learner ratings stored in the workspace." action={<button className="button secondary" onClick={() => void metrics.refetch()} disabled={metrics.isFetching}><Activity size={17} /> Refresh</button>} />
    {metrics.isPending && <Loading />}
    {metrics.isError && <Notice error={metrics.error} retry={() => void metrics.refetch()} />}
    {data && <>
      <div className="metric-grid">
        <Metric label="Answered" value={data.questions.answered} detail={data.questions.verified + ' verified under current checks'} icon={CheckCircle2} tone="mint" />
        <Metric label="Abstained" value={data.questions.abstained} detail="Insufficient or ambiguous evidence" icon={ArrowDownRight} tone="blue" />
        <Metric label="Provider errors" value={data.questions.provider_errors} detail="Includes missing credentials" icon={Activity} tone="lilac" />
        <Metric label="Other failures" value={data.questions.validation_errors + data.questions.processing_errors} detail={data.questions.validation_errors + ' validation · ' + data.questions.processing_errors + ' processing'} icon={ShieldCheck} tone="blue" />
      </div>
      <div className="dashboard-grid"><Trend trend={data.trend} /><FeedbackSummary data={data} showLink={false} /></div>
    </>}
  </>;
}

