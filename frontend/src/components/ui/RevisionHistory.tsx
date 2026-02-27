import { useState } from 'react';
import { ChevronDown, ChevronRight, History } from 'lucide-react';

export interface Revision {
  timestamp: string;
  field: string;
  oldValue: string;
  newValue: string;
  actor: 'ai' | 'operator';
}

interface RevisionHistoryProps {
  revisions: Revision[];
}

export default function RevisionHistory({ revisions }: RevisionHistoryProps) {
  const [open, setOpen] = useState(false);

  if (revisions.length === 0) return null;

  return (
    <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-tertiary)',
          fontWeight: 500,
          padding: '2px 0',
        }}
      >
        <History size={12} />
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {revisions.length} change{revisions.length !== 1 ? 's' : ''}
      </button>
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 'var(--space-1)', paddingLeft: 'var(--space-4)' }}>
          {revisions.map((r, i) => (
            <div key={i} style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                {new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              {' '}{r.field} changed from &ldquo;{r.oldValue}&rdquo; to &ldquo;{r.newValue}&rdquo;
              {' '}
              <span style={{
                fontSize: '0.65rem',
                fontWeight: 600,
                padding: '1px 4px',
                borderRadius: 'var(--radius-sm)',
                background: r.actor === 'ai' ? 'var(--priority-purple-bg)' : 'var(--accent-blue-bg)',
                color: r.actor === 'ai' ? 'var(--priority-purple)' : 'var(--accent-blue)',
              }}>
                {r.actor === 'ai' ? 'AI' : 'Operator'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
