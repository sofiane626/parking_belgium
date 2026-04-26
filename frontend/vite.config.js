import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// Build vers static/frontend/ pour que Django (whitenoise + collectstatic) le serve.
// On force des noms de fichiers stables (pas de hash) pour que le template
// Django puisse référencer le bundle sans logique de manifest.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, '../static/frontend'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'src/main.jsx'),
      output: {
        entryFileNames: 'map-bundle.js',
        chunkFileNames: 'map-chunk.[name].js',
        assetFileNames: 'map-bundle.[ext]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // En dev, on proxy l'API GeoJSON vers Django :8000 pour éviter CORS.
      '/map/polygons.geojson': 'http://localhost:8000',
    },
  },
});
