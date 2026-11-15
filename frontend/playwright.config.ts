import { defineConfig } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT || 8001);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 5174);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    acceptDownloads: true,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'python e2e/e2e_backend.py',
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ],
});
