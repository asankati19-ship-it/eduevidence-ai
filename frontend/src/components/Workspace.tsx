import { useQuery } from '@tanstack/react-query';
import { Activity, BookOpenCheck, ChevronRight, ClipboardList, Files, LayoutDashboard, Menu, MessageSquareText, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { Modal } from './Primitives';

const WORKSPACE = [
  { route: '/', title: 'Overview', icon: LayoutDashboard },
  { route: '/documents', title: 'Document Library', icon: Files },
  { route: '/assistant', title: 'Knowledge Assistant', icon: MessageSquareText },
  { route: '/history', title: 'Question History', icon: ClipboardList },
  { route: '/analytics', title: 'Feedback & Analytics', icon: Activity },
];
const SYSTEM = [
  { route: '/audit', title: 'Audit Logs', icon: ShieldCheck },
  { route: '/settings', title: 'System Health', icon: SlidersHorizontal },
];

const TABLE_FILTERS: Record<string, string[]> = {
  '/documents': ['q', 'course', 'status', 'offset'],
  '/history': ['q', 'status', 'offset'],
  '/audit': ['event', 'request', 'offset'],
};

function filteredDestination(pathname: string, search: string) {
  const selected = new URLSearchParams(search);
  const filters = new URLSearchParams();
  for (const field of TABLE_FILTERS[pathname] ?? []) {
    const value = selected.get(field);
    if (value) filters.set(field, value);
  }
  return filters.size ? pathname + '?' + filters.toString() : pathname;
}

function Navigation({ destination, onNavigate }: { destination: (route: string) => string; onNavigate?: () => void }) {
  const renderLinks = (items: typeof WORKSPACE) => items.map(({ route, title, icon: Icon }) => (
    <NavLink key={route} to={destination(route)} end={route === '/'} onClick={onNavigate}>
      <Icon size={19} strokeWidth={1.7} aria-hidden="true" /><span>{title}</span>
    </NavLink>
  ));
  return <nav className="workspace-nav" aria-label="Workspace navigation">
    <p>Workspace</p>{renderLinks(WORKSPACE)}
    <p className="system-nav">Administration</p>{renderLinks(SYSTEM)}
  </nav>;
}

export function Workspace() {
  const [open, setOpen] = useState(false);
  const main = useRef<HTMLElement>(null);
  const { pathname, search } = useLocation();
  const rememberedPages = useRef(new Map<string, string>());
  const lastPath = useRef(pathname);
  const active = [...WORKSPACE, ...SYSTEM].find((item) => item.route === pathname);
  const system = useQuery({ queryKey: ['system'], queryFn: api.system });
  const learner = system.data?.learner.display_name;
  const initials = learner?.split(/\s+/).slice(0, 2).map((name) => name[0]).join('').toUpperCase();
  const destination = (route: string) => route === pathname
    ? filteredDestination(route, search) : rememberedPages.current.get(route) ?? route;

  useEffect(() => {
    if (TABLE_FILTERS[pathname]) rememberedPages.current.set(pathname, filteredDestination(pathname, search));
  }, [pathname, search]);

  useEffect(() => {
    if (lastPath.current === pathname) return;
    lastPath.current = pathname;
    main.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const desktop = window.matchMedia('(min-width: 961px)');
    const closeOnResize = (event: MediaQueryListEvent) => { if (event.matches) setOpen(false); };
    desktop.addEventListener('change', closeOnResize);
    return () => desktop.removeEventListener('change', closeOnResize);
  }, [open]);

  return <div className="workspace">
    <a href="#main" className="skip-link">Skip to content</a>
    <aside className="sidebar">
      <NavLink className="brand" to="/">
        <span className="brand-icon"><BookOpenCheck size={24} strokeWidth={1.7} aria-hidden="true" /></span>
        <span><strong>EduEvidence <em>AI</em></strong><small>Course knowledge workspace</small></span>
      </NavLink>
      <Navigation destination={destination} />
      {learner && <div className="sidebar-foot"><span className="avatar" aria-hidden="true">{initials}</span><span><strong>{learner}</strong><small>Local workspace</small></span></div>}
    </aside>
    {open && <Modal title="Workspace navigation" onClose={() => setOpen(false)} drawer>
      <Navigation destination={destination} onNavigate={() => setOpen(false)} />
    </Modal>}
    <div className="application">
      <header className="topbar">
        <button className="icon-button mobile-toggle" onClick={() => setOpen(true)} aria-label="Open navigation"
          aria-haspopup="dialog" aria-expanded={open}><Menu size={22} aria-hidden="true" /></button>
        <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{active?.title ?? 'Page not found'}</strong></div>
        {system.data?.mode === 'local_synthetic' && <span className="local-marker"><span aria-hidden="true" /> Synthetic LMS</span>}
      </header>
      <main id="main" className="main" tabIndex={-1} ref={main}><Outlet /></main>
    </div>
  </div>;
}

