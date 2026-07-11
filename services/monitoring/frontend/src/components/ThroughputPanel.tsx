import type { Snapshot } from '../types';
import { STAGE_LABELS, STAGE_ORDER } from '../types';
import { formatFps } from '../format';
import BarRow from './BarRow';

const STAGE_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];

interface Props {
  snapshot: Snapshot | null;
}

export default function ThroughputPanel({ snapshot }: Props) {
  const stages = snapshot?.stages ?? {};
  const maxFps = Math.max(1, ...STAGE_ORDER.map((s) => stages[s]?.throughput_fps ?? 0));

  return (
    <div className="panel">
      <div className="panel-title">Per-Stage Throughput</div>
      {STAGE_ORDER.map((stage, i) => {
        const s = stages[stage];
        return (
          <BarRow
            key={stage}
            label={STAGE_LABELS[stage]}
            color={STAGE_COLORS[i]}
            value={s?.throughput_fps ?? null}
            maxValue={maxFps}
            valueText={formatFps(s?.throughput_fps ?? null)}
          />
        );
      })}
      <div className="legend-hint">Successful messages / window</div>
    </div>
  );
}
