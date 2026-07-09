import { useEffect } from 'react';
import { useWebRTC } from '../hooks/useWebRTC';
import VideoPanel from './VideoPanel';
import type { ActiveTrack, StreamConfig } from '../types';

interface Props {
  webrtcUrl: string;
  stream: StreamConfig;
  activeTracks: Map<number, ActiveTrack>;
  onConnectedChange: (sourceId: string, connected: boolean) => void;
}

function formatLabel(sourceId: string): string {
  return sourceId.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StreamPanel({ webrtcUrl, stream, activeTracks, onConnectedChange }: Props) {
  const { connected, videoRef } = useWebRTC(webrtcUrl, stream.stream_name);

  useEffect(() => {
    onConnectedChange(stream.source_id, connected);
  }, [stream.source_id, connected, onConnectedChange]);

  return (
    <VideoPanel
      videoRef={videoRef}
      activeTracks={activeTracks}
      webrtcConnected={connected}
      label={formatLabel(stream.source_id)}
    />
  );
}
