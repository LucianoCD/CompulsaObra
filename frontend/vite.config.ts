import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    fs: {
      strict: false,
    },
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5174,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})

