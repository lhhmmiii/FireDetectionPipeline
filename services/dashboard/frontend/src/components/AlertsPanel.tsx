import type { Alert } from '../types';

interface Props {
  alerts: Alert[];
  onClear: () => void;
}

export default function AlertsPanel({ alerts, onClear }: Props) {
  return (
    <div className="alerts-panel">
      <div className="panel-header">
        <h2>Alerts</h2>
        <button className="text-btn" onClick={onClear}>Clear</button>
      </div>
      <div className="alerts-list">
        {alerts.length === 0 ? (
          <div className="alert-empty"><p>No alerts yet</p></div>
        ) : (
          alerts.map((alert) => (
            <div key={alert.id} className={`alert-item ${alert.type}`}>
              <span className="alert-time">{alert.time}</span>
              <span>{alert.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
