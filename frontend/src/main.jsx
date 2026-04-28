import React from 'react';
import { createRoot } from 'react-dom/client';
import './app.css';  // contient @import de leaflet.css
import App from './App.jsx';

const container = document.getElementById('react-map-root');
if (container) {
  createRoot(container).render(<App />);
}
