import React from 'react';
import { createRoot } from 'react-dom/client';
import './wizard.css';  // contient @import de leaflet.css
import Wizard from './wizard/Wizard.jsx';

const container = document.getElementById('react-wizard-root');
if (container) {
  // Le template Django expose les paramètres dynamiques via data-attributes —
  // ça évite tout couplage URL/state global et reste serializable.
  const props = {
    vehiclePk: parseInt(container.dataset.vehiclePk, 10),
    eligibilityUrl: container.dataset.eligibilityUrl,
    submitUrl: container.dataset.submitUrl,
    paymentStartUrlTpl: container.dataset.paymentStartUrlTpl,
    permitDetailUrlTpl: container.dataset.permitDetailUrlTpl,
    polygonsGeojsonUrl: container.dataset.polygonsGeojsonUrl,
    csrfToken: container.dataset.csrfToken,
    initialPermitId: container.dataset.initialPermitId
      ? parseInt(container.dataset.initialPermitId, 10)
      : null,
    initialStep: container.dataset.initialStep || null,
  };
  createRoot(container).render(<Wizard {...props} />);
}
