import { useRef, useEffect, useCallback } from 'react';
import type { RefObject } from 'react';
import type { ActiveTrack } from '../types';

const BOX_COLORS: Record<string, string> = {
  fire: '#ef4444',
  smoke: '#f59e0b',
};
const DEFAULT_COLOR = '#3b82f6';

interface Props {
  videoRef: RefObject<HTMLVideoElement>;
  activeTracks: Map<number, ActiveTrack>;
  webrtcConnected: boolean;
  label?: string;
}

export default function VideoPanel({ videoRef, activeTracks, webrtcConnected, label = 'Live Feed' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const renderOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (activeTracks.size === 0) return;

    // The displayed video's native resolution (used for letterbox calculation).
    const videoW = video?.videoWidth || canvas.width;
    const videoH = video?.videoHeight || canvas.height;

    // Account for object-fit: contain letterboxing.
    // The video maintains its aspect ratio inside the container,
    // so there may be black bars on the sides or top/bottom.
    const containerAspect = canvas.width / canvas.height;
    const videoAspect = videoW / videoH;

    let renderW: number, renderH: number, offsetX: number, offsetY: number;
    if (videoAspect > containerAspect) {
      // Video is wider than container — black bars on top/bottom
      renderW = canvas.width;
      renderH = canvas.width / videoAspect;
      offsetX = 0;
      offsetY = (canvas.height - renderH) / 2;
    } else {
      // Video is taller than container — black bars on left/right
      renderH = canvas.height;
      renderW = canvas.height * videoAspect;
      offsetX = (canvas.width - renderW) / 2;
      offsetY = 0;
    }

    for (const track of activeTracks.values()) {
      const { bbox, class_name, track_id, confidence, frame_width, frame_height } = track;
      if (!bbox || bbox.length < 4) continue;

      // Bbox coordinates are in detection-frame space (e.g. 640×480).
      // Use frame_width/frame_height from the track if available,
      // otherwise fall back to the video's native resolution.
      const srcW = (frame_width && frame_width > 0) ? frame_width : videoW;
      const srcH = (frame_height && frame_height > 0) ? frame_height : videoH;

      const scaleX = renderW / srcW;
      const scaleY = renderH / srcH;

      const color = BOX_COLORS[class_name] ?? DEFAULT_COLOR;
      const x1 = bbox[0] * scaleX + offsetX;
      const y1 = bbox[1] * scaleY + offsetY;
      const w = (bbox[2] - bbox[0]) * scaleX;
      const h = (bbox[3] - bbox[1]) * scaleY;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, w, h);

      const label = `#${track_id} ${class_name} ${(confidence * 100).toFixed(0)}%`;
      ctx.font = '12px Inter, sans-serif';
      const textW = ctx.measureText(label).width;
      const pad = 4;

      ctx.fillStyle = color;
      ctx.globalAlpha = 0.85;
      ctx.fillRect(x1, y1 - 20, textW + pad * 2, 20);
      ctx.globalAlpha = 1;

      ctx.fillStyle = '#fff';
      ctx.fillText(label, x1 + pad, y1 - pad);
    }
  }, [activeTracks, videoRef]);

  useEffect(() => { renderOverlay(); }, [renderOverlay]);

  useEffect(() => {
    window.addEventListener('resize', renderOverlay);
    return () => window.removeEventListener('resize', renderOverlay);
  }, [renderOverlay]);

  function toggleFullscreen() {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen();
    }
  }

  return (
    <section className="video-panel">
      <div className="panel-header">
        <h2>{label}</h2>
        <button className="icon-btn" onClick={toggleFullscreen} title="Toggle fullscreen">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
          </svg>
        </button>
      </div>
      <div className="video-container" ref={containerRef}>
        <video ref={videoRef} autoPlay muted playsInline />
        <canvas ref={canvasRef} />
        {!webrtcConnected && (
          <div className="video-placeholder">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.4">
              <path d="M23 7l-7 5 7 5V7z" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
            <p>Waiting for video stream...</p>
            <span className="placeholder-hint">Connect a UAV RTSP stream to MediaMTX</span>
          </div>
        )}
      </div>
    </section>
  );
}
