import React from 'react';

export default function Step3Summary({ eligibility, onSubmit, onPrev, submitting }) {
  const priceEur = (eligibility.price_cents / 100).toFixed(2);
  const isFree = eligibility.price_cents === 0;
  return (
    <>
      <h1 className="pbw-title">Récapitulatif</h1>
      <p className="pbw-subtitle">
        Vérifiez le tarif avant de soumettre votre demande.
      </p>

      <div className="pbw-price">
        {isFree ? (
          <>
            <div className="pbw-price-amount">Gratuit</div>
            <div className="pbw-price-detail">Aucun paiement nécessaire pour cette commune.</div>
          </>
        ) : (
          <>
            <div>
              <span className="pbw-price-amount">{priceEur}</span>
              <span className="pbw-price-currency">€</span>
            </div>
            <div className="pbw-price-detail">
              pour {eligibility.validity_days} jours
              {eligibility.address.commune ? ` à ${eligibility.address.commune}` : ''}
            </div>
          </>
        )}
      </div>

      <div className="pbw-grid-3" style={{ marginTop: 16 }}>
        <div className="pbw-card">
          <p className="pbw-card-label">Type</p>
          <p className="pbw-card-value" style={{ fontSize: 15 }}>Riverain</p>
        </div>
        <div className="pbw-card">
          <p className="pbw-card-label">Validité</p>
          <p className="pbw-card-value" style={{ fontSize: 15 }}>{eligibility.validity_days} jours</p>
        </div>
        <div className="pbw-card">
          <p className="pbw-card-label">Plaque</p>
          <p className="pbw-card-value" style={{ fontSize: 15, fontFamily: 'ui-monospace, monospace' }}>
            {eligibility.vehicle.plate}
          </p>
        </div>
      </div>

      {eligibility.requires_manual_review && (
        <div className="pbw-notice pbw-notice-warn">
          ⏳ Cette demande passera en revue manuelle. Vous serez notifié sous 48 h ouvrées.
        </div>
      )}

      <div className="pbw-actions">
        <button type="button" className="pbw-btn pbw-btn-ghost" onClick={onPrev} disabled={submitting}>
          ← Retour
        </button>
        <button type="button" className="pbw-btn pbw-btn-primary" onClick={onSubmit} disabled={submitting}>
          {submitting ? <><span className="pbw-spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></span> Soumission…</> : 'Soumettre ma demande →'}
        </button>
      </div>
    </>
  );
}
