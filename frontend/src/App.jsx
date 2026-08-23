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

export default function App({ allCommunes = [] }) {
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

  // Nombre de zones par commune, à partir des données réellement importées.
  const zoneCountByNis = useMemo(() => {
    const counts = new Map();
    if (!data) return counts;
    data.features.forEach((f) => {
      const nis = f.properties.niscode;
      if (!nis) return;
      counts.set(nis, (counts.get(nis) || 0) + 1);
    });
    return counts;
  }, [data]);

  // Liste des 19 communes (couleur stable par ordre alphabétique, qu'il y ait
  // ou non des zones importées) — évite de masquer silencieusement les
  // communes sans données GIS pendant que d'autres pages du site annoncent
  // une couverture des 19 communes.
  const communeRows = useMemo(() => {
    return allCommunes
      .slice()
      .sort((a, b) => a.name_fr.localeCompare(b.name_fr))
      .map((c, idx) => ({
        niscode: c.niscode,
        name: c.name_fr,
        color: colorForNiscode(c.niscode, idx),
        count: zoneCountByNis.get(c.niscode) || 0,
        hasData: zoneCountByNis.has(c.niscode),
      }));
  }, [allCommunes, zoneCountByNis]);

  const colorByNis = useMemo(
    () => new Map(communeRows.map((r) => [r.niscode, r.color])),
    [communeRows],
  );
  const communesWithData = useMemo(
    () => communeRows.filter((r) => r.hasData).length,
    [communeRows],
  );

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
      communesWithData,
      communesTotal: allCommunes.length,
      areaKm2: (totalArea / 1_000_000).toFixed(2),
    };
  }, [data, filteredFeatures, communesWithData, allCommunes]);

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
            {communeRows.map((r) => (
              <option key={r.niscode} value={r.niscode}>
                {r.name}{!r.hasData ? ' (aucune donnée)' : ''}
              </option>
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
              <div className="pb-stat-value">{stats.communesWithData}/{stats.communesTotal}</div>
              <div className="pb-stat-label">Communes avec données</div>
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
          <p className="pb-section-title">
            Communes ({communesWithData}/{allCommunes.length} avec données)
          </p>
          <div className="pb-commune-list">
            {communeRows.map((r) => (
              <div
                key={r.niscode}
                className="pb-commune-row"
                onClick={() => r.hasData && setCommuneFilter(communeFilter === r.niscode ? '' : r.niscode)}
                title={r.hasData ? undefined : 'Import GIS pas encore réalisé pour cette commune'}
                style={{
                  cursor: r.hasData ? 'pointer' : 'default',
                  opacity: r.hasData ? 1 : 0.45,
                  background: communeFilter === r.niscode ? '#e8f1fb' : 'transparent',
                }}
              >
                <span>
                  <span className="pb-swatch" style={{ background: r.color }}></span>
                  {r.name}
                </span>
                <span className="pb-commune-count">{r.hasData ? r.count : '—'}</span>
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
              const color = colorByNis.get(feature.properties.niscode) || '#94a3b8';
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
                  const color = colorByNis.get(p.niscode) || '#94a3b8';
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
