import React from 'react';

/**
 * On délègue le paiement aux vues Django existantes (Stripe Checkout +
 * simulation). Le wizard offre simplement les boutons d'accès. Au retour
 * sur cette URL avec ?step=success, l'étape 5 est affichée directement.
 */
export default function Step4Payment({ eligibility, permitId, paymentStartUrlTpl, permitDetailUrlTpl }) {
  const priceEur = (eligibility.price_cents / 100).toFixed(2);
  const startUrl = paymentStartUrlTpl.replace('__PK__', permitId);
  const detailUrl = permitDetailUrlTpl.replace('__PK__', permitId);

  return (
    <>
      <h1 className="pbw-title">Paiement</h1>
      <p className="pbw-subtitle">
        Votre demande a été soumise. Procédez au paiement pour activer votre carte.
      </p>

      <div className="pbw-price">
        <div>
          <span className="pbw-price-amount">{priceEur}</span>
          <span className="pbw-price-currency">€</span>
        </div>
        <div className="pbw-price-detail">Carte #{permitId}</div>
      </div>

      <div className="pbw-notice pbw-notice-info">
        🔒 Paiement sécurisé via Stripe (test mode). Les méthodes disponibles vous seront proposées
        sur la page de paiement.
      </div>

      <div className="pbw-actions" style={{ flexWrap: 'wrap' }}>
        <a href={detailUrl} className="pbw-btn pbw-btn-ghost">← Voir ma carte</a>
        <a href={startUrl} className="pbw-btn pbw-btn-signal">
          Procéder au paiement ({priceEur} €) →
        </a>
      </div>

      <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', marginTop: 16 }}>
        Cette demande est conservée — vous pouvez aussi payer plus tard depuis « Mes cartes ».
      </p>
    </>
  );
}
