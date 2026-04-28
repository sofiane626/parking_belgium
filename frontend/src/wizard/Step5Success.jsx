import React from 'react';

export default function Step5Success({ eligibility, permitId, permitDetailUrlTpl }) {
  const detailUrl = permitId
    ? permitDetailUrlTpl.replace('__PK__', permitId)
    : null;
  return (
    <>
      <div style={{ textAlign: 'center' }}>
        <div className="pbw-success-icon">✓</div>
        <h1 className="pbw-title">Carte active</h1>
        <p className="pbw-subtitle">
          La carte riverain est désormais active. Un email de confirmation a été envoyé.
        </p>
      </div>

      <div className="pbw-card" style={{ marginTop: 16 }}>
        <p className="pbw-card-label">Plaque autorisée</p>
        <p className="pbw-card-value" style={{ fontFamily: 'ui-monospace, monospace' }}>
          {eligibility.vehicle.plate}
        </p>
        <p className="pbw-card-label" style={{ marginTop: 12 }}>Zones</p>
        <div>
          <span className="pbw-zone-tag" style={{ background: '#08447F', color: '#fff' }}>
            {eligibility.main_zone || '—'}
          </span>
          {eligibility.additional_zones.map((z) => (
            <span key={z} className="pbw-zone-tag" style={{ background: '#e8f1fb', color: '#08447F' }}>{z}</span>
          ))}
        </div>
      </div>

      <div className="pbw-actions pbw-actions-end">
        {detailUrl && (
          <a href={detailUrl} className="pbw-btn pbw-btn-primary">
            Voir ma carte →
          </a>
        )}
      </div>
    </>
  );
}
