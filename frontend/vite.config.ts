import react from '@vitejs/plugin-react'
import { defineConfig, type ProxyOptions } from 'vite'

const backendProxy: ProxyOptions = {
  target: 'http://localhost:8000',
  changeOrigin: true,
}

const apiProxyPaths = [
  '/api',
  '/auth',
  '/user',
  '/register',
  '/sts-token',
  '/create_session',
  '/quick_parse',
  '/chat_on_docs',
  '/upload_files',
  '/get_files',
  '/delete_file',
  '/get_messages',
  '/get_sessions',
  '/get_parsed_content',
  '/sessions',
  '/rag',
]

const proxy = Object.fromEntries(
  apiProxyPaths.map((path) => [path, backendProxy]),
) as Record<string, ProxyOptions>

proxy['/login'] = {
  ...backendProxy,
  // GET /login is a React route; POST /login is the auth API.
  bypass(req) {
    const acceptsHtml = req.headers.accept?.includes('text/html')
    if ((req.method === 'GET' || req.method === 'HEAD') && acceptsHtml) {
      return '/index.html'
    }
  },
}

// https://vite.dev/config/
export default defineConfig(() => {
  return {
    server: {
      port: 5181,
      host: '0.0.0.0',
      proxy,
    },
    resolve: {
      alias: [
        {
          find: /^@\//,
          replacement: '/src/',
        },
      ],
    },

    plugins: [react()],
  }
})
