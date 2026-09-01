import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api } from '../services/api';

export default function Evaluation() {
  const [metrics, setMetrics] = useState<Array<Record<string, number | string>>>([]);
  const [aiEval, setAiEval] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.evaluation()
      .then(data => {
        setMetrics(data.detection_metrics || []);
        setAiEval(data.ai_evaluation || {});
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading evaluation data...</p>;

  const chartData = metrics.map(m => ({
    method: m.method,
    precision: Number(m.precision),
    recall: Number(m.recall),
    f1: Number(m.f1),
    fpr: Number(m.false_positive_rate),
    latency: Number(m.avg_detection_latency),
  }));

  return (
    <div>
      <h2 className="page-title">Detection Evaluation</h2>
      {metrics.length === 0 ? (
        <div>
          <p>No evaluation results yet. Run: <code>python -m evaluation.run</code></p>
        </div>
      ) : (
        <>
          <table style={{ marginBottom: '2rem' }}>
            <thead>
              <tr>
                <th>Method</th><th>Precision</th><th>Recall</th><th>F1</th>
                <th>False Positive Rate</th><th>Avg Latency (s)</th><th>Fault Type Acc.</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(m => (
                <tr key={String(m.method)}>
                  <td>{m.method}</td>
                  <td>{Number(m.precision).toFixed(4)}</td>
                  <td>{Number(m.recall).toFixed(4)}</td>
                  <td>{Number(m.f1).toFixed(4)}</td>
                  <td>{Number(m.false_positive_rate).toFixed(4)}</td>
                  <td>{Number(m.avg_detection_latency).toFixed(2)}</td>
                  <td>{m.fault_type_accuracy != null ? Number(m.fault_type_accuracy).toFixed(4) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
                <XAxis dataKey="method" stroke="#8b9cb3" />
                <YAxis stroke="#8b9cb3" domain={[0, 1]} />
                <Tooltip contentStyle={{ background: '#1a2332', border: '1px solid #2d3a4f' }} />
                <Legend />
                <Bar dataKey="precision" fill="#3b82f6" />
                <Bar dataKey="recall" fill="#22c55e" />
                <Bar dataKey="f1" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      <section className="section">
        <h3>AI Investigation Evaluation</h3>
        {Object.keys(aiEval).length > 0 ? (
          <div className="cards">
            <div className="card"><div className="label">Evidence Grounding</div><div className="value">{((aiEval.evidence_grounding_rate as number) * 100).toFixed(0)}%</div></div>
            <div className="card"><div className="label">Signal Correctness</div><div className="value">{((aiEval.signal_correctness_rate as number) * 100).toFixed(0)}%</div></div>
            <div className="card"><div className="label">Requirement Linkage</div><div className="value">{((aiEval.requirement_linkage_rate as number) * 100).toFixed(0)}%</div></div>
            <div className="card"><div className="label">Hallucination Rate</div><div className="value">{((aiEval.hallucination_rate as number) * 100).toFixed(0)}%</div></div>
          </div>
        ) : (
          <p>Run evaluation benchmark to generate AI metrics.</p>
        )}
        {aiEval.methodology ? (
          <p style={{ marginTop: '1rem', color: 'var(--muted)', fontSize: '0.9rem' }}>
            {String(aiEval.methodology)}
          </p>
        ) : null}
      </section>
    </div>
  );
}
