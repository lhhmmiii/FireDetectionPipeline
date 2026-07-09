import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';

interface Props {
  fireCount: number;
  trackCount: number;
  fps: number | null;
  startTime: number;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function StatsGrid({ fireCount, trackCount, fps, startTime }: Props) {
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setUptime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  return (
    <div className="stats-grid">
      <StatCard iconClass="fire" icon={<FireIcon />} value={String(fireCount)} label="Active Fires" />
      <StatCard iconClass="track" icon={<TrackIcon />} value={String(trackCount)} label="Tracked Objects" />
      <StatCard iconClass="fps" icon={<ClockIcon />} value={fps !== null ? String(fps) : '--'} label="FPS" />
      <StatCard iconClass="uptime" icon={<ShieldIcon />} value={formatUptime(uptime)} label="Uptime" />
    </div>
  );
}

function StatCard({ iconClass, icon, value, label }: {
  iconClass: string;
  icon: ReactNode;
  value: string;
  label: string;
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconClass}`}>{icon}</div>
      <div className="stat-info">
        <span className="stat-value">{value}</span>
        <span className="stat-label">{label}</span>
      </div>
    </div>
  );
}

function FireIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2c.5 3.5 4 6 4 10a4 4 0 1 1-8 0c0-4 3.5-6.5 4-10z" />
    </svg>
  );
}

function TrackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
