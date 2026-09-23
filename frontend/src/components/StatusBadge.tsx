interface StatusBadgeProps {
  status: 'checking' | 'online' | 'offline';
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const label =
    status === 'online'
      ? 'API Online'
      : status === 'offline'
        ? 'API Offline'
        : 'Checking...';

  return (
    <span className={`status-badge status-${status}`} role="status">
      <span className="status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
