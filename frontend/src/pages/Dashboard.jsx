import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, AlertTriangle, CheckCircle, Droplets, CloudRain, Clock, ChevronRight } from 'lucide-react';
import { getAllStationStatus } from '../services/api';
import SystemLogViewer from '../components/SystemLogViewer';

export default function Dashboard() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    getAllStationStatus().then(data => {
      setStations(data);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const filteredStations = stations.filter(s => 
    s.station_name.toLowerCase().includes(search.toLowerCase()) || 
    (s.river_basin && s.river_basin.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="flex-1 h-full w-full bg-[#0f172a] p-6 lg:p-8 overflow-y-auto w-full max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8 mt-2">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-cyan-300 mb-2">
            River Observation Data
          </h1>
          <p className="text-sm text-slate-400">Monitoring {stations.length} river gauges across Sri Lanka with AI 12H Risk Forecasts</p>
        </div>

        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="Search station or basin..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-9 pr-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500/50 transition-colors placeholder:text-slate-600"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-10">
          {filteredStations.map(station => {
            
            // UI Color assignment based on Risk Class
            let cardClasses = "bg-slate-800/40 border-slate-700/50 hover:border-blue-500/30";
            let indicator = null;
            
            const maxRisk = station.risk_12h === 'Major Flood' || station.risk_3h === 'Major Flood' 
              ? 'Major Flood' : (station.risk_12h === 'Minor Flood' || station.risk_3h === 'Minor Flood' ? 'Minor Flood' : 'Normal');

            if (maxRisk === 'Major Flood') {
              cardClasses = "bg-slate-800/80 border-red-500/40 shadow-[0_0_15px_rgba(239,68,68,0.15)]";
              indicator = <span className="absolute top-0 right-0 w-16 h-16 overflow-hidden rounded-tr-xl"><span className="absolute transform rotate-45 bg-red-500 text-center text-white font-bold text-[10px] py-1 right-[-35px] top-[15px] w-[140px] shadow-sm">CRITICAL</span></span>;
            } else if (maxRisk === 'Minor Flood') {
               cardClasses = "bg-slate-800/60 border-yellow-500/30";
            }

            return (
              <div 
                key={station.station_id}
                onClick={() => navigate(`/stations/${station.station_id}`)}
                className={`flex flex-col relative rounded-xl border p-5 cursor-pointer transition-all duration-300 hover:bg-slate-800/80 group overflow-hidden ${cardClasses}`}
              >
                {indicator}
                
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-lg text-white group-hover:text-blue-400 transition-colors">{station.station_name}</h3>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">{station.river_basin || 'Unknown Basin'}</p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-blue-500 group-hover:translate-x-1 transition-all" />
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4 mt-auto">
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 flex flex-col justify-between">
                    <p className="text-[10px] text-slate-500 mb-1 flex items-center gap-1 uppercase tracking-widest"><Droplets className="w-3 h-3 text-cyan-400"/> Current Level</p>
                    <p className="text-xl font-semibold text-white">
                      {station.current_level !== null ? station.current_level.toFixed(2) : '--'}
                      <span className="text-xs text-slate-500 font-normal ml-1">m</span>
                    </p>
                  </div>
                  
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 flex flex-col justify-between">
                    <p className="text-[10px] text-slate-500 mb-1 flex items-center gap-1 uppercase tracking-widest"><Clock className="w-3 h-3 text-fuchsia-400"/> +12H AI Predict</p>
                    <p className="text-xl font-semibold text-white">
                      {station.pred_12h !== null ? station.pred_12h.toFixed(2) : '--'}
                      <span className="text-xs text-slate-500 font-normal ml-1">m</span>
                    </p>
                  </div>
                </div>

                <div className="flex justify-between items-end border-t border-slate-700/50 pt-3">
                  <div className="flex flex-col gap-1 text-slate-400 text-xs text-left">
                    <span className="flex items-center gap-1"><CloudRain className="w-3.5 h-3.5 text-blue-300" /> Current Rain: <span className="font-medium text-slate-200">{station.rainfall_mm !== null ? station.rainfall_mm.toFixed(1) : '--'} mm</span></span>
                    <span className="flex items-center gap-1 pl-4.5 text-slate-500">24H Total: <span className="text-slate-300">{station.rainfall_24h !== null ? station.rainfall_24h.toFixed(1) : '--'} mm</span></span>
                  </div>
                  
                  <div className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-md border ${
                    maxRisk === 'Normal' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    maxRisk === 'Minor Flood' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    'bg-red-500/10 text-red-500 border-red-500/20'
                  }`}>
                    {maxRisk === 'Normal' ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                    {maxRisk}
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}
      
      {/* System Logs Section */}
      <div className="pb-10">
        <SystemLogViewer />
      </div>
    </div>
  );
}
