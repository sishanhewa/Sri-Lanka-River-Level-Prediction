import { useEffect, useState } from 'react';
import { getSystemLogs } from '../services/api';
import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react';

export default function SystemLogViewer() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSystemLogs()
      .then(data => {
        setLogs(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch logs", err);
        setLoading(false);
      });
  }, []);

  // Time formatter handling naive UTC strings from backend
  const formatTime = (isoString) => {
    const utcString = isoString.endsWith('Z') ? isoString : `${isoString}Z`;
    const d = new Date(utcString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' (' + d.toLocaleDateString() + ')';
  };

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg text-slate-100 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          System Sync Audit (24H)
        </h3>
        <span className="text-xs font-semibold bg-blue-500/10 text-blue-400 px-2.5 py-1 rounded-full border border-blue-500/20">
          Live Backend
        </span>
      </div>

      <div className="flex-1 overflow-y-auto pr-2" style={{ maxHeight: '300px' }}>
        {loading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-blue-400"></div>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-slate-500 text-sm text-center py-6">No recent sync logs found.</div>
        ) : (
          <div className="space-y-3">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-700/30">
                <div className="flex items-center gap-3">
                  {log.status === 'success' ? (
                    <CheckCircle className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-400" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-slate-200">{log.status === 'success' ? 'Data Ingestion & AI Predict' : 'Sync Failed'}</p>
                    <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                      <Clock className="w-3 h-3" /> {log.sync_time ? formatTime(log.sync_time) : 'Unknown time'}
                    </p>
                  </div>
                </div>
                <div className="flex space-x-4 text-right">
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Records</span>
                    <span className="text-sm font-semibold text-slate-300">+{log.inserted_records}</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Predictions</span>
                    <span className="text-sm font-semibold text-blue-300">{log.predictions_run}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
