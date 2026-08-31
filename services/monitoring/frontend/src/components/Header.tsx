interface Props {
  connected: boolean;
  windowSeconds: number | null;
}

export default function Header({ connected, windowSeconds }: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <h1>Pipeline Monitoring</h1>
        <span className="header-subtitle">
          {windowSeconds ? `Rolling ${Math.round(windowSeconds)}s window` : 'Fire Detection Pipeline'}
        </span>
      </div>
      <div className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
        <span className="status-dot" />
        <span>{connected ? 'Live' : 'Disconnected'}</span>
      </div>
    </header>
  );
}
