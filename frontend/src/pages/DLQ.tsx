import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  AlertTriangle,
  RotateCcw,
  Flame,
  Loader2,
  Calendar,
  CheckCircle,
} from 'lucide-react';

interface Job {
  job_id: string;
  source_id: string;
  status: string;
  current_stage: string | null;
  retry_count: number;
  parent_job_id: string | null;
  error_message: string | null;
  created_at: string;
  job_type?: string;
}

export const DLQ: React.FC = () => {
  const [failedJobs, setFailedJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Recovery trigger loading indicators
  const [actioningJobId, setActioningJobId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchFailedJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      // Fetch jobs and filter by FAILED status
      const data = await api.get('/jobs?status=FAILED');
      // Sort by creation date descending
      const sorted = (data || []).sort(
        (a: Job, b: Job) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setFailedJobs(sorted);
    } catch (err: any) {
      setError(err.message || 'Failed to load Dead Letter Queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFailedJobs();
  }, []);

  const handleRetry = async (jobId: string) => {
    setActioningJobId(jobId);
    try {
      const response = await api.post(`/jobs/${jobId}/retry`);
      showNotification(`Job successfully retried. New Job ID: ${response.job_id.substring(0, 8)}`);
      fetchFailedJobs();
    } catch (err: any) {
      showNotification(err.message || 'Failed to retry job', 'error');
    } finally {
      setActioningJobId(null);
    }
  };

  const handleKill = async (jobId: string) => {
    if (!confirm('Are you sure you want to permanently cancel this failed job?')) return;
    setActioningJobId(jobId);
    try {
      await api.post(`/jobs/${jobId}/kill`);
      showNotification('Job permanently cancelled (Killed).');
      fetchFailedJobs();
    } catch (err: any) {
      showNotification(err.message || 'Failed to kill job', 'error');
    } finally {
      setActioningJobId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle color="#ef4444" size={24} />
            Dead Letter Queue (DLQ)
          </h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Audit broken landing pipelines, review infrastructure failure reasons, and execute manual recovery routines.
          </p>
        </div>
        <button
          onClick={fetchFailedJobs}
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

      {/* Alert Banner */}
      {notification && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: notification.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${notification.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            borderRadius: '6px',
            padding: '12px 16px',
            fontSize: '14px',
            color: notification.type === 'success' ? '#10b981' : '#ef4444',
          }}
        >
          {notification.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Table grid */}
      {loading && failedJobs.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading failures...</span>
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
      ) : failedJobs.length === 0 ? (
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
          <CheckCircle size={40} color="#10b981" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>Dead Letter Queue is Empty</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto' }}>
            All pipelines are operating normally. No dead letters or failed jobs currently require attention.
          </p>
        </div>
      ) : (
        <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#27272a', color: '#fafafa', borderBottom: '1px solid #27272a' }}>
                <th style={{ padding: '16px 20px', fontWeight: 600 }}>Job Reference</th>
                <th style={{ padding: '16px 20px', fontWeight: 600 }}>Source System ID</th>
                <th style={{ padding: '16px 20px', fontWeight: 600 }}>Failed Stage</th>
                <th style={{ padding: '16px 20px', fontWeight: 600 }}>Error Details</th>
                <th style={{ padding: '16px 20px', fontWeight: 600 }}>Timestamp</th>
                <th style={{ padding: '16px 20px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {failedJobs.map((job) => (
                <tr
                  key={job.job_id}
                  style={{
                    borderBottom: '1px solid #27272a',
                    borderLeft: job.job_type === 'QUALITY' ? '3px solid #f43f5e' : 'none',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.01)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  {/* Job ID */}
                  <td style={{ padding: '16px 20px', fontWeight: 500, fontFamily: 'monospace', color: '#fafafa' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>JOB-{job.job_id.substring(0, 8)}</span>
                      {job.job_type === 'QUALITY' && (
                        <span
                          style={{
                            fontSize: '9px',
                            fontWeight: 700,
                            backgroundColor: 'rgba(244, 63, 94, 0.12)',
                            color: '#f43f5e',
                            border: '1px solid rgba(244, 63, 94, 0.25)',
                            padding: '1px 5px',
                            borderRadius: '3px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                          }}
                        >
                          Quality Check
                        </span>
                      )}
                    </div>
                  </td>
                  {/* Source ID */}
                  <td style={{ padding: '16px 20px', color: '#a1a1aa' }}>
                    {job.source_id.substring(0, 8)}...
                  </td>
                  {/* Failed Stage */}
                  <td style={{ padding: '16px 20px' }}>
                    <span
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        color: '#ef4444',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                    >
                      {job.current_stage || 'Unknown Stage'}
                    </span>
                  </td>
                  {/* Error message */}
                  <td
                    style={{
                      padding: '16px 20px',
                      color: '#a1a1aa',
                      maxWidth: '300px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={job.error_message || ''}
                  >
                    {job.error_message || 'None reported.'}
                  </td>
                  {/* Timestamp */}
                  <td style={{ padding: '16px 20px', color: '#a1a1aa' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Calendar size={14} />
                      <span>{new Date(job.created_at).toLocaleString()}</span>
                    </div>
                  </td>
                  {/* Actions */}
                  <td style={{ padding: '16px 20px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      {/* Retry */}
                      <button
                        onClick={() => handleRetry(job.job_id)}
                        disabled={actioningJobId !== null}
                        className="btn"
                        style={{
                          backgroundColor: '#f59e0b',
                          borderColor: '#f59e0b',
                          color: '#09090b',
                          padding: '6px 12px',
                          fontSize: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          height: '30px',
                        }}
                      >
                        {actioningJobId === job.job_id ? (
                          <Loader2 className="animate-spin" size={14} />
                        ) : (
                          <RotateCcw size={14} />
                        )}
                        <span>Retry</span>
                      </button>

                      {/* Kill */}
                      <button
                        onClick={() => handleKill(job.job_id)}
                        disabled={actioningJobId !== null}
                        className="btn btn-secondary"
                        style={{
                          padding: '6px 12px',
                          fontSize: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          borderColor: 'rgba(239, 68, 68, 0.2)',
                          color: '#ef4444',
                          height: '30px',
                        }}
                      >
                        <Flame size={14} />
                        <span>Kill</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
