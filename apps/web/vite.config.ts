import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET;

// Базовый URL API задаётся переменной окружения VITE_API_BASE_URL.
// Сценарий моков — VITE_MSW_SCENARIO; при пустом значении моки выключены,
// и приложение работает против реального backend без изменения кода (принцип III).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@contracts': fileURLToPath(new URL('../../contracts/review-platform/v1/examples/http', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: apiProxyTarget
      ? {
          '/api': {
            target: apiProxyTarget,
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api/u, ''),
          },
        }
      : undefined,
  },
});
