import type { Snapshot } from '../types';
import { formatFps, formatMs } from '../format';

interface Props {
  snapshot: Snapshot | null;
}

export default function KpiRow({ snapshot }: Props) {
  const e2e = snapshot?.end_to_end;
  const dashboardStage = snapshot?.stages['dashboard'];
  const totalDropped = snapshot
    ? Object.values(snapshot.stages).reduce((sum, s) => sum + s.dropped_count, 0)
    : null;

  return (
    <div className="kpi-row">
      <KpiTile label="End-to-End p50" value={formatMs(e2e?.p50_ms ?? null)} sub={`n=${e2e?.count ?? 0}`} />
      <KpiTile label="End-to-End p95" value={formatMs(e2e?.p95_ms ?? null)} />
      <KpiTile
        label="Delivered FPS"
        value={dashboardStage ? formatFps(dashboardStage.throughput_fps) : '--'}
        sub="dashboard stage"
      />
      <KpiTile
        label="Dropped Frames"
        value={totalDropped !== null ? String(totalDropped) : '--'}
        sub="across all stages"
      />
    </div>
  );
}

function KpiTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="kpi-tile">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
