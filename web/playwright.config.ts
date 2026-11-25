import { defineConfig } from '@playwright/test'

// Runs against the local development stack with fake providers: no outside call is made.
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:5173', trace: 'retain-on-failure' },
  webServer: {
    command: 'make -C .. dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 180_000,
    env: { ATLAS_PROVIDERS: 'fake' },
  },
})
