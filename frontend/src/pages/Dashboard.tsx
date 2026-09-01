import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, DashboardSummary, Anomaly } from '../services/api';

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = async () => {
    try {
      const [s, a] = await Promise.all([api.dashboard(), api.anomalies()]);
      setSummary(s);
      setAnomalies(a.slice(0, 10));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const generateDemo = async () => {
    setGenerating(true);
    try {
      await api.generateScenario({
        scenario_type: 'high_load',
        fault_type: 'COOLING_FAILURE',
        injection_time: 125.0,
        seed: 42,
      });
      await load();
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <h2 className="page-title">Engineering Dashboard</h2>
      <div className="controls">
        <button onClick={generateDemo} disabled={generating}>
          {generating ? 'Generating...' : 'Generate Demo (Cooling Failure)'}
        </button>
      </div>
      {summary && (
        <div className="cards">
          <div className="card"><div className="label">Signals Analyzed</div><div className="value">{summary.signals_analyzed}</div></div>
          <div className="card"><div className="label">Scenarios</div><div className="value">{summary.scenarios}</div></div>
          <div className="card"><div className="label">Anomalies</div><div className="value">{summary.anomalies}</div></div>
          <div className="card"><div className="label">High/Critical</div><div className="value">{summary.high_critical_anomalies}</div></div>
          <div className="card"><div className="label">Precision</div><div className="value">{summary.detection_precision?.toFixed(2) ?? '—'}</div></div>
          <div className="card"><div className="label">Recall</div><div className="value">{summary.detection_recall?.toFixed(2) ?? '—'}</div></div>
          <div className="card"><div className="label">Data Quality</div><div className="value">{summary.data_quality_score?.toFixed(0) ?? '—'}%</div></div>
        </div>
      )}
      <section className="section">
        <h3>Recent Anomalies</h3>
        <table>
          <thead>
            <tr><th>Signal</th><th>Type</th><th>Time</th><th>Severity</th><th>Method</th><th></th></tr>
          </thead>
          <tbody>
            {anomalies.map(a => (
              <tr key={a.id}>
                <td>{a.signal}</td>
                <td>{a.anomaly_type}</td>
                <td>{a.start_time.toFixed(1)}s</td>
                <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                <td>{a.detection_method}</td>
                <td><Link to={`/investigation/${a.id}`}>Investigate</Link></td>
              </tr>
            ))}
            {anomalies.length === 0 && <tr><td colSpan={6}>No anomalies yet. Generate a demo scenario.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
