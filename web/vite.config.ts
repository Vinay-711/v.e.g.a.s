import { defineConfig } from 'vite'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  server: {
    port: 5180,
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        agents: resolve(__dirname, 'agents.html'),
        memory: resolve(__dirname, 'memory.html'),
        control: resolve(__dirname, 'control.html'),
        browser: resolve(__dirname, 'browser.html'),
        terminal: resolve(__dirname, 'terminal.html'),
        automation: resolve(__dirname, 'automation.html'),
        settings: resolve(__dirname, 'settings.html'),
        planning: resolve(__dirname, 'planning.html'),
        files: resolve(__dirname, 'files.html'),
      }
    }
  }
})
