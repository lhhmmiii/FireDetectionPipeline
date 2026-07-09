import { useEffect, useState } from 'react';
import type { StreamConfig } from '../types';

interface StreamsResponse {
  webrtc_url: string;
  streams: StreamConfig[];
}

export function useStreamConfig() {
  const [config, setConfig] = useState<StreamsResponse | null>(null);

  useEffect(() => {
    let dead = false;
    fetch('/api/streams')
      .then((res) => res.json())
      .then((data: StreamsResponse) => { if (!dead) setConfig(data); })
      .catch(() => { /* retried implicitly on next mount / page reload */ });
    return () => { dead = true; };
  }, []);

  return config;
}
