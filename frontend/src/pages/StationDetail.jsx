import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Droplets, CloudRain, AlertTriangle, CheckCircle, Navigation, BarChart2, Activity } from 'lucide-react';
import { getStationHistory, getStationForecast, getAllStationStatus, getStationAccuracy } from '../services/api';
import {
  ComposedChart, Line, ReferenceLine, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Brush
} from 'recharts';
import { format, parseISO } from 'date-fns';

// Safely convert implicit UTC naive strings from Python to local timestamps
const parseUTC = (dateStr) => {
  if (!dateStr) return new Date();
  if (typeof dateStr !== 'string') return new Date(dateStr);
  return new Date(dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`);
};

export default function StationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [station, setStation] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [accuracy, setAccuracy] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accuracyLoading, setAccuracyLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('history'); // 'history' | 'accuracy'
  const [accuracyHours, setAccuracyHours] = useState(48);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const stationsList = await getAllStationStatus();
        const currentStation = stationsList.find(s => s.station_id === parseInt(id));
        setStation(currentStation);
        const [historyData, forecastData] = await Promise.all([
          getStationHistory(id),
          getStationForecast(id)
        ]);
        setHistory(historyData);
        if (!forecastData.error) setForecast(forecastData);
        setLoading(false);
      } catch (err) {
        console.error(err);
        setError('Failed to load station data');
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  useEffect(() => {
    const fetchAccuracy = async () => {
      try {
        setAccuracyLoading(true);
        const data = await getStationAccuracy(id, accuracyHours);
        setAccuracy(data);
      } catch (e) {
        console.error(e);
      } finally {
        setAccuracyLoading(false);
      }
    };
    if (activeTab === 'accuracy') fetchAccuracy();
  }, [id, activeTab, accuracyHours]);

  // ── History chart data ────────────────────────────────────────────────
  const chartData = useMemo(() => {
    if (!history.length && !forecast) return [];
    const data = history.map(h => ({
      time: parseUTC(h.observed_at).getTime(),
      label: format(parseUTC(h.observed_at), 'MMM dd, HH:mm'),
      historical: h.water_level,
      predicted: null
    }));
    if (forecast && forecast.horizons) {
      if (data.length > 0) {
        const lastHist = data[data.length - 1];
        data.push({ time: lastHist.time, label: lastHist.label, historical: null, predicted: lastHist.historical });
      }
      const predictionTime = parseUTC(forecast.horizons[0].prediction_time || new Date()).getTime();
      forecast.horizons.forEach(h => {
        const futureTime = predictionTime + h.hours * 3600000;
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

  // ── Accuracy chart data ───────────────────────────────────────────────
  const accuracyChartData = useMemo(() => {
    if (!history.length) return { chart: [], stats: null };

    // 1. Filter history to the selected window (accuracyHours)
    const cutoff = Date.now() - accuracyHours * 60 * 60 * 1000;
    const recentHistory = history.filter(h => parseUTC(h.observed_at).getTime() >= cutoff);
    if (!recentHistory.length) return { chart: [], stats: null };

    // 2. Build chart array from filtered history (actual always populated)
    const chart = recentHistory.map(h => ({
      time: parseUTC(h.observed_at).getTime(),
      label: format(parseUTC(h.observed_at), 'MMM dd HH:mm'),
      actual: h.water_level,
      pred3h: null,
      pred12h: null,
    }));

    // 3. For each accuracy prediction, stamp it onto the nearest history bucket
    accuracy.forEach(r => {
      const targetMs = parseUTC(r.target_time).getTime();
      let best = -1;
      let bestDiff = Infinity;
      chart.forEach((pt, i) => {
        const diff = Math.abs(pt.time - targetMs);
        if (diff < bestDiff) { bestDiff = diff; best = i; }
      });
      // Only stamp if within 35 minutes
      if (best >= 0 && bestDiff < 35 * 60 * 1000) {
        if (r.horizon_hours === 3 && r.predicted != null) chart[best].pred3h = r.predicted;
        if (r.horizon_hours === 12 && r.predicted != null) chart[best].pred12h = r.predicted;
      }
    });

    // 4. Stats from accuracy API data
    const errors3h = accuracy.filter(r => r.horizon_hours === 3 && r.error !== null).map(r => r.error);
    const errors12h = accuracy.filter(r => r.horizon_hours === 12 && r.error !== null).map(r => r.error);
    const withMatch = accuracy.filter(r => r.actual !== null).length;
    const coverage = accuracy.length ? Math.round((withMatch / accuracy.length) * 100) : 0;

    const stats = {
      mae3h: errors3h.length ? (errors3h.reduce((a, b) => a + b, 0) / errors3h.length).toFixed(3) : 'N/A',
      mae12h: errors12h.length ? (errors12h.reduce((a, b) => a + b, 0) / errors12h.length).toFixed(3) : 'N/A',
      coverage: Math.min(coverage, 100),
      gapsExist: coverage < 80,
    };

    return { chart, stats };
  }, [accuracy, history, accuracyHours]);


  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  );

  if (error || !station) return (
    <div className="h-full flex flex-col items-center justify-center p-8 text-center">
      <AlertTriangle className="w-16 h-16 text-red-500 mb-4 opacity-80" />
      <h2 className="text-2xl font-bold text-white mb-2">Station Error</h2>
      <p className="text-slate-400 mb-6">{error || 'Station could not be found.'}</p>
      <button onClick={() => navigate('/')} className="px-6 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition text-sm font-medium">Return to Map</button>
    </div>
  );

  const risk3H = forecast?.horizons?.find(h => h.hours === 3)?.risk_class || 'Unknown';
  const risk12H = forecast?.horizons?.find(h => h.hours === 12)?.risk_class || 'Unknown';
  const currentLevel = history.length > 0 ? history[history.length - 1].water_level : 0;
  const currentRain = history.length > 0 ? history[history.length - 1].rainfall_mm : 0;

  const RiskBadge = ({ risk, hours }) => {
    const color = risk === 'Normal' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
      : risk === 'Minor Flood' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30 font-bold animate-pulse';
    const Icon = risk === 'Normal' ? CheckCircle : AlertTriangle;
    return (
      <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border ${color}`}>
        <Icon className="w-4 h-4" />
        <span className="text-sm">+{hours}H: {risk}</span>
      </div>
    );
  };

  const { chart: accChart, stats: accStats } = accuracyChartData;

  return (
    <div className="h-full bg-[#0f172a] p-6 lg:p-8 overflow-y-auto">
      {/* Back */}
      <button onClick={() => navigate('/')} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6 group">
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        <span className="text-sm font-medium tracking-wide">Back to Map</span>
      </button>

      {/* Header */}
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
            <span className="text-slate-400 mb-1 font-medium">/ {station.rainfall_24h != null ? station.rainfall_24h.toFixed(1) : '--'} mm</span>
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

      {/* Tab Switcher */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('history')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all border ${
            activeTab === 'history'
              ? 'bg-blue-600/20 border-blue-500/40 text-blue-300'
              : 'bg-slate-900/50 border-slate-700 text-slate-400 hover:text-white'
          }`}
        >
          <Droplets className="w-4 h-4" /> Level History & Forecast
        </button>
        <button
          onClick={() => setActiveTab('accuracy')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all border ${
            activeTab === 'accuracy'
              ? 'bg-purple-600/20 border-purple-500/40 text-purple-300'
              : 'bg-slate-900/50 border-slate-700 text-slate-400 hover:text-white'
          }`}
        >
          <BarChart2 className="w-4 h-4" /> Forecast Accuracy
        </button>
      </div>

      {/* ── TAB: History & Forecast ── */}
      {activeTab === 'history' && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-2xl">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Droplets className="w-5 h-5 text-blue-400" />
              Level History &amp; AI Forecast
            </h2>
            <div className="flex items-center gap-4 text-xs font-medium">
              <span className="flex items-center gap-1 text-slate-300"><span className="w-3 h-1 bg-blue-500 rounded inline-block"></span> Recorded</span>
              <span className="flex items-center gap-1 text-slate-300"><span className="w-3 h-1 bg-red-500 rounded inline-block"></span> Predicted</span>
            </div>
          </div>
          <div className="w-full h-[450px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} tickMargin={10} minTickGap={30} />
                <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} domain={['auto', 'auto']} tickFormatter={v => v.toFixed(1)} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }} itemStyle={{ color: '#e2e8f0' }} labelStyle={{ color: '#94a3b8', marginBottom: '8px' }} />
                {station.minor_flood_level && <ReferenceLine y={station.minor_flood_level} stroke="#eab308" strokeDasharray="4 4" label={{ position: 'insideTopLeft', value: 'Minor Flood', fill: '#eab308', fontSize: 12 }} />}
                {station.major_flood_level && <ReferenceLine y={station.major_flood_level} stroke="#ef4444" strokeDasharray="4 4" label={{ position: 'insideTopLeft', value: 'Major Flood', fill: '#ef4444', fontSize: 12 }} />}
                <Brush dataKey="label" height={24} stroke="#334155" fill="#0f172a" travellerWidth={8} startIndex={Math.max(0, chartData.length - 48)} />
                <Line type="monotone" dataKey="historical" name="Recorded Level" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: '#3b82f6', stroke: '#0f172a', strokeWidth: 2 }} connectNulls={true} />
                <Line type="monotone" dataKey="predicted" name="AI Forecast" stroke="#f43f5e" strokeWidth={3} strokeDasharray="6 4" dot={{ r: 4, fill: '#f43f5e', stroke: 'none' }} activeDot={{ r: 6, fill: '#f43f5e', stroke: '#0f172a', strokeWidth: 2 }} connectNulls={true} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── TAB: Forecast Accuracy ── */}
      {activeTab === 'accuracy' && (
        <div className="flex flex-col gap-8">
          {/* 3H Horizon Chart */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-red-500" />
                3-Hour Forecast Accuracy
              </h2>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-sm">Window:</span>
                {[24, 48, 72, 168].map(h => (
                  <button
                    key={h}
                    onClick={() => setAccuracyHours(h)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold border transition-all ${
                      accuracyHours === h ? 'bg-red-600/30 border-red-500/50 text-red-300' : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
                    }`}
                  >
                    {h === 168 ? '7D' : `${h}H`}
                  </button>
                ))}
              </div>
            </div>

            {accuracyLoading ? (
              <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-red-500"></div></div>
            ) : accChart.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <BarChart2 className="w-12 h-12 text-slate-600 mb-3" />
                <p className="text-slate-400 font-medium">No 3H data available</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 flex justify-between items-center">
                    <div>
                      <p className="text-slate-500 text-xs font-medium mb-1">Avg 3H Error (MAE)</p>
                      <p className="text-2xl font-bold text-red-400">{accStats.mae3h} m</p>
                    </div>
                  </div>
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 flex justify-between items-center">
                    <div>
                      <p className="text-slate-500 text-xs font-medium mb-1">Data Coverage</p>
                      <p className={`text-2xl font-bold ${accStats.coverage > 90 ? 'text-emerald-400' : 'text-yellow-400'}`}>{accStats.coverage}%</p>
                    </div>
                  </div>
                </div>

                <div className="w-full h-[380px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={accChart} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                      <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} tickMargin={10} minTickGap={40} />
                      <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} domain={['auto', 'auto']} tickFormatter={v => v.toFixed(2)} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }} />
                      <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '12px', paddingTop: '16px' }} />
                      <Brush dataKey="label" height={24} stroke="#334155" fill="#0f172a" travellerWidth={8} />
                      <Line type="monotone" dataKey="actual" name="Actual Recorded" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 5, fill: '#3b82f6' }} />
                      <Line type="monotone" dataKey="pred3h" name="3H AI Prediction" stroke="#f43f5e" strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3, fill: '#f43f5e' }} activeDot={{ r: 4, fill: '#f43f5e' }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>

          {/* 12H Horizon Chart */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-6">
              <Activity className="w-5 h-5 text-amber-500" />
              12-Hour Forecast Accuracy
            </h2>

            {accuracyLoading ? (
              <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-amber-500"></div></div>
            ) : accChart.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center"><p className="text-slate-400">No 12H data available</p></div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                    <p className="text-slate-500 text-xs font-medium mb-1">Avg 12H Error (MAE)</p>
                    <p className="text-2xl font-bold text-amber-400">{accStats.mae12h} m</p>
                  </div>
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                    <p className="text-slate-500 text-xs font-medium mb-1">Gap Detected</p>
                    <p className={`text-2xl font-bold ${accStats.gapsExist ? 'text-yellow-400' : 'text-emerald-400'}`}>{accStats.gapsExist ? 'Yes ⚠️' : 'No ✅'}</p>
                  </div>
                </div>

                <div className="w-full h-[380px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={accChart} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                      <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} tickMargin={10} minTickGap={40} />
                      <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} domain={['auto', 'auto']} tickFormatter={v => v.toFixed(2)} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }} />
                      <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '12px', paddingTop: '16px' }} />
                      <Brush dataKey="label" height={24} stroke="#334155" fill="#0f172a" travellerWidth={8} />
                      <Line type="monotone" dataKey="actual" name="Actual Recorded" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 5, fill: '#3b82f6' }} />
                      <Line type="monotone" dataKey="pred12h" name="12H AI Prediction" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3, fill: '#f59e0b' }} activeDot={{ r: 4, fill: '#f59e0b' }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
