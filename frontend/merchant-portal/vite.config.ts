import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8451,
    host: '0.0.0.0',
    allowedHosts: ['app.abhinava.xyz'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8453',  // Merchant backend
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 8451,
    host: '0.0.0.0'
  }
})
