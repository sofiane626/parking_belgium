import React from 'react';

// Mini-formateur JSON avec coloration syntaxique. Pas de dépendance externe :
// on génère le HTML ligne par ligne en utilisant React, ce qui reste safe (pas
// de dangerouslySetInnerHTML, donc immune au XSS sur les payloads d'audit).

function renderValue(value, indent = 0) {
  if (value === null) return <span className="pba-json-null">null</span>;
  if (typeof value === 'boolean') return <span className="pba-json-bool">{String(value)}</span>;
  if (typeof value === 'number') return <span className="pba-json-number">{value}</span>;
  if (typeof value === 'string') return <span className="pba-json-string">"{value}"</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <>[]</>;
    return (
      <>
        {'['}
        {value.map((item, i) => (
          <React.Fragment key={i}>
            {'\n'}{' '.repeat((indent + 1) * 2)}
            {renderValue(item, indent + 1)}
            {i < value.length - 1 && ','}
          </React.Fragment>
        ))}
        {'\n'}{' '.repeat(indent * 2)}{']'}
      </>
    );
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.length === 0) return <>{'{}'}</>;
    return (
      <>
        {'{'}
        {entries.map(([k, v], i) => (
          <React.Fragment key={k}>
            {'\n'}{' '.repeat((indent + 1) * 2)}
            <span className="pba-json-key">"{k}"</span>: {renderValue(v, indent + 1)}
            {i < entries.length - 1 && ','}
          </React.Fragment>
        ))}
        {'\n'}{' '.repeat(indent * 2)}{'}'}
      </>
    );
  }
  return <>{String(value)}</>;
}

export default function JsonViewer({ value }) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) {
    return <div className="pba-json-cell" style={{ fontStyle: 'italic', color: '#94a3b8' }}>(payload vide)</div>;
  }
  return <pre className="pba-json-cell">{renderValue(value)}</pre>;
}
