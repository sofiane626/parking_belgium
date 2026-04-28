import React from 'react';
import { createRoot } from 'react-dom/client';
import './audit.css';
import AuditTable from './audit/AuditTable.jsx';

const container = document.getElementById('react-audit-root');
if (container) {
  createRoot(container).render(
    <AuditTable
      apiUrl={container.dataset.apiUrl}
      exportUrl={container.dataset.exportUrl}
    />
  );
}
