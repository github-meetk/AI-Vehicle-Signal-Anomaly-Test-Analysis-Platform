import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { api, Scenario } from '../services/api';

const SIGNAL_OPTIONS = [
  'battery_temperature',
  'battery_current',
  'coolant_temperature',
  'battery_voltage',
  'vehicle_speed',
];

export default function SignalExplorer() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState('');
  const [selectedSignals, setSelectedSignals] = useState(['battery_temperature', 'battery_current', 'coolant_temperature']);
  const [data, setData] = useState<Array<Record<string, number>>>([]);
  const [injectionTime, setInjectionTime] = useState<number | null>(null);

  useEffect(() => {
    api.scenarios().then(s => {
      setScenarios(s);
      if (s.length) setScenarioId(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (!scenarioId) return;
    const scenario = scenarios.find(s => s.id === scenarioId);
    setInjectionTime(scenario?.injection_time ?? null);
    api.signalData(scenarioId, selectedSignals.join(','))
      .then(setData)
      .catch(console.error);
  }, [scenarioId, selectedSignals, scenarios]);

  const toggleSignal = (sig: string) => {
    setSelectedSignals(prev =>
      prev.includes(sig) ? prev.filter(s => s !== sig) : [...prev, sig]
    );
  };

  const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#a855f7'];

  return (
    <div>
      <h2 className="page-title">Signal Explorer</h2>
      <div className="controls">
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}>
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.id} ({s.fault_type})</option>
          ))}
        </select>
        {SIGNAL_OPTIONS.map(sig => (
          <label key={sig} style={{ marginRight: '0.75rem' }}>
            <input type="checkbox" checked={selectedSignals.includes(sig)} onChange={() => toggleSignal(sig)} />
            {' '}{sig}
          </label>
        ))}
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
            <XAxis dataKey="timestamp" stroke="#8b9cb3" label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }} />
            <YAxis stroke="#8b9cb3" />
            <Tooltip contentStyle={{ background: '#1a2332', border: '1px solid #2d3a4f' }} />
            <Legend />
            {selectedSignals.map((sig, i) => (
              <Line key={sig} type="monotone" dataKey={sig} stroke={colors[i % colors.length]} dot={false} strokeWidth={2} />
            ))}
            {injectionTime && <ReferenceLine x={injectionTime} stroke="#ef4444" strokeDasharray="5 5" label="Fault" />}
            <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="3 3" label="80°C" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
