import React from 'react';

export default function Stepper({ steps, currentKey }) {
  const currentIdx = steps.findIndex((s) => s.key === currentKey);
  return (
    <ol className="pbw-stepper">
      {steps.map((s, i) => {
        const cls =
          i < currentIdx ? 'pbw-step is-done'
          : i === currentIdx ? 'pbw-step is-current'
          : 'pbw-step';
        return (
          <li key={s.key} className={cls}>
            <div className="pbw-bullet">
              {i < currentIdx ? '✓' : i + 1}
            </div>
            <div className="pbw-step-label">{s.label}</div>
          </li>
        );
      })}
    </ol>
  );
}
