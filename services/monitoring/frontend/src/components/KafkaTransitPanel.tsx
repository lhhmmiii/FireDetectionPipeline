import type { Snapshot } from '../types';
import { HOP_LABELS, HOP_ORDER } from '../types';
import { formatMs } from '../format';
import BarRow from './BarRow';

interface Props {
  snapshot: Snapshot | null;
}

export default function KafkaTransitPanel({ snapshot }: Props) {
  const hops = snapshot?.kafka_transit ?? {};
  const maxP95 = Math.max(1, ...HOP_ORDER.map((h) => hops[h]?.p95_ms ?? 0));

  return (
    <div className="panel">
      <div className="panel-title">Kafka Transit Latency</div>
      {HOP_ORDER.map((hop) => {
        const h = hops[hop];
        return (
          <BarRow
            key={hop}
            label={HOP_LABELS[hop]}
            color="var(--sequential)"
            value={h?.p50_ms ?? null}
            marker={h?.p95_ms ?? null}
            maxValue={maxP95}
            valueText={formatMs(h?.p50_ms ?? null)}
            markerText={h ? `p95 ${formatMs(h.p95_ms)}` : undefined}
          />
        );
      })}
      <div className="legend-hint">Time between one stage finishing and the next starting (topic hop + queueing)</div>
    </div>
  );
}
