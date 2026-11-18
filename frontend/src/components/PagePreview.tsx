import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, ExternalLink, FileImage } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Loading, Notice } from './Primitives';

export function PagePreview({ documentId, initialPage, pageCount, locked = false }: {
  documentId: number; initialPage: number; pageCount: number; locked?: boolean;
}) {
  const [page, setPage] = useState(initialPage);
  const [image, setImage] = useState<{ blob: Blob; url: string }>();
  const query = useQuery({
    queryKey: ['pdf-page', documentId, page],
    queryFn: ({ signal }) => api.pagePreview(documentId, page, signal),
    gcTime: 0,
  });
  const blob = query.data;
  useEffect(() => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    setImage({ blob, url });
    return () => URL.revokeObjectURL(url);
  }, [blob]);
  return <div className="page-preview">
    <div className="preview-toolbar">
      <FileImage size={17} aria-hidden="true" /><strong>PDF preview</strong>
      <span>Page {page} of {pageCount}</span>
      {!locked && <div className="preview-actions">
        <button className="icon-button" aria-label="Previous PDF page" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={18} /></button>
        <button className="icon-button" aria-label="Next PDF page" disabled={page >= pageCount} onClick={() => setPage(page + 1)}><ChevronRight size={18} /></button>
      </div>}
      {blob && <a className="icon-button" href={api.page(documentId, page)} target="_blank" rel="noreferrer"
        aria-label={'Open PDF page ' + page + ' in a new tab'} title="Open full page"><ExternalLink size={16} /></a>}
    </div>
    <div className="preview-stage" role="region" aria-label={'PDF page ' + page + ' preview'} tabIndex={0}>
      {query.isError ? <Notice error={query.error} retry={() => void query.refetch()} />
        : image && image.blob === blob ? <img src={image.url} alt={'PDF page ' + page} />
          : <Loading label="Rendering PDF page…" />}
    </div>
  </div>;
}

