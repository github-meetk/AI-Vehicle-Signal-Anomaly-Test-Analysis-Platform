import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { api, Anomaly, Investigation } from '../services/api';

export default function AnomalyInvestigation() {
  const { anomalyId: paramId } = useParams();
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [selectedId, setSelectedId] = useState(paramId || '');
  const [anomaly, setAnomaly] = useState<Anomaly | null>(null);
  const [signalData, setSignalData] = useState<Record<string, unknown> | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.anomalies().then(a => {
      setAnomalies(a);
      const id = paramId || a[0]?.id;
      if (id) setSelectedId(id);
    });
  }, [paramId]);

  useEffect(() => {
    if (!selectedId) return;
    setInvestigation(null);
    setError('');
    api.anomaly(selectedId).then(setAnomaly).catch(e => setError(e.message));
    api.anomalySignals(selectedId).then(setSignalData).catch(console.error);
  }, [selectedId]);

  const runInvestigation = async () => {
    if (!selectedId) return;
    setInvestigating(true);
    setError('');
    try {
      const result = await api.investigate(selectedId);
      setInvestigation(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Investigation failed');
    } finally {
      setInvestigating(false);
    }
  };

  const windowData = (signalData?.window_data as Array<Record<string, number>>) || [];

  return (
    <div>
      <h2 className="page-title">Anomaly Investigation</h2>
      <div className="controls">
        <select value={selectedId} onChange={e => setSelectedId(e.target.value)}>
          {anomalies.map(a => (
            <option key={a.id} value={a.id}>{a.signal} @ {a.start_time.toFixed(1)}s ({a.severity})</option>
          ))}
        </select>
        <button onClick={runInvestigation} disabled={investigating || !selectedId}>
          {investigating ? 'Investigating...' : 'Run AI Investigation'}
        </button>
      </div>
      {error && <div className="error">{error}</div>}

      {anomaly && (
        <>
          <div className="cards">
            <div className="card"><div className="label">Severity</div><div className="value"><span className={`badge badge-${anomaly.severity}`}>{anomaly.severity}</span></div></div>
            <div className="card"><div className="label">Signal</div><div className="value" style={{ fontSize: '1.1rem' }}>{anomaly.signal}</div></div>
            <div className="card"><div className="label">Time</div><div className="value">{anomaly.start_time.toFixed(1)}s</div></div>
            <div className="card"><div className="label">Observed</div><div className="value">{anomaly.observed_value.toFixed(1)}</div></div>
            <div className="card"><div className="label">Expected Max</div><div className="value">{anomaly.expected_range.max.toFixed(1)}</div></div>
            <div className="card"><div className="label">Detection</div><div className="value" style={{ fontSize: '0.9rem' }}>{anomaly.detection_method}</div></div>
          </div>

          <section className="section">
            <h3>Evidence — Signal Window</h3>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={windowData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
                  <XAxis dataKey="timestamp" stroke="#8b9cb3" />
                  <YAxis stroke="#8b9cb3" />
                  <Tooltip contentStyle={{ background: '#1a2332', border: '1px solid #2d3a4f' }} />
                  <Legend />
                  <Line type="monotone" dataKey="battery_temperature" stroke="#ef4444" dot={false} />
                  <Line type="monotone" dataKey="battery_current" stroke="#3b82f6" dot={false} />
                  <Line type="monotone" dataKey="coolant_temperature" stroke="#22c55e" dot={false} />
                  <ReferenceLine x={anomaly.start_time} stroke="#f59e0b" label="Anomaly" />
                  <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="3 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          {signalData?.evidence && (
            <section className="section">
              <h3>Statistics</h3>
              <pre style={{ background: 'var(--surface)', padding: '1rem', borderRadius: '8px', overflow: 'auto', fontSize: '0.8rem' }}>
                {JSON.stringify(signalData.evidence, null, 2)}
              </pre>
            </section>
          )}
        </>
      )}

      {investigation && (
        <section className="section">
          <h3>AI Investigation Result</h3>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <p><strong>Summary:</strong> {investigation.result.summary}</p>
            <p style={{ marginTop: '0.5rem' }}><strong>Confidence:</strong> {(investigation.result.confidence * 100).toFixed(0)}%</p>
          </div>
          <h3>Observations</h3>
          <ul className="evidence-list">
            {investigation.result.observations.map((o, i) => <li key={i}>{o}</li>)}
          </ul>
          <h3 style={{ marginTop: '1rem' }}>Possible Causes</h3>
          <ul>{investigation.result.possible_causes.map((c, i) => <li key={i}>{c}</li>)}</ul>
          <h3 style={{ marginTop: '1rem' }}>Related Requirements</h3>
          <p>{investigation.result.related_requirements.join(', ') || 'None linked'}</p>
          <h3 style={{ marginTop: '1rem' }}>Recommended Follow-Up Tests</h3>
          <ul>{investigation.result.recommended_followup_tests.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h3 style={{ marginTop: '1rem' }}>Investigation Trace</h3>
          {investigation.trace.map((step, i) => (
            <div key={i} className="trace-step">
              {step.tool} — {step.status} ({step.latency_ms.toFixed(0)}ms)
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
