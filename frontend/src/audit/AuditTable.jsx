import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import FilterBar from './FilterBar.jsx';
import AuditRow from './AuditRow.jsx';

const PAGE_SIZE = 50;

// debounce hook minimaliste — pour différer la requête API quand l'utilisateur tape
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function AuditTable({ apiUrl, exportUrl }) {
  // Filtres contrôlés
  const [filters, setFilters] = useState({
    action: '', severity: '', target_type: '',
    actor: '', date_from: '', date_to: '', q: '',
  });
  const debouncedFilters = useDebounce(filters, 250);

  // Page courante — ré-init quand les filtres changent
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [counts, setCounts] = useState({});
  const [meta, setMeta] = useState({ actions: [], severities: [], target_types: [] });
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const buildUrl = useCallback((cursor = null) => {
    const params = new URLSearchParams();
    Object.entries(debouncedFilters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    params.set('page_size', String(PAGE_SIZE));
    if (cursor) params.set('cursor', String(cursor));
    return `${apiUrl}?${params.toString()}`;
  }, [apiUrl, debouncedFilters]);

  // Premier load + reset à chaque changement de filtre
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(buildUrl(), { credentials: 'same-origin' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setNextCursor(data.next_cursor);
        setCounts(data.counts_by_severity || {});
        setMeta(data.meta || { actions: [], severities: [], target_types: [] });
        setTotal(data.total_filtered || 0);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [buildUrl]);

  // Charge la page suivante (scroll infini)
  const loadMore = useCallback(() => {
    if (!nextCursor || loading) return;
    setLoading(true);
    fetch(buildUrl(nextCursor), { credentials: 'same-origin' })
      .then((r) => r.json())
      .then((data) => {
        setItems((prev) => [...prev, ...data.items]);
        setNextCursor(data.next_cursor);
      })
      .finally(() => setLoading(false));
  }, [buildUrl, nextCursor, loading]);

  // Sentinel intersection observer pour scroll infini
  const sentinelRef = useRef(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) loadMore();
    }, { rootMargin: '200px' });
    io.observe(node);
    return () => io.disconnect();
  }, [loadMore]);

  // URL d'export = même endpoint Django, mais on transmet les filtres courants
  const exportHref = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(debouncedFilters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    return `${exportUrl}?${params.toString()}`;
  }, [exportUrl, debouncedFilters]);

  const toggleSeverityFilter = (severity) => {
    setFilters((f) => ({ ...f, severity: f.severity === severity ? '' : severity }));
  };

  const resetFilters = () => {
    setFilters({
      action: '', severity: '', target_type: '',
      actor: '', date_from: '', date_to: '', q: '',
    });
  };

  return (
    <div className="pba-shell">
      {/* Header avec compteurs cliquables */}
      <div className="pba-header">
        <div>
          <p style={{ margin: 0, fontSize: 14, color: '#64748b' }}>
            <strong style={{ color: '#0f172a', fontSize: 16 }}>{total.toLocaleString()}</strong>
            {' '}entrée{total > 1 ? 's' : ''} correspond{total > 1 ? 'ent' : ''} aux filtres
          </p>
          <div className="pba-counts" style={{ marginTop: 8 }}>
            {['info', 'notice', 'warning', 'critical'].map((sev) => (
              <span
                key={sev}
                className={`pba-chip pba-chip-${sev} ${filters.severity === sev ? 'pba-chip-active' : ''}`}
                onClick={() => toggleSeverityFilter(sev)}
              >
                {sev}
                <span className="pba-chip-count">{(counts[sev] || 0).toLocaleString()}</span>
              </span>
            ))}
          </div>
        </div>
        <a href={exportHref} className="pba-btn pba-btn-ghost">
          Exporter CSV
        </a>
      </div>

      {/* Barre de filtres */}
      <FilterBar
        filters={filters}
        onChange={setFilters}
        onReset={resetFilters}
        meta={meta}
      />

      {/* Table */}
      {error && (
        <div className="pba-empty" style={{ color: '#b91c1c' }}>
          Erreur de chargement : {error}
        </div>
      )}

      <div className="pba-table-wrapper">
        <table className="pba-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Sévérité</th>
              <th>Action</th>
              <th>Acteur</th>
              <th>Cible</th>
              <th>IP</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading && (
              <tr><td colSpan={7} className="pba-empty">Aucune entrée correspondant aux filtres.</td></tr>
            )}
            {items.map((row) => (
              <AuditRow
                key={row.id}
                row={row}
                expanded={expandedId === row.id}
                onToggle={() => setExpandedId((prev) => prev === row.id ? null : row.id)}
              />
            ))}
          </tbody>
        </table>

        <div ref={sentinelRef}></div>

        {loading && (
          <div className="pba-footer">
            <span className="pba-spinner"></span> Chargement…
          </div>
        )}
        {!loading && !nextCursor && items.length > 0 && (
          <div className="pba-footer">
            Fin de la liste · {items.length} entrée{items.length > 1 ? 's' : ''} affichée{items.length > 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  );
}
