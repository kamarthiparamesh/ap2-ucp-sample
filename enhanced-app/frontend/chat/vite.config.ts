import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8450,
    host: '0.0.0.0',
    allowedHosts: ['chat.abhinava.xyz'], 
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8452',
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 8450,
    host: '0.0.0.0'
  }
})
