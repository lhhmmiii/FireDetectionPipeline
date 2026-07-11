import { useMetricsSocket } from './hooks/useMetricsSocket';
import Header from './components/Header';
import KpiRow from './components/KpiRow';
import StageLatencyPanel from './components/StageLatencyPanel';
import ThroughputPanel from './components/ThroughputPanel';
import KafkaTransitPanel from './components/KafkaTransitPanel';
import DroppedFramesPanel from './components/DroppedFramesPanel';
import BaselinePanel from './components/BaselinePanel';

const WS_URL = `ws://${window.location.host}/ws/metrics`;

export default function App() {
  const { connected, snapshot } = useMetricsSocket(WS_URL);

  return (
    <div className="app">
      <Header connected={connected} windowSeconds={snapshot?.window_seconds ?? null} />
      <main className="main-content">
        <KpiRow snapshot={snapshot} />
        <div className="panels-grid">
          <StageLatencyPanel snapshot={snapshot} />
          <ThroughputPanel snapshot={snapshot} />
          <KafkaTransitPanel snapshot={snapshot} />
          <DroppedFramesPanel snapshot={snapshot} />
        </div>
        <BaselinePanel />
      </main>
    </div>
  );
}
