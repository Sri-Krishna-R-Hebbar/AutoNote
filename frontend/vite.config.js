import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // During `npm run dev`, forward API calls to the local Flask server
      // so the React dev server and Flask can run side by side.
      '/api': 'http://localhost:5000',
    },
  },
})
