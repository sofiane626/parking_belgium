import React from 'react';
import { createRoot } from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './app.css';
import App from './App.jsx';

const container = document.getElementById('react-map-root');
if (container) {
  createRoot(container).render(<App />);
}
