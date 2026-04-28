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
      input: {
        // Bundle séparé pour la carte (/map/) — charge react-leaflet (lourd)
        map: resolve(__dirname, 'src/main.jsx'),
        // Bundle séparé pour le wizard de création de carte
        wizard: resolve(__dirname, 'src/wizard.jsx'),
        // Bundle pour la datatable d'audit côté back-office
        audit: resolve(__dirname, 'src/audit.jsx'),
      },
      output: {
        // Nom prévisible : <entry>-bundle.js → map-bundle.js, wizard-bundle.js
        entryFileNames: '[name]-bundle.js',
        chunkFileNames: '[name]-chunk.js',
        assetFileNames: ({ name }) => {
          // CSS produit par chaque entry → <entry>-bundle.css
          if (name && name.endsWith('.css')) return '[name]-bundle.css';
          return '[name][extname]';
        },
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
