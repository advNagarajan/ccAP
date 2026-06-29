import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  History,
  Calendar,
  User,
  AlertTriangle,
  Loader2,
  Terminal,
  RotateCcw,
} from 'lucide-react';

interface AuditLog {
  log_id: string;
  user_email: string;
  action: string;
  details: any;
  created_at: string;
}

export const Audit: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get('/audit-logs');
      // Sort logs by date descending
      const sorted = (data || []).sort(
        (a: AuditLog, b: AuditLog) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setLogs(sorted);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch system audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const formatJSON = (json: any) => {
    return JSON.stringify(json, null, 2);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <History size={22} color="#8b5cf6" />
            System Audit Logs
          </h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Chronological record of manual engineering actions, operations, and schema mutations.
          </p>
        </div>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="btn btn-secondary"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '36px',
            padding: '0 16px',
            fontSize: '13px',
          }}
        >
          <RotateCcw size={14} className={loading ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      </div>

      {loading && logs.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading audit records...</span>
        </div>
      ) : error ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.05)',
            border: '1px solid rgba(239, 68, 68, 0.1)',
            color: '#ef4444',
            padding: '16px',
            borderRadius: '6px',
          }}
        >
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      ) : logs.length === 0 ? (
        <div
          style={{
            border: '1px dashed #27272a',
            borderRadius: '8px',
            padding: '60px 20px',
            textAlign: 'center',
            backgroundColor: '#18181b',
            color: '#a1a1aa',
          }}
        >
          <History size={40} color="#71717a" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>No Audit Logs</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto' }}>
            System logs recording manual recoveries or structural overrides will populate here as events occur.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {logs.map((log) => (
            <div
              key={log.log_id}
              style={{
                backgroundColor: '#18181b',
                border: '1px solid #27272a',
                borderRadius: '8px',
                padding: '20px 24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              {/* Timeline row header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      backgroundColor: 'rgba(139, 92, 246, 0.1)',
                      color: '#a78bfa',
                      border: '1px solid rgba(139, 92, 246, 0.2)',
                      padding: '3px 10px',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {log.action}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#fafafa', fontWeight: 500 }}>
                    <User size={14} color="#71717a" />
                    <span>{log.user_email}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#a1a1aa' }}>
                  <Calendar size={14} />
                  <span>{new Date(log.created_at).toLocaleString()}</span>
                </div>
              </div>

              {/* Log Context Metadata Details */}
              {log.details && Object.keys(log.details).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>
                    <Terminal size={12} />
                    <span>Action Parameters</span>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: '10px 14px',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      color: '#a78bfa',
                      overflowX: 'auto',
                    }}
                  >
                    <code>{formatJSON(log.details)}</code>
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
