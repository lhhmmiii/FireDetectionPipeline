export interface TrackMessage {
  track_id: number;
  frame_id: string;
  timestamp: string;
  bbox: [number, number, number, number];
  confidence: number;
  class_id: number;
  class_name: string;
  source_id: string;
}

export type AlertType = 'fire' | 'smoke' | 'info';

export interface Alert {
  id: string;
  type: AlertType;
  message: string;
  time: string;
  timestamp: number;
}

export interface ActiveTrack extends TrackMessage {
  lastSeen: number;
}

export interface StreamConfig {
  source_id: string;
  stream_name: string;
}
