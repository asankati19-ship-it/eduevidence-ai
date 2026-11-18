import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, FileText, RefreshCw, Search, Trash2, UploadCloud } from 'lucide-react';
import { useDeferredValue, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Cell, Empty, Heading, Loading, Modal, Notice, Pager, Status, date, number, size } from '../components/Primitives';
import { PagePreview } from '../components/PagePreview';
import { api } from '../services/api';
import { pageOffset, positiveId, withSearch } from '../services/searchParams';
import type { Course, Document } from '../types';

function UploadForm({ courses, loading, courseError, retryCourses, limits, onClose, onFinished }: {
  courses: Course[]; loading: boolean; courseError: Error | null; retryCourses: () => void;
  limits: string; onClose: () => void; onFinished: (doc: Document) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const [file, setFile] = useState<File>();
  const [drag, setDrag] = useState(false);
  const [course, setCourse] = useState('');
  const [title, setTitle] = useState('');
  const mutation = useMutation({
    mutationFn: api.upload,
    onSuccess: onFinished,
    onSettled: () => { inFlight.current = false; },
  });
  function choose(next?: File) {
    if (inFlight.current) return;
    setFile(next);
    mutation.reset();
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !course || inFlight.current) return;
    const data = new FormData();
    data.set('file', file);
    data.set('course_id', course);
    if (title.trim()) data.set('title', title.trim());
    inFlight.current = true;
    mutation.mutate(data);
  }
  return <Modal title="Upload a course PDF" onClose={onClose} busy={mutation.isPending}>
    <form className="form-stack" onSubmit={submit}>
      <p className="form-intro">Assign the PDF to a course so learners can find it in the assistant.</p>
      <div className={'drop-zone ' + (drag ? 'drop-active' : '')} onDragOver={(event) => { event.preventDefault(); if (!inFlight.current) setDrag(true); }}
        onDragLeave={() => setDrag(false)} onDrop={(event) => { event.preventDefault(); setDrag(false); choose(event.dataTransfer.files[0]); }}>
        <span className="drop-icon"><UploadCloud size={25} /></span>
        <button type="button" className="button secondary small" onClick={() => input.current?.click()} disabled={mutation.isPending}>Choose a PDF</button>
        <span className="selected-file" role="status">{file?.name ?? 'or drag a file here'}</span><small>{limits}</small>
        <input ref={input} className="sr-only" tabIndex={-1} aria-label="PDF file" type="file" accept=".pdf,application/pdf"
          disabled={mutation.isPending} onChange={(event) => choose(event.target.files?.[0])} />
      </div>
      <div className="field"><label htmlFor="upload-course">Course</label><select id="upload-course" required value={course}
        disabled={mutation.isPending || loading || !!courseError} onChange={(event) => setCourse(event.target.value)}>
        <option value="">{loading ? 'Loading courses…' : 'Select a course'}</option>
        {courses.map((option) => <option key={option.id} value={option.id}>{option.title}</option>)}
      </select></div>
      <div className="field"><label htmlFor="upload-title">Display title <span className="muted">(optional)</span></label>
        <input id="upload-title" value={title} disabled={mutation.isPending} maxLength={180}
          onChange={(event) => setTitle(event.target.value)} placeholder="Use the PDF title by default" /></div>
      {courseError && <Notice error={courseError} retry={retryCourses} />}
      {mutation.isError && <Notice title="Upload failed" error={mutation.error} />}
      {mutation.isPending && <Loading label="Uploading PDF…" />}
      <div className="form-actions"><button type="button" className="button secondary" disabled={mutation.isPending} onClick={onClose}>Cancel</button>
        <button className="button primary" disabled={mutation.isPending || !file || !course}><UploadCloud size={17} />{mutation.isPending ? 'Uploading…' : 'Upload and index'}</button></div>
    </form>
  </Modal>;
}

function DocumentDetails({ id, uploaded, onClose, onChanged }: {
  id: number; uploaded: boolean; onClose: () => void; onChanged: (message: string) => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['document', id], queryFn: () => api.document(id),
    refetchInterval: (query) => query.state.data?.status === 'processing' ? 700 : false });
  const reindex = useMutation({ mutationFn: () => api.reindex(id), onSuccess: (document) => {
    client.setQueryData(['document', id], document);
    onChanged('Reindex started.');
    void client.invalidateQueries({ queryKey: ['document', id] });
  } });
  const remove = useMutation({ mutationFn: () => api.remove(id), onSuccess: () => {
    void client.invalidateQueries({ queryKey: ['document', id] });
    onChanged('Document removed from the active library.');
    onClose();
  } });
  const doc = query.data;
  const indexStatus = doc?.status;
  useEffect(() => {
    if (!indexStatus || indexStatus === 'processing') return;
    void client.invalidateQueries({ queryKey: ['documents'] });
    void client.invalidateQueries({ queryKey: ['overview'] });
    void client.invalidateQueries({ queryKey: ['audit'] });
  }, [client, indexStatus]);
  return <Modal title="Document details" onClose={onClose} wide busy={remove.isPending || reindex.isPending}>
    {uploaded && <Notice title="PDF uploaded">Indexing status appears below.</Notice>}
    {query.isPending && <Loading label="Loading document…" />}
    {query.isError && <Notice error={query.error} retry={() => void query.refetch()} />}
    {doc && <>
      <div className="detail-title">
        <div className="file-icon"><FileText size={21} /></div><div><h3>{doc.title}</h3><p>{doc.original_filename}</p></div>
        <span role="status"><Status value={doc.status} label={doc.status === 'processing' ? 'Indexing' : undefined} /></span>
      </div>
      <dl className="detail-grid">
        <div><dt>Course</dt><dd>{doc.course_title}</dd></div><div><dt>Pages with text</dt><dd>{doc.text_pages ?? '—'} of {doc.page_count}</dd></div>
        <div><dt>File size</dt><dd>{size(doc.size_bytes)}</dd></div><div><dt>Indexed chunks</dt><dd>{doc.chunk_count}</dd></div>
        <div><dt>Uploaded</dt><dd>{date(doc.created_at)}</dd></div><div><dt>Index revision</dt><dd>{doc.active_revision || '—'}</dd></div>
      </dl>
      {doc.status === 'processing' && <Loading label="Indexing the PDF…" />}
      {doc.error_message && <Notice title="Indexing failed" error={new Error(doc.error_message)} />}
      {(reindex.isError || remove.isError) && <Notice error={reindex.isError ? reindex.error : remove.error} />}
      {confirm ? <div className="remove-confirm" role="group" aria-label="Confirm removal">
        <div><strong>Remove this PDF from the library?</strong><p>Future questions will exclude it. Existing citations can still open its pages.</p></div>
        <button className="button secondary small" disabled={remove.isPending} onClick={() => setConfirm(false)}>Cancel</button>
        <button className="button danger small" disabled={remove.isPending} onClick={() => remove.mutate()}>{remove.isPending ? 'Removing…' : 'Confirm removal'}</button>
      </div> : <div className="detail-actions">
        {doc.status === 'indexed' && <Link className="button primary small" to={'/assistant?document=' + doc.id + '&course=' + doc.course_id}>Ask this PDF <ArrowRight size={15} /></Link>}
        {doc.status !== 'retired' && <>
          <button className="button secondary small" onClick={() => reindex.mutate()} disabled={reindex.isPending || doc.status === 'processing'}><RefreshCw size={15} /> Reindex</button>
          <button className="button secondary small danger-text" onClick={() => setConfirm(true)} disabled={reindex.isPending || doc.status === 'processing'}><Trash2 size={15} /> Remove</button>
        </>}
      </div>}
      {doc.status !== 'processing' && <PagePreview key={doc.id} documentId={doc.id} initialPage={1} pageCount={doc.page_count} />}
    </>}
  </Modal>;
}

const LIMIT = 10;
export function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const search = (params.get('q') ?? '').slice(0, 150);
  const deferredSearch = useDeferredValue(search.trim());
  const course = positiveId(params.get('course'));
  const status = params.get('status') ?? '';
  const offset = pageOffset(params, LIMIT);
  const [message, setMessage] = useState('');
  const client = useQueryClient();
  const uploading = params.get('upload') === '1';
  const uploaded = params.get('added') === '1';
  const opened = positiveId(params.get('document'));

  const courses = useQuery({ queryKey: ['courses'], queryFn: api.courses });
  const system = useQuery({ queryKey: ['system'], queryFn: api.system });
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.overview,
    refetchInterval: (query) => query.state.data?.documents.processing ? 900 : false });
  const rows = useQuery({
    queryKey: ['documents', { search: deferredSearch, course, status, offset }],
    queryFn: () => api.documents({ search: deferredSearch, course_id: course ?? undefined, status, offset, limit: LIMIT }),
    refetchInterval: (query) => query.state.data?.items.some((doc) => doc.status === 'processing') || overview.data?.documents.processing ? 900 : false,
  });
  useEffect(() => {
    if (rows.data && !rows.data.items.length && offset > 0 && offset >= rows.data.total) {
      setParams((current) => withSearch(current, { offset: Math.max(0, offset - LIMIT) || null }), { replace: true });
    }
  }, [rows.data, offset, setParams]);

  function update(changes: Record<string, string | number | null>, replace = true) {
    setParams((current) => withSearch(current, changes), { replace });
  }
  function refresh(value: string) {
    void client.invalidateQueries({ queryKey: ['documents'] });
    void client.invalidateQueries({ queryKey: ['overview'] });
    void client.invalidateQueries({ queryKey: ['audit'] });
    setMessage(value);
  }
  function openUpload() { setMessage(''); update({ upload: 1, document: null, added: null }, false); }
  const rowData = rows.data;
  const limits = system.data?.upload;
  const filtered = !!(search || course || status);
  return <>
    <Heading title="Document Library" subtitle="Upload course PDFs, check indexing, and preview source pages."
      action={<button className="button primary" onClick={openUpload}><UploadCloud size={18} /> Upload PDF</button>} />
    {!!message && !opened && <Notice>{message}</Notice>}
    <section className="panel table-panel" aria-label="Approved PDF documents">
      <div className="filter-bar">
        <label className="search"><Search size={18} /><input aria-label="Search documents" placeholder="Search documents…" value={search} maxLength={150}
          onChange={(event) => update({ q: event.target.value, offset: null })} /></label>
        <select aria-label="Filter by course" value={course ?? ''} onChange={(event) => update({ course: event.target.value, offset: null })}>
          <option value="">All courses</option>{courses.data?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>
        <select aria-label="Filter by indexing status" value={status} onChange={(event) => update({ status: event.target.value, offset: null })}>
          <option value="">All statuses</option><option value="indexed">Indexed</option><option value="processing">Indexing</option><option value="error">Indexing error</option>
        </select>
        {filtered && <button className="button secondary small" onClick={() => update({ q: null, course: null, status: null, offset: null })}>Clear filters</button>}
      </div>
      {rows.isPending && <Loading label="Loading documents…" />}
      {rows.isError && <Notice title="Documents unavailable" error={rows.error} retry={() => void rows.refetch()} />}
      {courses.isError && <Notice title="Courses unavailable" error={courses.error} retry={() => void courses.refetch()} />}
      {rowData && (rowData.items.length ? <div className="table-scroll"><table role="table" aria-label="Course PDFs">
        <thead role="rowgroup"><tr role="row"><th scope="col">Document</th><th scope="col">Course</th><th scope="col">Status</th><th scope="col">Pages / chunks</th><th scope="col">Uploaded</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
        <tbody role="rowgroup">{rowData.items.map((doc) => <tr role="row" key={doc.id}>
          <Cell className="primary-cell"><div className="table-document"><span className="file-icon"><FileText size={20} /></span><div><strong>{doc.title}</strong><small>{doc.original_filename} · {size(doc.size_bytes)}</small></div></div></Cell>
          <Cell label="Course"><span className="course-code" title={doc.course_title}>{doc.course_code}</span></Cell>
          <Cell label="Status"><Status value={doc.status} label={doc.status === 'processing' ? 'Indexing' : undefined} /></Cell>
          <Cell label="Pages / chunks">{number(doc.page_count)} / {number(doc.chunk_count)}</Cell>
          <Cell label="Uploaded" className="time-cell">{date(doc.created_at)}</Cell>
          <Cell className="action-cell"><button className="button secondary small" onClick={() => update({ document: doc.id, upload: null, added: null }, false)} aria-label={'View details for ' + doc.title}>View details <ArrowRight size={16} /></button></Cell>
        </tr>)}</tbody>
      </table></div> : <Empty title={filtered ? 'No matching documents' : 'No PDFs in the library'}
        text={filtered ? 'Try a different search or clear the filters.' : 'Upload a searchable course PDF to build the library.'}
        action={filtered ? undefined : <button className="button primary small" onClick={openUpload}>Upload your first PDF <ArrowRight size={16} /></button>} />)}
      {rowData && <Pager offset={offset} total={rowData.total} limit={LIMIT} onChange={(next) => update({ offset: next || null })} />}
    </section>
    {uploading && <UploadForm courses={courses.data ?? []} loading={courses.isPending} courseError={courses.error} retryCourses={() => void courses.refetch()}
      limits={limits ? 'PDF · up to ' + limits.max_mb + ' MB and ' + limits.max_pages + ' pages' : 'Searchable PDF'}
      onClose={() => update({ upload: null })} onFinished={(doc) => {
        client.setQueryData(['document', doc.id], doc);
        update({ upload: null, document: doc.id, added: 1 });
        refresh('PDF uploaded.');
      }} />}
    {!uploading && opened && <DocumentDetails key={opened} id={opened} uploaded={uploaded}
      onClose={() => update({ document: null, added: null })} onChanged={refresh} />}
  </>;
}

