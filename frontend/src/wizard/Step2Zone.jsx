import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';

export default function Step2Zone({ eligibility, polygonsGeojsonUrl, onNext, onPrev }) {
  const [geojson, setGeojson] = useState(null);

  // On filtre côté client le polygone correspondant pour ne dessiner que celui-là
  useEffect(() => {
    fetch(polygonsGeojsonUrl)
      .then((r) => r.json())
      .then((data) => {
        const codes = new Set([
          eligibility.main_zone, ...(eligibility.additional_zones || []),
        ].filter(Boolean));
        const features = data.features.filter((f) => codes.has(f.properties.zonecode));
        setGeojson({ type: 'FeatureCollection', features });
      })
      .catch(() => setGeojson({ type: 'FeatureCollection', features: [] }));
  }, [polygonsGeojsonUrl, eligibility]);

  const totalZones = (eligibility.main_zone ? 1 : 0) + eligibility.additional_zones.length;

  return (
    <>
      <h1 className="pbw-title">Zone d'attribution</h1>
      <p className="pbw-subtitle">
        Zones autorisées pour cette carte selon l'adresse de référence.
      </p>

      {eligibility.requires_manual_review && (
        <div className="pbw-notice pbw-notice-warn">
          Cette demande nécessitera une validation manuelle par un agent.
        </div>
      )}

      <div className="pbw-card is-highlight">
        <p className="pbw-card-label">Zone principale</p>
        <p className="pbw-card-value">
          <span className="pbw-zone-tag">{eligibility.main_zone || '—'}</span>
        </p>
        {eligibility.additional_zones.length > 0 && (
          <>
            <p className="pbw-card-label" style={{ marginTop: 12 }}>
              Zones supplémentaires ({eligibility.additional_zones.length})
            </p>
            <div>
              {eligibility.additional_zones.map((z) => (
                <span key={z} className="pbw-zone-tag">{z}</span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="pbw-mini-map">
        <MapContainer center={[50.847, 4.357]} zoom={13} scrollWheelZoom={false}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            subdomains={['a','b','c','d']}
            maxZoom={19}
            attribution="&copy; CARTO &copy; OpenStreetMap"
          />
          {geojson && geojson.features.length > 0 && (
            <GeoJSON
              key={geojson.features.map((f) => f.properties.zonecode).join('|')}
              data={geojson}
              style={(feature) => ({
                color: feature.properties.zonecode === eligibility.main_zone ? '#08447F' : '#2375C0',
                weight: feature.properties.zonecode === eligibility.main_zone ? 3 : 2,
                fillColor: feature.properties.zonecode === eligibility.main_zone ? '#2375C0' : '#06B0D4',
                fillOpacity: 0.4,
              })}
              eventHandlers={{
                add: (e) => {
                  // Auto-fit aux polygones quand ils sont ajoutés
                  const map = e.target._map;
                  if (map && e.target.getBounds) {
                    map.fitBounds(e.target.getBounds(), { padding: [20, 20] });
                  }
                },
              }}
            />
          )}
        </MapContainer>
      </div>

      <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', margin: '8px 0 16px' }}>
        {totalZones} zone{totalZones > 1 ? 's' : ''} autorisée{totalZones > 1 ? 's' : ''}
      </p>

      <div className="pbw-actions">
        <button type="button" className="pbw-btn pbw-btn-ghost" onClick={onPrev}>← Retour</button>
        <button type="button" className="pbw-btn pbw-btn-primary" onClick={onNext}>
          Continuer →
        </button>
      </div>
    </>
  );
}
