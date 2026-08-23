import React from 'react';
import { createRoot } from 'react-dom/client';
import './app.css';  // contient @import de leaflet.css
import App from './App.jsx';

const container = document.getElementById('react-map-root');
if (container) {
  const communesDataEl = document.getElementById('pb-communes-data');
  const allCommunes = communesDataEl ? JSON.parse(communesDataEl.textContent) : [];
  createRoot(container).render(<App allCommunes={allCommunes} />);
}
