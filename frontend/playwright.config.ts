import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = fileURLToPath(new URL('.', import.meta.url));
const root = path.resolve(frontend, '..');
const python = process.env.EDUEVIDENCE_TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const mode = process.env.EDUEVIDENCE_UI_MODE ?? 'fixture';
if (!['fixture', 'live', 'unconfigured', 'empty', 'database-error'].includes(mode)) throw new Error('Unknown UI test mode.');
const appPort = Number(process.env.EDUEVIDENCE_TEST_WEB_PORT ?? 5183);
const apiPort = Number(process.env.EDUEVIDENCE_TEST_API_PORT ?? 8018);
const browserURL = 'http://127.0.0.1:' + appPort;
const apiURL = 'http://127.0.0.1:' + apiPort;

export default defineConfig({
  testDir: './e2e',
  outputDir: 'test-results/' + mode + (process.env.EDUEVIDENCE_TRACE_DB_DIR ? '-trace' : ''),
  fullyParallel: false,
  workers: 1,
  timeout: 35000,
  reporter: 'list',
  use: {
    baseURL: browserURL,
    channel: process.env.EDUEVIDENCE_BROWSER_CHANNEL,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    { command: '"' + python + '" -m backend.tests.browser_backend --mode ' + mode + ' --port ' + apiPort, cwd: root, url: apiURL + '/health', timeout: 60000 },
    { command: npm + ' run dev -- --port ' + appPort, cwd: frontend, url: browserURL, timeout: 60000,
      env: { EDUEVIDENCE_API_ORIGIN: apiURL } },
  ],
});

