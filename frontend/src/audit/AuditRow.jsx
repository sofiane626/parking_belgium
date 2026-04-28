import React from 'react';
import JsonViewer from './JsonViewer.jsx';

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('fr-BE', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export default function AuditRow({ row, expanded, onToggle }) {
  const sev = row.severity || 'info';
  return (
    <>
      <tr
        className={`pba-row-clickable ${expanded ? 'pba-row-expanded' : ''}`}
        onClick={onToggle}
      >
        <td className="pba-cell-time">{fmtDate(row.created_at)}</td>
        <td>
          <span className={`pba-sev-badge pba-sev-${sev}`}>{sev}</span>
        </td>
        <td className="pba-cell-action">{row.action}</td>
        <td className="pba-cell-actor">
          {row.actor ? (
            <>
              <span style={{ fontWeight: 500 }}>{row.actor}</span>
              {row.actor_role && <span style={{ color: '#94a3b8' }}> · {row.actor_role}</span>}
            </>
          ) : (
            <span className="pba-system">système</span>
          )}
        </td>
        <td className="pba-cell-target">
          {row.target_type ? (
            <>
              <div>{row.target_type}{row.target_id ? ` #${row.target_id}` : ''}</div>
              {row.target_label && <div className="pba-cell-target-label">{row.target_label}</div>}
            </>
          ) : (
            <span className="pba-system">—</span>
          )}
        </td>
        <td className="pba-cell-time" style={{ fontFamily: 'ui-monospace, monospace' }}>
          {row.ip || <span className="pba-system">—</span>}
        </td>
        <td style={{ textAlign: 'right', color: '#94a3b8', fontSize: 14 }}>
          {expanded ? '▾' : '▸'}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="pba-detail">
            <div className="pba-detail-grid">
              <div>
                <p className="pba-label" style={{ marginBottom: 8 }}>Détails</p>
                <div className="pba-detail-meta">
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">id</span>
                    <span style={{ fontFamily: 'ui-monospace, monospace' }}>{row.id}</span>
                  </div>
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">Date complète</span>
                    <span>{fmtDate(row.created_at)}</span>
                  </div>
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">Action</span>
                    <span style={{ fontFamily: 'ui-monospace, monospace' }}>{row.action}</span>
                  </div>
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">Sévérité</span>
                    <span className={`pba-sev-badge pba-sev-${row.severity}`}>{row.severity}</span>
                  </div>
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">Acteur</span>
                    <span>{row.actor || 'système'} {row.actor_role ? `(${row.actor_role})` : ''}</span>
                  </div>
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">Cible</span>
                    <span>
                      {row.target_type || '—'}
                      {row.target_id && ` #${row.target_id}`}
                    </span>
                  </div>
                  {row.target_label && (
                    <div className="pba-detail-meta-item">
                      <span className="pba-detail-meta-label">Libellé cible</span>
                      <span>{row.target_label}</span>
                    </div>
                  )}
                  <div className="pba-detail-meta-item">
                    <span className="pba-detail-meta-label">IP source</span>
                    <span style={{ fontFamily: 'ui-monospace, monospace' }}>{row.ip || '—'}</span>
                  </div>
                </div>
              </div>
              <div>
                <p className="pba-label" style={{ marginBottom: 8 }}>Payload JSON</p>
                <JsonViewer value={row.payload} />
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
