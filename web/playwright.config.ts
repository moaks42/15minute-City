import { defineConfig, devices } from '@playwright/test'

// Smoke test (README §11 C DoD). Runs against BASE_URL (staging) or a local
// dev server in fixtures mode.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: process.env.BASE_URL ?? 'http://localhost:5174', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: process.env.BASE_URL
    ? undefined
    : { command: 'VITE_USE_FIXTURES=1 npx vite --port 5174 --strictPort', port: 5174, reuseExistingServer: true },
})
