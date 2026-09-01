import { Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import SignalExplorer from './pages/SignalExplorer';
import AnomalyInvestigation from './pages/AnomalyInvestigation';
import Evaluation from './pages/Evaluation';

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Signal Analysis</h1>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/explorer">Signal Explorer</NavLink>
          <NavLink to="/investigation">Investigation</NavLink>
          <NavLink to="/evaluation">Evaluation</NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/explorer" element={<SignalExplorer />} />
          <Route path="/investigation" element={<AnomalyInvestigation />} />
          <Route path="/investigation/:anomalyId" element={<AnomalyInvestigation />} />
          <Route path="/evaluation" element={<Evaluation />} />
        </Routes>
      </main>
    </div>
  );
}
