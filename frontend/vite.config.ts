import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Прокси на бэкенд для dev/preview (в проде этим занимается nginx)
const backend = 'http://localhost:8000'
const proxy = {
  '/api': { target: backend, changeOrigin: true },
  '/health': { target: backend, changeOrigin: true },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
