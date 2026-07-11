import type { Snapshot } from '../types';
import { STAGE_LABELS, STAGE_ORDER } from '../types';
import { formatMs } from '../format';
import BarRow from './BarRow';

const STAGE_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];

interface Props {
  snapshot: Snapshot | null;
}

export default function StageLatencyPanel({ snapshot }: Props) {
  const stages = snapshot?.stages ?? {};
  const maxP95 = Math.max(1, ...STAGE_ORDER.map((s) => stages[s]?.p95_ms ?? 0));

  return (
    <div className="panel">
      <div className="panel-title">Per-Stage Latency</div>
      {STAGE_ORDER.map((stage, i) => {
        const s = stages[stage];
        return (
          <BarRow
            key={stage}
            label={STAGE_LABELS[stage]}
            color={STAGE_COLORS[i]}
            value={s?.p50_ms ?? null}
            marker={s?.p95_ms ?? null}
            maxValue={maxP95}
            valueText={formatMs(s?.p50_ms ?? null)}
            markerText={s ? `p95 ${formatMs(s.p95_ms)}` : undefined}
          />
        );
      })}
      <div className="legend-hint">Bar = p50, tick = p95</div>
    </div>
  );
}
