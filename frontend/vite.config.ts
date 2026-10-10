import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

// Версия сборки в углу интерфейса: номер из package.json и коммит.
// В Docker коммит приходит аргументом APP_COMMIT (в образе нет .git).
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string }
function commit(): string {
  if (process.env.APP_COMMIT) return process.env.APP_COMMIT.slice(0, 7)
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return 'dev'
  }
}

// Прокси на бэкенд для dev/preview (в проде этим занимается nginx)
const backend = 'http://localhost:8000'
const proxy = {
  '/api': { target: backend, changeOrigin: true },
  '/health': { target: backend, changeOrigin: true },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __APP_COMMIT__: JSON.stringify(commit()),
    __APP_BUILT_AT__: JSON.stringify(new Date().toISOString()),
  },
  server: { proxy },
  preview: { proxy },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    isolate: true,
    pool: 'forks',
  },
})
