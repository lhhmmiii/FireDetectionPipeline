export const STAGE_ORDER = ['frame_extractor', 'detection', 'tracking', 'dashboard'] as const;
export type Stage = (typeof STAGE_ORDER)[number];

export const HOP_ORDER = ['frames', 'detections', 'tracks'] as const;
export type Hop = (typeof HOP_ORDER)[number];

export interface StageStats {
  count: number;
  throughput_fps: number;
  p50_ms: number | null;
  p95_ms: number | null;
  dropped_count: number;
  drop_rate: number;
}

export interface HopStats {
  p50_ms: number | null;
  p95_ms: number | null;
  count: number;
}

export interface LatencyStats {
  p50_ms: number | null;
  p95_ms: number | null;
  count: number;
}

export interface Snapshot {
  window_seconds: number;
  generated_at: string;
  stages: Record<string, StageStats>;
  kafka_transit: Record<string, HopStats>;
  end_to_end: LatencyStats;
}

export interface Diffed<T> {
  baseline: T;
  live: T;
  delta: T extends number ? number : never;
}

export interface CompareResponse {
  baseline: Snapshot;
  live: Snapshot;
  diff: unknown;
}

export const STAGE_LABELS: Record<string, string> = {
  frame_extractor: 'Frame Extractor',
  detection: 'Detection',
  tracking: 'Tracking',
  dashboard: 'Dashboard',
};

export const HOP_LABELS: Record<string, string> = {
  frames: 'Frames (extractor → detection)',
  detections: 'Detections (detection → tracking)',
  tracks: 'Tracks (tracking → dashboard)',
};
