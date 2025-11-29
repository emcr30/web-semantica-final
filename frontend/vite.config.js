import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // proxy API calls to the Flask backend
      '/sparql': 'http://127.0.0.1:5000',
      '/ingest': 'http://127.0.0.1:5000',
      '/search': 'http://127.0.0.1:5000',
      '/reason': 'http://127.0.0.1:5000',
      '/detect_contradictions': 'http://127.0.0.1:5000',
      '/ingest_csv': 'http://127.0.0.1:5000',
      '/entity': 'http://127.0.0.1:5000',
      '/fetch_url_debug': 'http://127.0.0.1:5000'
    }
  }
})
