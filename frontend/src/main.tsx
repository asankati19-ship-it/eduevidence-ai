import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Workspace } from './components/Workspace';
import { Empty } from './components/Primitives';
import { OverviewPage, AnalyticsPage } from './pages/Overview';
import { LibraryPage } from './pages/Library';
import { AssistantPage } from './pages/Assistant';
import { HistoryPage, AuditPage, SettingsPage } from './pages/Records';
import './styles.css';

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 4000, retry: false, refetchOnWindowFocus: true } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode><QueryClientProvider client={client}><BrowserRouter><Routes>
    <Route element={<Workspace />}>
      <Route index element={<OverviewPage />} />
      <Route path="documents" element={<LibraryPage />} />
      <Route path="assistant" element={<AssistantPage />} />
      <Route path="history" element={<HistoryPage />} />
      <Route path="analytics" element={<AnalyticsPage />} />
      <Route path="audit" element={<AuditPage />} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="*" element={<Empty title="Page not found" text="Return to your workspace overview." action={<Link className="button primary" to="/">Overview</Link>} />} />
    </Route>
  </Routes></BrowserRouter></QueryClientProvider></StrictMode>,
);

