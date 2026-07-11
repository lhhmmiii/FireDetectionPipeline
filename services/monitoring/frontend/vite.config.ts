import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Build output goes to ../static so FastAPI can serve it.
// Base is /static/ to match the FastAPI StaticFiles mount point.
export default defineConfig({
  plugins: [react()],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    port: 3001,
    proxy: {
      '/ws': {
        target: 'ws://localhost:8090',
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8090',
      },
    },
  },
});
