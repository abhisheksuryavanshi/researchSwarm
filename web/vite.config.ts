/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Same-origin in dev → no CORS. Backend must listen on this target (see setup.sh / uvicorn).
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true, configure: (proxy) => { proxy.on('proxyRes', (proxyRes) => { if (proxyRes.headers['content-type']?.includes('text/event-stream')) { proxyRes.headers['cache-control'] = 'no-cache'; proxyRes.headers['x-accel-buffering'] = 'no'; } }); } },
      '/tools': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setup.ts',
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
  },
})
