import { useEffect, useRef, useState } from 'react';
import type { TrackMessage } from '../types';

const RECONNECT_DELAY_MS = 3000;

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<TrackMessage | null>(null);

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
          setLastMessage(JSON.parse(e.data as string) as TrackMessage);
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

  return { connected, lastMessage };
}
