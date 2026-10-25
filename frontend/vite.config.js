import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

const UN_DIA = 60 * 60 * 24;

export default defineConfig(({ mode }) => {
  // Destino del proxy de desarrollo: Nginx enruta /api/v1/tutor (tutor) y /api/v2 (catálogo, lecciones y trazos).
  const env = loadEnv(mode, process.cwd(), '');
  const gatewayUrl = env.VITE_GATEWAY_URL || 'http://localhost:80';

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'],
        manifest: {
          name: 'HanziMentor',
          short_name: 'HanziMentor',
          description: 'Aprendé mandarín trazo a trazo con un tutor adaptativo.',
          lang: 'es',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#eee4cd',
          theme_color: '#eee4cd',
          icons: [
            { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,png,svg,woff2}'],
          // Noto Serif SC son ~100 archivos por rangos unicode (~4 MB): no se
          // precargan; se guardan solo los que el usuario llega a ver (regla abajo).
          globIgnores: ['**/noto-serif-sc-*'],
          navigateFallback: '/index.html',
          // La API comparte origen con la app: sus rutas nunca deben caer en el index.html.
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              // Imágenes de fondo de la maqueta (dominio externo). Se piden desde
              // CSS sin CORS, por eso se aceptan respuestas opacas (status 0).
              urlPattern: /^https:\/\/hebbkx1anhila5yf\.public\.blob\.vercel-storage\.com\//,
              handler: 'CacheFirst',
              options: {
                cacheName: 'hanzi-imagenes-externas',
                expiration: { maxEntries: 10, maxAgeSeconds: 30 * UN_DIA },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // Tramos de Noto Serif SC excluidos del precache.
              urlPattern: /\/assets\/noto-serif-sc-[^/]+\.woff2?$/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'hanzi-fuentes-noto',
                expiration: { maxEntries: 120, maxAgeSeconds: 365 * UN_DIA },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
        },
      }),
    ],
    server: {
      host: true,
      proxy: {
        '/api': { target: gatewayUrl, changeOrigin: true },
      },
    },
  };
});
