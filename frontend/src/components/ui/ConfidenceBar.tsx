interface ConfidenceBarProps {
  value: number; // 0-1
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

function getConfidenceInfo(value: number): { label: string; color: string; bg: string } {
  if (value >= 0.7) return { label: 'High', color: 'var(--accent-green)', bg: 'var(--accent-green-bg)' };
  if (value >= 0.4) return { label: 'Medium', color: 'var(--accent-warning)', bg: 'var(--accent-warning-bg)' };
  return { label: 'Low', color: 'var(--accent-danger)', bg: 'var(--accent-danger-bg)' };
}

export default function ConfidenceBar({ value, showLabel = true, size = 'sm' }: ConfidenceBarProps) {
  const pct = Math.round(value * 100);
  const { label, color, bg } = getConfidenceInfo(value);
  const height = size === 'sm' ? 4 : 6;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
      <div
        style={{
          flex: 1,
          height,
          borderRadius: 'var(--radius-full)',
          backgroundColor: bg,
          overflow: 'hidden',
          minWidth: 40,
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            borderRadius: 'var(--radius-full)',
            backgroundColor: color,
            transition: 'width var(--transition-base)',
          }}
        />
      </div>
      {showLabel && (
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color, whiteSpace: 'nowrap' }}>
          {pct}% {label}
        </span>
      )}
    </div>
  );
}
