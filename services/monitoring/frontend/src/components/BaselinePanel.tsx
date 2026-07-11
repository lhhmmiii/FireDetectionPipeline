import { useEffect, useState } from 'react';
import { HOP_LABELS, HOP_ORDER, STAGE_LABELS, STAGE_ORDER } from '../types';
import type { CompareResponse } from '../types';
import { formatFps, formatMs } from '../format';

interface DiffLeaf {
  baseline: number | null;
  live: number | null;
  delta: number;
}

type Unit = 'ms' | 'fps' | 'count';

interface MetricRow {
  label: string;
  path: (string | number)[];
  unit: Unit;
  lowerIsBetter: boolean;
}

const ROWS: MetricRow[] = [
  { label: 'End-to-End p50', path: ['end_to_end', 'p50_ms'], unit: 'ms', lowerIsBetter: true },
  { label: 'End-to-End p95', path: ['end_to_end', 'p95_ms'], unit: 'ms', lowerIsBetter: true },
  ...STAGE_ORDER.flatMap((stage): MetricRow[] => [
    { label: `${STAGE_LABELS[stage]} p50`, path: ['stages', stage, 'p50_ms'], unit: 'ms', lowerIsBetter: true },
    { label: `${STAGE_LABELS[stage]} FPS`, path: ['stages', stage, 'throughput_fps'], unit: 'fps', lowerIsBetter: false },
    { label: `${STAGE_LABELS[stage]} Dropped`, path: ['stages', stage, 'dropped_count'], unit: 'count', lowerIsBetter: true },
  ]),
  ...HOP_ORDER.map((hop): MetricRow => ({
    label: `${HOP_LABELS[hop]} transit p50`,
    path: ['kafka_transit', hop, 'p50_ms'],
    unit: 'ms',
    lowerIsBetter: true,
  })),
];

function getLeaf(diff: unknown, path: (string | number)[]): DiffLeaf | undefined {
  let cur: unknown = diff;
  for (const key of path) {
    if (cur === null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string | number, unknown>)[key];
  }
  if (
    cur !== null &&
    typeof cur === 'object' &&
    'baseline' in cur &&
    'live' in cur &&
    'delta' in cur
  ) {
    return cur as DiffLeaf;
  }
  return undefined;
}

function formatByUnit(value: number | null, unit: Unit): string {
  if (value === null) return '--';
  if (unit === 'ms') return formatMs(value);
  if (unit === 'fps') return formatFps(value);
  return String(Math.round(value));
}

export default function BaselinePanel() {
  const [labels, setLabels] = useState<string[]>([]);
  const [newLabel, setNewLabel] = useState('');
  const [selected, setSelected] = useState('');
  const [compare, setCompare] = useState<CompareResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshLabels = async () => {
    try {
      const res = await fetch('/api/baseline');
      const data = await res.json();
      setLabels(data.labels ?? []);
    } catch {
      /* keep previous list on transient failure */
    }
  };

  useEffect(() => {
    refreshLabels();
  }, []);

  useEffect(() => {
    if (!selected) {
      setCompare(null);
      return;
    }
    let cancelled = false;
    fetch(`/api/baseline/${encodeURIComponent(selected)}/compare`)
      .then((res) => res.json())
      .then((data) => { if (!cancelled) setCompare(data); })
      .catch(() => { if (!cancelled) setError('Failed to load comparison'); });
    return () => { cancelled = true; };
  }, [selected]);

  const saveBaseline = async () => {
    const label = newLabel.trim();
    if (!label) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/baseline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Failed to save baseline');
      }
      setNewLabel('');
      await refreshLabels();
      setSelected(label);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save baseline');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-title">Before / After Comparison</div>
      <div className="baseline-controls">
        <input
          type="text"
          placeholder="baseline label, e.g. before-model-swap"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
        />
        <button onClick={saveBaseline} disabled={saving || !newLabel.trim()}>
          Save current as baseline
        </button>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Compare against…</option>
          {labels.map((label) => (
            <option key={label} value={label}>{label}</option>
          ))}
        </select>
      </div>

      {error && <div className="empty-hint">{error}</div>}

      {!compare && !error && (
        <div className="empty-hint">
          Save a labeled snapshot now, make a change, then select it above to see live vs. baseline.
        </div>
      )}

      {compare && (
        <table className="compare-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Baseline</th>
              <th>Live</th>
              <th>Δ</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const leaf = getLeaf(compare.diff, row.path);
              if (!leaf || leaf.baseline === null || leaf.live === null) {
                return (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td colSpan={3}>--</td>
                  </tr>
                );
              }
              const improved = row.lowerIsBetter ? leaf.delta < 0 : leaf.delta > 0;
              const worsened = row.lowerIsBetter ? leaf.delta > 0 : leaf.delta < 0;
              const deltaClass = leaf.delta === 0 ? 'delta-flat' : improved ? 'delta-good' : worsened ? 'delta-bad' : 'delta-flat';
              const sign = leaf.delta > 0 ? '+' : '';
              return (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{formatByUnit(leaf.baseline, row.unit)}</td>
                  <td>{formatByUnit(leaf.live, row.unit)}</td>
                  <td className={deltaClass}>
                    {sign}{formatByUnit(leaf.delta, row.unit)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
