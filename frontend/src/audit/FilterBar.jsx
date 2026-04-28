import React from 'react';

export default function FilterBar({ filters, onChange, onReset, meta }) {
  const set = (key, value) => onChange({ ...filters, [key]: value });

  const hasActive = Object.values(filters).some((v) => v);

  return (
    <div className="pba-filters">
      <div className="pba-field">
        <label className="pba-label">Recherche libre</label>
        <input
          className="pba-input"
          type="search"
          placeholder="Cible, IP…"
          value={filters.q}
          onChange={(e) => set('q', e.target.value)}
        />
      </div>

      <div className="pba-field">
        <label className="pba-label">Action</label>
        <select className="pba-select" value={filters.action} onChange={(e) => set('action', e.target.value)}>
          <option value="">Toutes</option>
          {meta.actions.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
      </div>

      <div className="pba-field">
        <label className="pba-label">Type cible</label>
        <select className="pba-select" value={filters.target_type} onChange={(e) => set('target_type', e.target.value)}>
          <option value="">Tous</option>
          {meta.target_types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="pba-field">
        <label className="pba-label">Acteur (username)</label>
        <input
          className="pba-input"
          type="text"
          placeholder="ex : alice"
          value={filters.actor}
          onChange={(e) => set('actor', e.target.value)}
        />
      </div>

      <div className="pba-field">
        <label className="pba-label">Du</label>
        <input
          className="pba-input"
          type="date"
          value={filters.date_from}
          onChange={(e) => set('date_from', e.target.value)}
        />
      </div>

      <div className="pba-field">
        <label className="pba-label">Au</label>
        <input
          className="pba-input"
          type="date"
          value={filters.date_to}
          onChange={(e) => set('date_to', e.target.value)}
        />
      </div>

      <div className="pba-actions">
        <button
          type="button"
          className="pba-btn pba-btn-ghost"
          onClick={onReset}
          disabled={!hasActive}
        >
          Réinitialiser
        </button>
      </div>
    </div>
  );
}
