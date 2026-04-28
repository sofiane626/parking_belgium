import React from 'react';

export default function Step1Vehicle({ eligibility, onNext }) {
  const v = eligibility.vehicle;
  const a = eligibility.address;
  return (
    <>
      <h1 className="pbw-title">Vérifions vos informations</h1>
      <p className="pbw-subtitle">
        Voici le véhicule et l'adresse qui seront utilisés pour cette demande de carte riverain.
      </p>

      <div className="pbw-grid-2">
        <div className="pbw-card">
          <p className="pbw-card-label">Véhicule</p>
          <p className="pbw-card-value" style={{ fontFamily: 'ui-monospace, monospace' }}>
            {v.plate}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#475569' }}>
            {v.brand} {v.model}{v.color ? ` · ${v.color}` : ''}
          </p>
        </div>
        <div className="pbw-card">
          <p className="pbw-card-label">Adresse de référence</p>
          <p className="pbw-card-value" style={{ fontSize: 15 }}>
            {a.street} {a.number}{a.box ? ` bte ${a.box}` : ''}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#475569' }}>
            {a.postal_code} {a.commune}
          </p>
        </div>
      </div>

      <div className="pbw-notice pbw-notice-info">
        ℹ Si l'une de ces informations est incorrecte, fermez ce wizard et corrigez-la depuis
        votre espace personnel avant de revenir.
      </div>

      <div className="pbw-actions pbw-actions-end">
        <button type="button" className="pbw-btn pbw-btn-primary" onClick={onNext}>
          Continuer →
        </button>
      </div>
    </>
  );
}
