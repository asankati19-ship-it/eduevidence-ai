import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const apiOrigin = process.env.EDUEVIDENCE_API_ORIGIN ?? 'http://127.0.0.1:8000';
const proxy = {
  '/api': {
    target: apiOrigin,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { __API_DOCS_URL__: JSON.stringify(new URL('/docs', apiOrigin).href) },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
});

