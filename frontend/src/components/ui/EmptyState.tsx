import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-10) var(--space-6)',
        textAlign: 'center',
        gap: 'var(--space-3)',
        flex: 1,
      }}
    >
      <div style={{ color: 'var(--text-tertiary)' }}>
        {icon || <Inbox size={32} />}
      </div>
      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-secondary)' }}>
        {title}
      </div>
      {description && (
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', maxWidth: 240 }}>
          {description}
        </div>
      )}
      {action && <div style={{ marginTop: 'var(--space-2)' }}>{action}</div>}
    </div>
  );
}
