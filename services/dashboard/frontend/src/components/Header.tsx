interface Props {
  webrtcConnected: boolean;
  wsConnected: boolean;
  pipelineOk: boolean;
}

export default function Header({ webrtcConnected, wsConnected, pipelineOk }: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2c.5 3.5 4 6 4 10a4 4 0 1 1-8 0c0-4 3.5-6.5 4-10z" />
          </svg>
          <h1>Fire Detection</h1>
        </div>
        <span className="header-subtitle">Real-Time Surveillance System</span>
      </div>
      <nav className="header-right">
        <div className="status-indicators">
          <StatusBadge label="Video" connected={webrtcConnected} />
          <StatusBadge label="Tracking" connected={wsConnected} />
          <StatusBadge label="Pipeline" connected={pipelineOk} />
        </div>
      </nav>
    </header>
  );
}

function StatusBadge({ label, connected }: { label: string; connected: boolean }) {
  return (
    <div className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
      <span className="status-dot" />
      <span className="status-label">{label}</span>
    </div>
  );
}
