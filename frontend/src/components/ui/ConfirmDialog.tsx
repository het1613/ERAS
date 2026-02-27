import React from 'react';
import { AlertTriangle } from 'lucide-react';
import Button from './Button';
import './ConfirmDialog.css';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'primary' | 'danger' | 'success';
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'primary',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="eras-dialog-overlay" onClick={onCancel}>
      <div className="eras-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="eras-dialog-header">
          <AlertTriangle size={18} style={{ color: 'var(--accent-warning)' }} />
          <h3 className="eras-dialog-title">{title}</h3>
        </div>
        <div className="eras-dialog-body">{children}</div>
        <div className="eras-dialog-footer">
          <Button variant="secondary" size="md" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={variant} size="md" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
