import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Droplets, CloudRain, AlertTriangle, CheckCircle, Navigation } from 'lucide-react';
import { getStationHistory, getStationForecast, getAllStationStatus } from '../services/api';
import {
  ComposedChart, Line, ReferenceLine, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { format, parseISO } from 'date-fns';

export default function StationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [station, setStation] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Pull the comprehensive station statuses instead of basic thresholds
        const stationsList = await getAllStationStatus();
        const currentStation = stationsList.find(s => s.station_id === parseInt(id));
        setStation(currentStation);

        const [historyData, forecastData] = await Promise.all([
          getStationHistory(id),
          getStationForecast(id)
        ]);
        
        setHistory(historyData);
        if (!forecastData.error) {
          setForecast(forecastData);
        }
        setLoading(false);
      } catch (err) {
        console.error(err);
        setError("Failed to load station data");
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const chartData = useMemo(() => {
    if (!history.length && !forecast) return [];
    
    // 1. Map historical data
    const data = history.map(h => ({
      time: new Date(h.observed_at).getTime(),
      label: format(new Date(h.observed_at), 'MMM dd, HH:mm'),
      historical: h.water_level,
      predicted: null
    }));

    // 2. Append predictive data from the AI
    if (forecast && forecast.horizons) {
      if (data.length > 0) {
        const lastHist = data[data.length - 1];
        // Connect the prediction line organically from the last historical point
        // Create an intermediate point so the line draws correctly
        data.push({
          time: lastHist.time,
          label: lastHist.label,
          historical: null,
          predicted: lastHist.historical
        });
      }
      
      const predictionTime = new Date(forecast.horizons[0].prediction_time || new Date()).getTime();
      
      forecast.horizons.forEach(h => {
        const futureTime = predictionTime + (h.hours * 3600000);
        data.push({
          time: futureTime,
          label: format(new Date(futureTime), "MMM dd, HH:mm '(AI)'"),
          historical: null,
          predicted: h.predicted_water_level
        });
      });
    }
    
    return data;
  }, [history, forecast]);

  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  );

  if (error || !station) return (
    <div className="h-full flex flex-col items-center justify-center p-8 text-center">
      <AlertTriangle className="w-16 h-16 text-red-500 mb-4 opacity-80" />
      <h2 className="text-2xl font-bold text-white mb-2">Station Error</h2>
      <p className="text-slate-400 mb-6">{error || "Station could not be found."}</p>
      <button onClick={() => navigate('/')} className="px-6 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition text-sm font-medium">Return to Map</button>
    </div>
  );

  const risk3H = forecast?.horizons?.find(h => h.hours === 3)?.risk_class || 'Unknown';
  const risk12H = forecast?.horizons?.find(h => h.hours === 12)?.risk_class || 'Unknown';
  const currentLevel = history.length > 0 ? history[history.length-1].water_level : 0;
  const currentRain = history.length > 0 ? history[history.length-1].rainfall_mm : 0;

  const RiskBadge = ({ risk, hours }) => {
    let color = risk === 'Normal' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 
                risk === 'Minor Flood' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' : 
                'bg-red-500/20 text-red-400 border-red-500/30 font-bold animate-pulse';
                
    const Icon = risk === 'Normal' ? CheckCircle : AlertTriangle;
    
    return (
      <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border ${color}`}>
        <Icon className="w-4 h-4" />
        <span className="text-sm">+{hours}H: {risk}</span>
      </div>
    );
  };

  return (
    <div className="h-full bg-[#0f172a] p-6 lg:p-8 overflow-y-auto">
      {/* Top Bar Navigation */}
      <button 
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6 group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        <span className="text-sm font-medium tracking-wide">Back to Map</span>
      </button>

      {/* Header Profile */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8 pb-8 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">{station.station_name}</h1>
            <span className="px-3 py-1 bg-slate-800 rounded-full text-xs font-semibold text-slate-400 border border-slate-700">
              {station.river_basin || 'Unknown Basin'}
            </span>
          </div>
          <div className="flex items-center gap-4 text-slate-400 text-sm">
            <span className="flex items-center gap-1"><Navigation className="w-4 h-4" /> {station.latitude?.toFixed(4)}, {station.longitude?.toFixed(4)}</span>
            <span className="flex items-center gap-1 text-xs">Model: {forecast?.model_version || 'N/A'}</span>
          </div>
        </div>

        {/* AI Predictions */}
        <div className="flex flex-wrap gap-3">
          <RiskBadge risk={risk3H} hours={3} />
          <RiskBadge risk={risk12H} hours={12} />
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
          <div className="absolute -right-4 -top-4 w-24 h-24 bg-blue-500/10 rounded-full blur-xl"></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Current Water Level</p>
          <div className="flex items-end gap-2">
            <span className="text-4xl font-bold text-white">{currentLevel.toFixed(2)}</span>
            <span className="text-slate-500 mb-1">meters</span>
          </div>
        </div>
        
        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
           <div className="absolute -right-4 -top-4 w-24 h-24 bg-cyan-500/10 rounded-full blur-xl"></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Rainfall (Live / 24H)</p>
          <div className="flex items-end gap-2">
            <span className="text-4xl font-bold text-white">{currentRain.toFixed(1)}</span>
            <span className="text-slate-400 mb-1 font-medium">/ {station.rainfall_24h !== null && station.rainfall_24h !== undefined ? station.rainfall_24h.toFixed(1) : '--'} mm</span>
          </div>
        </div>
        
        <div className="bg-slate-900/50 border border-yellow-900/30 p-5 rounded-2xl">
          <p className="text-slate-400 text-sm font-medium mb-1 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" /> Minor Flood Level
          </p>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-semibold text-yellow-400/90">{station.minor_flood_level || 'N/A'}</span>
            <span className="text-slate-500 mb-1">m</span>
          </div>
        </div>

        <div className="bg-slate-900/50 border border-red-900/30 p-5 rounded-2xl">
          <p className="text-slate-400 text-sm font-medium mb-1 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500" /> Major Flood Level
          </p>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-semibold text-red-400/90">{station.major_flood_level || 'N/A'}</span>
            <span className="text-slate-500 mb-1">m</span>
          </div>
        </div>
      </div>

      {/* Main Chart */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-2xl">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Droplets className="w-5 h-5 text-blue-400" /> 
            Level History & AI Forecast
          </h2>
          <div className="flex items-center gap-4 text-xs font-medium">
             <span className="flex items-center gap-1 text-slate-300"><span className="w-3 h-1 bg-blue-500 rounded"></span> Recorded</span>
             <span className="flex items-center gap-1 text-slate-300"><span className="w-3 h-1 bg-red-500 rounded border-t border-dashed border-red-500 bg-transparent"></span> Predicted</span>
          </div>
        </div>

        <div className="w-full h-[450px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              
              <XAxis 
                dataKey="label" 
                stroke="#64748b" 
                tick={{fill: '#64748b', fontSize: 12}}
                tickMargin={10}
                minTickGap={30}
              />
              
              <YAxis 
                stroke="#64748b" 
                tick={{fill: '#64748b', fontSize: 12}}
                domain={['auto', 'auto']}
                tickFormatter={(val) => val.toFixed(1)}
              />
              
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }}
                itemStyle={{ color: '#e2e8f0' }}
                labelStyle={{ color: '#94a3b8', marginBottom: '8px' }}
              />

              {/* Threshold Lines */}
              {station.minor_flood_level && (
                <ReferenceLine 
                  y={station.minor_flood_level} 
                  stroke="#eab308" 
                  strokeDasharray="4 4" 
                  label={{ position: 'insideTopLeft', value: 'Minor Flood', fill: '#eab308', fontSize: 12 }} 
                />
              )}
              {station.major_flood_level && (
                 <ReferenceLine 
                  y={station.major_flood_level} 
                  stroke="#ef4444" 
                  strokeDasharray="4 4" 
                  label={{ position: 'insideTopLeft', value: 'Major Flood', fill: '#ef4444', fontSize: 12 }} 
                />
              )}

              {/* Data Lines */}
              <Line 
                type="monotone" 
                dataKey="historical" 
                name="Recorded Level"
                stroke="#3b82f6" 
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 6, fill: '#3b82f6', stroke: '#0f172a', strokeWidth: 2 }}
              />
              <Line 
                type="monotone" 
                dataKey="predicted" 
                name="AI Forecast"
                stroke="#f43f5e" 
                strokeWidth={3}
                strokeDasharray="6 4"
                dot={{ r: 4, fill: '#f43f5e', stroke: 'none' }}
                activeDot={{ r: 6, fill: '#f43f5e', stroke: '#0f172a', strokeWidth: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
