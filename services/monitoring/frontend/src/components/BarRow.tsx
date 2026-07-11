interface Props {
  label: string;
  color: string;
  value: number | null;
  marker?: number | null;
  maxValue: number;
  valueText: string;
  markerText?: string;
}

/** A single hand-rolled horizontal bar row: label, track+fill(+marker), value. */
export default function BarRow({ label, color, value, marker, maxValue, valueText, markerText }: Props) {
  const pct = value !== null && maxValue > 0 ? Math.min(100, (value / maxValue) * 100) : 0;
  const markerPct = marker !== null && marker !== undefined && maxValue > 0
    ? Math.min(100, (marker / maxValue) * 100)
    : null;

  return (
    <div className="bar-row">
      <div className="bar-row-label">{label}</div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
        {markerPct !== null && (
          <div className="bar-marker" style={{ left: `calc(${markerPct}% - 1px)` }} title={markerText} />
        )}
      </div>
      <div className="bar-row-value">
        {valueText}
        {markerText && <span className="secondary"> / {markerText}</span>}
      </div>
    </div>
  );
}
