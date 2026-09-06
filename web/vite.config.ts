import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { pureStyles } from './styles-plugin';

export default defineConfig({
  css: { postcss: { plugins: [] } },
  plugins: [pureStyles(), react()],
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  build: { outDir: 'dist/client', cssMinify: false },
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    watch: { useFsEvents: false, usePolling: true },
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
});
