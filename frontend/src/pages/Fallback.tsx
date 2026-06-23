import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  FileCode,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  Calendar,
  Layers,
  Database,
  X,
} from 'lucide-react';

interface FallbackRequest {
  request_id: string;
  job_id: string;
  source_id: string;
  drift_score: number;
  reason: string | null;
  request_status: string;
  generated_ddl: string | null;
  created_at: string;
}

export const Fallback: React.FC = () => {
  const [requests, setRequests] = useState<FallbackRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState('PENDING');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected request tracking for modal/actions
  const [selectedReq, setSelectedReq] = useState<FallbackRequest | null>(null);
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);

  // Approve Form State
  const [schemaName, setSchemaName] = useState('fallback_landing');
  const [tableName, setTableName] = useState('');
  const [notes, setNotes] = useState('');

  // Rejection Form State
  const [rejectNotes, setRejectNotes] = useState('');

  // Action Loading
  const [actionLoading, setActionLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchRequests = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.get(`/schema-fallbacks?status=${statusFilter}`);
      setRequests(list || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch fallback requests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  const handleApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq) return;

    setActionLoading(true);
    try {
      const response = await api.post(`/schema-fallbacks/${selectedReq.request_id}/approve`, {
        schema_name: schemaName,
        table_name: tableName || undefined,
        review_notes: notes || undefined,
      });

      showNotification(response.message || 'Schema fallback approved. Target table created.');
      setIsApproveOpen(false);
      setSelectedReq(null);
      setNotes('');
      setTableName('');
      fetchRequests();
    } catch (err: any) {
      showNotification(err.message || 'Failed to approve fallback', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq || !rejectNotes) return;

    setActionLoading(true);
    try {
      await api.post(`/schema-fallbacks/${selectedReq.request_id}/reject`, {
        review_notes: rejectNotes,
      });

      showNotification('Schema fallback request rejected.');
      setIsRejectOpen(false);
      setSelectedReq(null);
      setRejectNotes('');
      fetchRequests();
    } catch (err: any) {
      showNotification(err.message || 'Failed to reject request', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Layers size={22} color="#f59e0b" />
            Fallback Approvals
          </h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Approve database DDL generation when ingestion schema-drift matches exceed fallback criteria.
          </p>
        </div>

        {/* Tab Filters */}
        <div
          style={{
            display: 'flex',
            backgroundColor: '#18181b',
            border: '1px solid #27272a',
            padding: '2px',
            borderRadius: '6px',
          }}
        >
          {['PENDING', 'APPROVED', 'REJECTED'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              style={{
                border: 'none',
                backgroundColor: statusFilter === status ? '#27272a' : 'transparent',
                color: statusFilter === status ? '#fafafa' : '#a1a1aa',
                padding: '6px 12px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background-color 0.15s',
              }}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

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

      {/* Grid listing */}
      {loading && requests.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading requests...</span>
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
      ) : requests.length === 0 ? (
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
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>No Pending Fallbacks</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto' }}>
            Everything is matching or handled. No schema mutations currently require manual approval.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {requests.map((req) => (
            <div
              key={req.request_id}
              style={{
                backgroundColor: '#18181b',
                border: '1px solid #27272a',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
              }}
            >
              {/* Row Summary header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 600, color: '#fafafa', fontFamily: 'monospace' }}>
                      REQ-{req.request_id.substring(0, 8)}
                    </span>
                    <span
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        color: '#ef4444',
                        fontSize: '11px',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        fontWeight: 600,
                      }}
                    >
                      {req.drift_score.toFixed(0)}% Drift
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '6px', display: 'flex', gap: '12px' }}>
                    <span>Job ID: {req.job_id.substring(0, 8)}...</span>
                    <span>•</span>
                    <span>Source ID: {req.source_id.substring(0, 8)}...</span>
                    <span>•</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Calendar size={12} />
                      {new Date(req.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Actions when PENDING */}
                {req.request_status === 'PENDING' && (
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      onClick={() => {
                        setSelectedReq(req);
                        setIsRejectOpen(true);
                      }}
                      className="btn btn-secondary"
                      style={{ borderColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', height: '34px', fontSize: '12px' }}
                    >
                      <XCircle size={14} />
                      <span>Reject</span>
                    </button>

                    <button
                      onClick={() => {
                        setSelectedReq(req);
                        setTableName(`landing_fallback_${req.request_id.substring(0, 8)}`);
                        setIsApproveOpen(true);
                      }}
                      className="btn"
                      style={{ height: '34px', fontSize: '12px', backgroundColor: '#10b981', borderColor: '#10b981' }}
                    >
                      <CheckCircle size={14} />
                      <span>Approve & Land</span>
                    </button>
                  </div>
                )}
              </div>

              {/* DDL Code Box */}
              {req.generated_ddl && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '12px', color: '#a1a1aa', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileCode size={14} />
                    <span>Generated SQL Schema DDL:</span>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: '16px',
                      fontSize: '12px',
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      color: '#0ea5e9',
                      overflowX: 'auto',
                      maxHeight: '200px',
                    }}
                  >
                    <code>{req.generated_ddl}</code>
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal: Approve & Land fallback table */}
      {isApproveOpen && selectedReq && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.8)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '480px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
            }}
          >
            <button
              onClick={() => {
                setIsApproveOpen(false);
                setSelectedReq(null);
              }}
              style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                background: 'none',
                border: 'none',
                color: '#71717a',
                cursor: 'pointer',
              }}
            >
              <X size={20} />
            </button>

            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
              Approve Schema Landing Table
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Configure destination settings for the fallback schema table generation.
            </p>

            <form onSubmit={handleApprove} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label htmlFor="app-schema">Target Schema Name</label>
                <input
                  id="app-schema"
                  type="text"
                  placeholder="fallback_landing"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label htmlFor="app-table">Target Table Name</label>
                <input
                  id="app-table"
                  type="text"
                  placeholder="e.g. landing_fallback_uuid"
                  value={tableName}
                  onChange={(e) => setTableName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label htmlFor="app-notes">Approval Review Notes</label>
                <textarea
                  id="app-notes"
                  rows={3}
                  placeholder="Notes detailing why this high-drift schema is approved..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#fafafa',
                    padding: '8px 12px',
                    fontSize: '13px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={actionLoading}
                className="btn"
                style={{
                  width: '100%',
                  marginTop: '8px',
                  height: '40px',
                  backgroundColor: '#10b981',
                  borderColor: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {actionLoading ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <>
                    <Database size={16} />
                    <span>Generate Landing Table</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reject fallback table */}
      {isRejectOpen && selectedReq && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.8)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '450px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
            }}
          >
            <button
              onClick={() => {
                setIsRejectOpen(false);
                setSelectedReq(null);
              }}
              style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                background: 'none',
                border: 'none',
                color: '#71717a',
                cursor: 'pointer',
              }}
            >
              <X size={20} />
            </button>

            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
              Reject Schema Fallback Request
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Indicate why the schema changes are rejected.
            </p>

            <form onSubmit={handleReject} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label htmlFor="rej-notes">Rejection Reason Notes *</label>
                <textarea
                  id="rej-notes"
                  rows={4}
                  placeholder="e.g. Critical fields like user_id are unmapped or missing, please contact source system owner..."
                  value={rejectNotes}
                  onChange={(e) => setRejectNotes(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#fafafa',
                    padding: '10px 12px',
                    fontSize: '13px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={actionLoading || !rejectNotes}
                className="btn"
                style={{
                  width: '100%',
                  marginTop: '8px',
                  height: '40px',
                  backgroundColor: '#ef4444',
                  borderColor: '#ef4444',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {actionLoading ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <>
                    <XCircle size={16} />
                    <span>Reject Request</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
