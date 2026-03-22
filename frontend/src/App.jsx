import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import StationDetail from './pages/StationDetail';

function App() {
  return (
    <div className="flex h-screen w-full bg-[#0f172a] text-slate-100 font-sans overflow-hidden">
      <Sidebar />
      <main className="flex-1 h-full relative overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stations/:id" element={<StationDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
