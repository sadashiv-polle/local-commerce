import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: '/assets/local_commerce/frontend/',
  plugins: [vue()],
  build: {
    outDir: '../local_commerce/public/frontend', emptyOutDir: true, manifest: true,
    rollupOptions: { input: fileURLToPath(new URL('./src/main.js', import.meta.url)) },
  },
})
