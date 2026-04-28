import React, { useEffect, useState } from 'react';
import Stepper from './Stepper.jsx';
import Step1Vehicle from './Step1Vehicle.jsx';
import Step2Zone from './Step2Zone.jsx';
import Step3Summary from './Step3Summary.jsx';
import Step4Payment from './Step4Payment.jsx';
import Step5Success from './Step5Success.jsx';

const STEPS = [
  { key: 'vehicle', label: 'Véhicule' },
  { key: 'zone',    label: 'Zone' },
  { key: 'summary', label: 'Tarif' },
  { key: 'payment', label: 'Paiement' },
  { key: 'success', label: 'Activée' },
];

export default function Wizard(props) {
  const {
    vehiclePk,
    eligibilityUrl,
    submitUrl,
    paymentStartUrlTpl,
    permitDetailUrlTpl,
    polygonsGeojsonUrl,
    csrfToken,
    initialPermitId,
    initialStep,
  } = props;

  // Si on revient depuis Stripe (callback success), on saute direct à l'étape 5
  const [currentStep, setCurrentStep] = useState(
    initialStep || (initialPermitId ? 'success' : 'vehicle')
  );
  const [eligibility, setEligibility] = useState(null);
  const [permitId, setPermitId] = useState(initialPermitId);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Charge l'eligibility au mount (et aussi au retour pour récap)
  useEffect(() => {
    fetch(eligibilityUrl, { credentials: 'same-origin' })
      .then((r) => {
        if (!r.ok) return r.json().then((d) => Promise.reject(d));
        return r.json();
      })
      .then(setEligibility)
      .catch((e) => {
        setError(e.address || e.detail || e.vehicle || 'Impossible de charger les informations.');
      });
  }, [eligibilityUrl]);

  const goNext = () => {
    const idx = STEPS.findIndex((s) => s.key === currentStep);
    if (idx < STEPS.length - 1) setCurrentStep(STEPS[idx + 1].key);
  };

  const goPrev = () => {
    const idx = STEPS.findIndex((s) => s.key === currentStep);
    if (idx > 0) setCurrentStep(STEPS[idx - 1].key);
  };

  // Étape 3 → 4 : on crée et soumet le permit côté serveur
  const submitAndProceed = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(submitUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data.detail || 'Erreur lors de la création de la carte.');
        return;
      }
      setPermitId(data.permit_id);
      // Si la carte est gratuite et déjà activée → succès direct
      if (data.next_step === 'success') {
        setCurrentStep('success');
      } else if (data.next_step === 'payment') {
        setCurrentStep('payment');
      } else if (data.next_step === 'review') {
        setError('Cette demande passe en revue manuelle. Délai indicatif : 48 h ouvrées.');
      } else {
        setError('Demande refusée. Vérifiez l\'adresse et le véhicule.');
      }
    } catch (_e) {
      setError('Erreur réseau.');
    } finally {
      setSubmitting(false);
    }
  };

  if (error && !eligibility) {
    return (
      <div className="pbw-shell">
        <div className="pbw-error">{error}</div>
      </div>
    );
  }
  if (!eligibility) {
    return (
      <div className="pbw-shell">
        <div className="pbw-loading"><div className="pbw-spinner"></div><p>Chargement…</p></div>
      </div>
    );
  }

  // L'attribution est refusée (DENY) → on n'avance pas
  if (eligibility.denied) {
    return (
      <div className="pbw-shell">
        <h1 className="pbw-title">Demande non éligible</h1>
        <p className="pbw-subtitle">
          L'attribution automatique a été refusée pour cette adresse.
        </p>
        <div className="pbw-notice pbw-notice-error">
          {eligibility.notes.length > 0 ? eligibility.notes.join(' · ') : 'Contactez votre commune pour plus d\'informations.'}
        </div>
      </div>
    );
  }

  return (
    <div className="pbw-shell">
      <Stepper steps={STEPS} currentKey={currentStep} />

      {error && <div className="pbw-notice pbw-notice-error">{error}</div>}

      <div className="pbw-step-content" key={currentStep}>
        {currentStep === 'vehicle' && (
          <Step1Vehicle eligibility={eligibility} onNext={goNext} />
        )}
        {currentStep === 'zone' && (
          <Step2Zone
            eligibility={eligibility}
            polygonsGeojsonUrl={polygonsGeojsonUrl}
            onNext={goNext}
            onPrev={goPrev}
          />
        )}
        {currentStep === 'summary' && (
          <Step3Summary
            eligibility={eligibility}
            onSubmit={submitAndProceed}
            onPrev={goPrev}
            submitting={submitting}
          />
        )}
        {currentStep === 'payment' && (
          <Step4Payment
            eligibility={eligibility}
            permitId={permitId}
            paymentStartUrlTpl={paymentStartUrlTpl}
            permitDetailUrlTpl={permitDetailUrlTpl}
          />
        )}
        {currentStep === 'success' && (
          <Step5Success
            eligibility={eligibility}
            permitId={permitId}
            permitDetailUrlTpl={permitDetailUrlTpl}
          />
        )}
      </div>
    </div>
  );
}
