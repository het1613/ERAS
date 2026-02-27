import React from 'react';

type BadgeVariant = 'priority' | 'status' | 'confidence' | 'info' | 'warning' | 'danger' | 'neutral';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  color?: string;
  bg?: string;
  size?: 'sm' | 'md';
  dot?: boolean;
  className?: string;
}

const VARIANT_STYLES: Record<BadgeVariant, { bg: string; color: string }> = {
  priority: { bg: 'var(--surface-tertiary)', color: 'var(--text-secondary)' },
  status: { bg: 'var(--accent-blue-bg)', color: 'var(--accent-blue)' },
  confidence: { bg: 'var(--accent-green-bg)', color: 'var(--accent-green)' },
  info: { bg: 'var(--accent-blue-bg)', color: 'var(--accent-blue)' },
  warning: { bg: 'var(--accent-warning-bg)', color: 'var(--accent-warning)' },
  danger: { bg: 'var(--accent-danger-bg)', color: 'var(--accent-danger)' },
  neutral: { bg: 'var(--surface-tertiary)', color: 'var(--text-secondary)' },
};

export default function Badge({ children, variant = 'neutral', color, bg, size = 'sm', dot, className = '' }: BadgeProps) {
  const styles = VARIANT_STYLES[variant];
  const finalBg = bg || styles.bg;
  const finalColor = color || styles.color;

  return (
    <span
      className={`eras-badge eras-badge-${size} ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: size === 'sm' ? '2px 8px' : '3px 10px',
        borderRadius: 'var(--radius-full)',
        fontSize: size === 'sm' ? 'var(--text-xs)' : 'var(--text-sm)',
        fontWeight: 600,
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
        backgroundColor: finalBg,
        color: finalColor,
      }}
    >
      {dot && (
        <span
          style={{
            width: size === 'sm' ? 6 : 8,
            height: size === 'sm' ? 6 : 8,
            borderRadius: '50%',
            backgroundColor: finalColor,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  );
}
