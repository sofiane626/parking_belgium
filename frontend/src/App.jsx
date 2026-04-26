import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, LayersControl } from 'react-leaflet';

const PALETTE = [
  '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16',
  '#a855f7', '#eab308', '#0ea5e9', '#22c55e', '#d946ef',
  '#f43f5e', '#6366f1', '#65a30d', '#dc2626', '#475569',
];

function colorForNiscode(niscode, paletteIndex) {
  if (!niscode) return '#94a3b8';
  return PALETTE[paletteIndex % PALETTE.length];
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [communeFilter, setCommuneFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [selectedZone, setSelectedZone] = useState(null);

  useEffect(() => {
    fetch('/map/polygons.geojson')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  // Index commune → couleur stable (premier-arrivé, premier-servi)
  const communeIndex = useMemo(() => {
    if (!data) return new Map();
    const seen = new Map();
    data.features.forEach((f) => {
      const nis = f.properties.niscode;
      if (nis && !seen.has(nis)) {
        seen.set(nis, {
          name: f.properties.commune || nis,
          color: colorForNiscode(nis, seen.size),
          count: 1,
        });
      } else if (nis) {
        seen.get(nis).count += 1;
      }
    });
    return seen;
  }, [data]);

  // Features filtrées (commune + recherche)
  const filteredFeatures = useMemo(() => {
    if (!data) return [];
    const q = searchText.trim().toLowerCase();
    return data.features.filter((f) => {
      const p = f.properties;
      if (communeFilter && p.niscode !== communeFilter) return false;
      if (q) {
        const hay = [p.zonecode, p.name_fr, p.name_nl, p.name_en, p.commune]
          .filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, communeFilter, searchText]);

  // Stats live
  const stats = useMemo(() => {
    const total = data?.features?.length || 0;
    const shown = filteredFeatures.length;
    const totalArea = filteredFeatures.reduce(
      (acc, f) => acc + (f.properties.area || 0), 0,
    );
    return {
      total,
      shown,
      communes: communeIndex.size,
      areaKm2: (totalArea / 1_000_000).toFixed(2),
    };
  }, [data, filteredFeatures, communeIndex]);

  if (error) {
    return <div className="pb-loading">Erreur de chargement : {error}</div>;
  }
  if (!data) {
    return <div className="pb-loading">Chargement de la carte…</div>;
  }

  // GeoJSON nécessite une key qui change quand on filtre, sinon Leaflet cache
  const geoKey = `${communeFilter}|${searchText}`;

  return (
    <div className="pb-map-shell">
      <aside className="pb-sidebar">

        <section>
          <p className="pb-section-title">Filtres</p>
          <select
            className="pb-select"
            value={communeFilter}
            onChange={(e) => setCommuneFilter(e.target.value)}
            style={{ marginBottom: 8 }}
          >
            <option value="">Toutes les communes</option>
            {[...communeIndex.entries()]
              .sort((a, b) => a[1].name.localeCompare(b[1].name))
              .map(([nis, info]) => (
                <option key={nis} value={nis}>{info.name}</option>
              ))}
          </select>
          <input
            className="pb-input"
            type="search"
            placeholder="Zonecode ou nom…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          {(communeFilter || searchText) && (
            <button
              type="button"
              className="pb-btn pb-btn-ghost"
              onClick={() => { setCommuneFilter(''); setSearchText(''); }}
              style={{ marginTop: 8, width: '100%' }}
            >
              ↻ Réinitialiser
            </button>
          )}
        </section>

        <section>
          <p className="pb-section-title">Statistiques</p>
          <div className="pb-stats">
            <div className="pb-stat-card">
              <div className="pb-stat-value">{stats.shown}</div>
              <div className="pb-stat-label">Zones affichées</div>
            </div>
            <div className="pb-stat-card">
              <div className="pb-stat-value">{stats.total}</div>
              <div className="pb-stat-label">Total Région</div>
            </div>
            <div className="pb-stat-card">
              <div className="pb-stat-value">{stats.communes}</div>
              <div className="pb-stat-label">Communes</div>
            </div>
            <div className="pb-stat-card">
              <div className="pb-stat-value">{stats.areaKm2}</div>
              <div className="pb-stat-label">km² affichés</div>
            </div>
          </div>
        </section>

        {selectedZone && (
          <section>
            <p className="pb-section-title">Zone sélectionnée</p>
            <dl className="pb-zone-detail">
              <dt>Zonecode</dt>
              <dd><code>{selectedZone.zonecode || '—'}</code></dd>
              <dt>Commune</dt>
              <dd>{selectedZone.commune || '—'}</dd>
              <dt>Type</dt>
              <dd>{selectedZone.type || '—'}</dd>
              <dt>Nom (fr)</dt>
              <dd>{selectedZone.name_fr || '—'}</dd>
              <dt>Nom (nl)</dt>
              <dd>{selectedZone.name_nl || '—'}</dd>
              {selectedZone.area && (
                <>
                  <dt>Aire</dt>
                  <dd>{(selectedZone.area / 10000).toFixed(2)} ha</dd>
                </>
              )}
            </dl>
          </section>
        )}

        <section>
          <p className="pb-section-title">Communes ({communeIndex.size})</p>
          <div className="pb-commune-list">
            {[...communeIndex.entries()]
              .sort((a, b) => a[1].name.localeCompare(b[1].name))
              .map(([nis, info]) => (
                <div
                  key={nis}
                  className="pb-commune-row"
                  onClick={() => setCommuneFilter(communeFilter === nis ? '' : nis)}
                  style={{
                    cursor: 'pointer',
                    background: communeFilter === nis ? '#e8f1fb' : 'transparent',
                  }}
                >
                  <span>
                    <span className="pb-swatch" style={{ background: info.color }}></span>
                    {info.name}
                  </span>
                  <span className="pb-commune-count">{info.count}</span>
                </div>
              ))}
          </div>
        </section>
      </aside>

      <div className="pb-map-container">
        <MapContainer center={[50.847, 4.357]} zoom={12} scrollWheelZoom={true}>
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="Voyager">
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                subdomains={['a', 'b', 'c', 'd']}
                maxZoom={19}
                attribution="&copy; CARTO &copy; OpenStreetMap"
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Clair">
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                subdomains={['a', 'b', 'c', 'd']}
                maxZoom={19}
                attribution="&copy; CARTO &copy; OpenStreetMap"
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Sombre">
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                subdomains={['a', 'b', 'c', 'd']}
                maxZoom={19}
                attribution="&copy; CARTO &copy; OpenStreetMap"
              />
            </LayersControl.BaseLayer>
          </LayersControl>

          <GeoJSON
            key={geoKey}
            data={{ type: 'FeatureCollection', features: filteredFeatures }}
            style={(feature) => {
              const info = communeIndex.get(feature.properties.niscode);
              const color = info?.color || '#94a3b8';
              return { color, weight: 1, fillColor: color, fillOpacity: 0.32 };
            }}
            onEachFeature={(feature, layer) => {
              const p = feature.properties;
              const label = p.zonecode + (p.name_fr ? ` — ${p.name_fr}` : '');
              layer.bindTooltip(label, { sticky: true });
              layer.on({
                click: () => setSelectedZone(p),
                mouseover: () => layer.setStyle({ weight: 3, fillOpacity: 0.5 }),
                mouseout: () => {
                  const info = communeIndex.get(p.niscode);
                  const color = info?.color || '#94a3b8';
                  layer.setStyle({ color, weight: 1, fillColor: color, fillOpacity: 0.32 });
                },
              });
            }}
          />
        </MapContainer>
      </div>
    </div>
  );
}
