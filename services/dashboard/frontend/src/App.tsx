import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useStreamConfig } from './hooks/useStreamConfig';
import Header from './components/Header';
import StreamPanel from './components/StreamPanel';
import StatsGrid from './components/StatsGrid';
import AlertsPanel from './components/AlertsPanel';
import TracksPanel from './components/TracksPanel';
import type { ActiveTrack, Alert } from './types';

const WS_URL = `ws://${window.location.host}/ws/tracks`;
const MAX_ALERTS = 50;
const TRACK_STALE_MS = 5000;

function formatLabel(sourceId: string): string {
  return sourceId.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function App() {
  const { connected: wsConnected, lastMessage } = useWebSocket(WS_URL);
  const streamConfig = useStreamConfig();

  // Tracks grouped by source_id so each stream only overlays its own detections.
  const [tracksBySource, setTracksBySource] = useState<Map<string, Map<number, ActiveTrack>>>(new Map());
  const [connectedBySource, setConnectedBySource] = useState<Map<string, boolean>>(new Map());
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [fps, setFps] = useState<number | null>(null);
  const frameCountRef = useRef(0);
  const lastFpsTimeRef = useRef(Date.now());
  const startTimeRef = useRef(Date.now());

  const handleConnectedChange = useCallback((sourceId: string, connected: boolean) => {
    setConnectedBySource((prev) => {
      if (prev.get(sourceId) === connected) return prev;
      const next = new Map(prev);
      next.set(sourceId, connected);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!lastMessage) return;
    const now = Date.now();
    frameCountRef.current++;
    const sourceId = lastMessage.source_id || 'default';

    setTracksBySource((prev) => {
      const next = new Map(prev);
      const sourceTracks = new Map(next.get(sourceId) ?? []);
      sourceTracks.set(lastMessage.track_id, { ...lastMessage, lastSeen: now });
      for (const [id, t] of sourceTracks) {
        if (now - t.lastSeen > TRACK_STALE_MS) sourceTracks.delete(id);
      }
      next.set(sourceId, sourceTracks);
      return next;
    });

    const cls = lastMessage.class_name;
    if (cls === 'fire' || cls === 'smoke') {
      setAlerts((prev) => {
        const isDup = prev.some(
          (a) =>
            a.type === cls &&
            a.message.includes(`#${lastMessage.track_id}`) &&
            now - a.timestamp < 10_000,
        );
        if (isDup) return prev;
        const timeStr = new Date(now).toLocaleTimeString('en-US', { hour12: false });
        const newAlert: Alert = {
          id: `${cls}-${lastMessage.track_id}-${now}`,
          type: cls,
          message: `${cls.charAt(0).toUpperCase()}${cls.slice(1)} detected — ${formatLabel(sourceId)} Track #${lastMessage.track_id} (${(lastMessage.confidence * 100).toFixed(0)}%)`,
          time: timeStr,
          timestamp: now,
        };
        return [newAlert, ...prev].slice(0, MAX_ALERTS);
      });
    }
  }, [lastMessage]);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      if (now - lastFpsTimeRef.current >= 1000) {
        setFps(frameCountRef.current);
        frameCountRef.current = 0;
        lastFpsTimeRef.current = now;
      }
    }, 500);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setTracksBySource((prev) => {
        let changed = false;
        const next = new Map(prev);
        for (const [sourceId, sourceTracks] of next) {
          const filtered = new Map(sourceTracks);
          for (const [id, t] of filtered) {
            if (now - t.lastSeen > TRACK_STALE_MS) { filtered.delete(id); changed = true; }
          }
          next.set(sourceId, filtered);
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const allTracks = useMemo(
    () => [...tracksBySource.values()].flatMap((m) => [...m.values()]),
    [tracksBySource],
  );

  const fireCount = useMemo(
    () => allTracks.filter((t) => t.class_name === 'fire').length,
    [allTracks],
  );

  const allWebrtcConnected =
    !!streamConfig && streamConfig.streams.length > 0 &&
    streamConfig.streams.every((s) => connectedBySource.get(s.source_id));
  const pipelineOk = wsConnected && allTracks.length > 0;

  return (
    <div className="app">
      <Header webrtcConnected={allWebrtcConnected} wsConnected={wsConnected} pipelineOk={pipelineOk} />
      <main className="main-content">
        <div className={`video-grid ${streamConfig && streamConfig.streams.length > 1 ? 'multi' : ''}`}>
          {streamConfig?.streams.map((stream) => (
            <StreamPanel
              key={stream.source_id}
              webrtcUrl={streamConfig.webrtc_url}
              stream={stream}
              activeTracks={tracksBySource.get(stream.source_id) ?? new Map()}
              onConnectedChange={handleConnectedChange}
            />
          ))}
        </div>
        <aside className="side-panel">
          <StatsGrid
            fireCount={fireCount}
            trackCount={allTracks.length}
            fps={fps}
            startTime={startTimeRef.current}
          />
          <AlertsPanel alerts={alerts} onClear={() => setAlerts([])} />
          <TracksPanel activeTracks={allTracks} />
        </aside>
      </main>
    </div>
  );
}
