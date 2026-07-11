import { useEffect, useRef, useState } from 'react';
import type { Snapshot } from '../types';

const RECONNECT_DELAY_MS = 3000;

export function useMetricsSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);

  useEffect(() => {
    let dead = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (dead) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => { if (!dead) setConnected(true); };

      ws.onmessage = (e) => {
        if (dead) return;
        try {
          setSnapshot(JSON.parse(e.data as string) as Snapshot);
        } catch { /* skip malformed */ }
      };

      ws.onclose = () => {
        if (!dead) {
          setConnected(false);
          timer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      dead = true;
      if (timer) clearTimeout(timer);
      wsRef.current?.close();
    };
  }, [url]);

  return { connected, snapshot };
}
