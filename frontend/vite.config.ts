import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop on Windows does not forward inotify events into the
    // container, so watch via polling or hot-reload never fires.
    watch: {
      usePolling: true,
      interval: 200,
      ignored: ['**/dist/**'],
    },
    hmr: {
      clientPort: Number(process.env.VITE_CLIENT_PORT || 5173),
    },
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
  },
});
