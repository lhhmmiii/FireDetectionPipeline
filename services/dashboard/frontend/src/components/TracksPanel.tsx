import type { ActiveTrack } from '../types';

interface Props {
  activeTracks: ActiveTrack[];
}

export default function TracksPanel({ activeTracks }: Props) {
  return (
    <div className="tracks-panel">
      <div className="panel-header">
        <h2>Active Tracks</h2>
      </div>
      <div className="tracks-list">
        {activeTracks.length === 0 ? (
          <div className="track-empty"><p>No active tracks</p></div>
        ) : (
          activeTracks.map((track) => (
            <TrackItem key={`${track.source_id}-${track.track_id}`} track={track} />
          ))
        )}
      </div>
    </div>
  );
}

function formatLabel(sourceId: string): string {
  return sourceId.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function TrackItem({ track }: { track: ActiveTrack }) {
  const cls = track.class_name || 'unknown';
  const dotClass = cls === 'fire' ? 'fire' : cls === 'smoke' ? 'smoke' : '';
  return (
    <div className="track-item">
      <div className="track-id">
        <span className={`track-class-dot ${dotClass}`} />
        #{track.track_id} — {cls}
        {track.source_id && <span className="track-source"> · {formatLabel(track.source_id)}</span>}
      </div>
      <span className="track-confidence">{(track.confidence * 100).toFixed(0)}%</span>
    </div>
  );
}
