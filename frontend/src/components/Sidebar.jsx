import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Map, Activity, AlertTriangle, Settings, RefreshCw } from 'lucide-react';
import { syncArcgisData } from '../services/api';

export default function Sidebar() {
  const location = useLocation();
  
  const navItems = [
    { name: 'Live Map', path: '/', icon: Map },
    { name: 'Analytics', path: '/analytics', icon: Activity },
    { name: 'Alerts', path: '/alerts', icon: AlertTriangle },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const [isSyncing, setIsSyncing] = useState(false);

  const handleManualSync = async () => {
    try {
      setIsSyncing(true);
      const data = await syncArcgisData();
      if (data.status === 'success') {
        alert(`Success! Fetched ${data.inserted_records} raw updates from ArcGIS and automatically fired ${data.predictions_run} fresh AI predictions.`);
        window.location.reload(); // Instantly refresh the page to show the new data
      } else {
        alert(`Warning: The server returned an error during sync.\\nDetails: ${data.message || 'Unknown Error'}`);
      }
    } catch (err) {
      alert(`Critical Error: Could not connect to the Backend Sync API.\\nIt appears the server is offline or the ArcGIS endpoint refused connection.\\nDetails: ${err.message}`);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <aside className="w-64 bg-slate-800/50 backdrop-blur-xl border-r border-slate-700/50 flex flex-col items-center py-6 px-4 z-50 shadow-2xl">
      <div className="flex items-center gap-3 w-full px-2 mb-10">
        <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center flex-shrink-0 border border-blue-500/30">
          <Map className="w-6 h-6 text-blue-400" />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-lg leading-tight tracking-wide text-white">Rivernet AI</span>
          <span className="text-xs text-blue-400 font-medium tracking-wider uppercase">Sri Lanka</span>
        </div>
      </div>

      <nav className="flex-1 w-full space-y-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
          const Icon = item.icon;
          
          return (
            <Link
              key={item.name}
              to={item.path}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl transition-all duration-300 ${
                isActive 
                  ? 'bg-blue-500/15 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]' 
                  : 'text-slate-400 hover:bg-slate-700/30 hover:text-slate-200'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium text-sm">{item.name}</span>
            </Link>
          );
        })}
      </nav>
      
      <div className="w-full mt-auto p-4 rounded-xl bg-slate-800/80 border border-slate-700/50 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-xs font-medium text-slate-300">Live Sync Active</span>
        </div>
        
        <button 
          onClick={handleManualSync}
          disabled={isSyncing}
          className="flex items-center justify-center gap-2 w-full py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Fetching...' : 'Force Sync AI Data'}
        </button>
        
        <p className="text-[10px] text-slate-500 leading-tight text-center">ArcGIS connected. XGBoost v4 running.</p>
      </div>
    </aside>
  );
}
