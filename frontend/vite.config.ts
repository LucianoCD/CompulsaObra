import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 5174);
const backendPort = Number(process.env.E2E_BACKEND_PORT || 8001);

export default defineConfig({
  plugins: [react()],
  resolve: {
    preserveSymlinks: true,
  },
  server: {
    port: frontendPort,
    fs: {
      strict: false,
    },
    proxy: {
      '/api/v1': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: frontendPort,
    proxy: {
      '/api/v1': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
})
