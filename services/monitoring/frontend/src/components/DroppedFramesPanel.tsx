import type { Snapshot } from '../types';
import { STAGE_LABELS, STAGE_ORDER } from '../types';
import { formatPct } from '../format';

interface Props {
  snapshot: Snapshot | null;
}

export default function DroppedFramesPanel({ snapshot }: Props) {
  const stages = snapshot?.stages ?? {};

  return (
    <div className="panel">
      <div className="panel-title">Dropped / Errored Frames</div>
      {STAGE_ORDER.map((stage) => {
        const s = stages[stage];
        const count = s?.dropped_count ?? 0;
        return (
          <div className="dropped-row" key={stage}>
            <div className="bar-row-label">{STAGE_LABELS[stage]}</div>
            <div className={`dropped-badge ${count > 0 ? 'some' : 'none'}`}>
              {count > 0 ? `${count} dropped` : 'none dropped'}
            </div>
            <div className="bar-row-value">{formatPct(s?.drop_rate ?? 0)}</div>
          </div>
        );
      })}
      <div className="legend-hint">Share of messages at each stage that errored or were skipped</div>
    </div>
  );
}
