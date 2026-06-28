import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  Server,
  Play,
  Plus,
  X,
  FileCode,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Calendar,
  RefreshCw,
} from 'lucide-react';

interface Source {
  source_id: string;
  config_id: string;
  name: string;
  source_type: string;
  connection_details: any;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Configuration {
  config_id: string;
  name: string;
  config_type: string;
  config_subtype: string;
  config_content: any;
  status: string;
  version: number;
}

interface Job {
  job_id: string;
  source_id: string;
  status: string;
  created_at: string;
}

export const Sources: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [selectedConfig, setSelectedConfig] = useState<Configuration | null>(null);

  // Configuration Swapping Modal State
  const [isSwapOpen, setIsSwapOpen] = useState(false);
  const [swappingSource, setSwappingSource] = useState<Source | null>(null);
  const [nextConfigId, setNextConfigId] = useState('');

  // Pre-ingest Configuration Review Modal State
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [reviewSource, setReviewSource] = useState<Source | null>(null);

  // Register Form State
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('GCS');
  const [newConfigId, setNewConfigId] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newConnDetails, setNewConnDetails] = useState('{\n  "bucket_name": "sutherland-landing-bucket",\n  "prefix": "raw-datasets/"\n}');

  // Ingest/Upload Loading States
  const [ingestingId, setIngestingId] = useState<string | null>(null);

  // Success Notification state
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sourcesList, configsList, jobsList] = await Promise.all([
        api.get('/sources'),
        api.get('/configurations'),
        api.get('/jobs'),
      ]);
      setSources(sourcesList);
      // Filter configs to only show config_type === "SOURCE"
      setConfigs((configsList || []).filter((c: any) => c.config_type === 'SOURCE'));
      setJobs(jobsList || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRegisterSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName || !newConfigId) {
      showNotification('Please fill in all required fields', 'error');
      return;
    }

    let parsedConn = {};
    try {
      parsedConn = JSON.parse(newConnDetails);
    } catch (err) {
      showNotification('Connection details must be valid JSON', 'error');
      return;
    }

    try {
      setLoading(true);
      await api.post('/sources', {
        name: newName,
        source_type: newType,
        config_id: newConfigId,
        description: newDesc || null,
        connection_details: parsedConn,
      });

      showNotification('Source registered successfully!');
      setIsRegisterOpen(false);
      // Reset form
      setNewName('');
      setNewDesc('');
      setNewConfigId('');
      fetchData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to register source', 'error');
    } finally {
      setLoading(false);
    }
  };


  const handleTriggerIngest = async (sourceId: string) => {
    setIngestingId(sourceId);
    try {
      const job = await api.post('/ingestions', { source_id: sourceId });
      showNotification(`Ingestion job ${job.job_id.substring(0, 8)} triggered successfully!`);
      // Refresh jobs list to update Last Ingest time
      const jobsList = await api.get('/jobs');
      setJobs(jobsList || []);
    } catch (err: any) {
      showNotification(err.message || 'Failed to trigger ingestion', 'error');
    } finally {
      setIngestingId(null);
    }
  };

  const getLastIngestTime = (sourceId: string) => {
    const sourceJobs = jobs.filter((j) => j.source_id === sourceId);
    if (sourceJobs.length === 0) return 'Never';

    // Find max created_at
    const dates = sourceJobs.map((j) => new Date(j.created_at).getTime());
    const maxTime = Math.max(...dates);
    return new Date(maxTime).toLocaleString();
  };

  // Helper to format JSON preview
  const formatJSON = (json: any) => {
    return JSON.stringify(json, null, 2);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner / Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa' }}>Registered Data Sources</h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Manage database connections, ingestion YAML templates, and trigger jobs.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => {
              if (configs.length === 0) {
                showNotification('Register a configuration template under the Configurations tab first before registering a source', 'error');
              } else {
                setNewConfigId(configs[0].config_id);
                setIsRegisterOpen(true);
              }
            }}
            className="btn"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px' }}
          >
            <Plus size={16} />
            <span>Register Source</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
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

      {/* Main Content Loading / Error / Grid */}
      {loading && sources.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading sources...</span>
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
      ) : sources.length === 0 ? (
        <div
          style={{
            border: '1px dashed #27272a',
            borderRadius: '8px',
            padding: '60px 20px',
            textAlign: 'center',
            backgroundColor: '#18181b',
          }}
        >
          <Server size={40} color="#71717a" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>No Sources Registered</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto' }}>
            Before launching data landing pipelines, you need to register a source connection. Ensure configuration templates are registered under the Configurations tab.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: '20px',
          }}
        >
          {sources.map((source) => (
            <div
              key={source.source_id}
              style={{
                backgroundColor: '#18181b',
                border: '1px solid #27272a',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '20px',
                position: 'relative',
              }}
            >
              {/* Header */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <h3
                    style={{
                      fontSize: '16px',
                      fontWeight: 600,
                      color: '#fafafa',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {source.name}
                  </h3>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      backgroundColor: 'rgba(14, 165, 233, 0.1)',
                      color: '#0ea5e9',
                      border: '1px solid rgba(14, 165, 233, 0.2)',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {source.source_type}
                  </span>
                </div>
                <p
                  style={{
                    color: '#a1a1aa',
                    fontSize: '13px',
                    marginTop: '8px',
                    minHeight: '36px',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {source.description || 'No description provided.'}
                </p>
              </div>

              {/* Ingestion Info */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  borderTop: '1px solid #27272a',
                  paddingTop: '16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#a1a1aa' }}>
                  <Calendar size={14} />
                  <span>Last Ingest:</span>
                  <span style={{ color: '#fafafa', fontWeight: 500 }}>{getLastIngestTime(source.source_id)}</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#a1a1aa' }}>
                  <FileCode size={14} />
                  <span>Template:</span>
                  <button
                    onClick={() => {
                      const cfg = configs.find((c) => c.config_id === source.config_id);
                      if (cfg) {
                        setSelectedConfig(cfg);
                      } else {
                        alert(`Configuration ${source.config_id} details not pre-loaded.`);
                      }
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#0ea5e9',
                      fontWeight: 500,
                      cursor: 'pointer',
                      padding: 0,
                      textDecoration: 'underline',
                    }}
                    title="Click to view full YAML/JSON template configuration"
                  >
                    {configs.find((c) => c.config_id === source.config_id)?.name || (source.config_id || '').substring(0, 8)}
                  </button>
                  <button
                    onClick={() => {
                      setSwappingSource(source);
                      setNextConfigId(source.config_id);
                      setIsSwapOpen(true);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#a1a1aa',
                      cursor: 'pointer',
                      padding: '2px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      transition: 'color 0.15s',
                    }}
                    title="Swap configuration template"
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#0ea5e9')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#a1a1aa')}
                  >
                    <RefreshCw size={12} />
                  </button>
                </div>
              </div>

              {/* Hoverable details panel */}
              <div className="hover-config-parent">
                <span
                  style={{
                    fontSize: '12px',
                    color: '#0ea5e9',
                    cursor: 'pointer',
                    fontWeight: 500,
                    alignSelf: 'flex-start',
                  }}
                >
                  Hover to view Connection JSON
                </span>
                <div className="hover-config-child">
                  <pre
                    style={{
                      margin: 0,
                      padding: '12px',
                      fontSize: '11px',
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      color: '#0ea5e9',
                      overflowX: 'auto',
                      maxHeight: '160px',
                    }}
                  >
                    <code>{formatJSON(source.connection_details)}</code>
                  </pre>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => {
                  setReviewSource(source);
                  setIsReviewOpen(true);
                }}
                disabled={ingestingId === source.source_id}
                className="btn"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  backgroundColor: ingestingId === source.source_id ? '#27272a' : '#0ea5e9',
                  borderColor: ingestingId === source.source_id ? '#27272a' : '#0ea5e9',
                  height: '38px',
                }}
              >
                {ingestingId === source.source_id ? (
                  <>
                    <Loader2 className="animate-spin" size={16} />
                    <span>Triggering...</span>
                  </>
                ) : (
                  <>
                    <Play size={16} fill="currentColor" />
                    <span>Ingest Now</span>
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Register Source */}
      {isRegisterOpen && (
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
              maxWidth: '500px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
            }}
          >
            <button
              onClick={() => setIsRegisterOpen(false)}
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
              Register Source Connection
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Connect a source system to launch automatic ingestion.
            </p>

            <form onSubmit={handleRegisterSource} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label htmlFor="modal-name">Source Name *</label>
                <input
                  id="modal-name"
                  type="text"
                  placeholder="e.g. User Inbound GCS Bucket"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label htmlFor="modal-type">Source Type *</label>
                  <select
                    id="modal-type"
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    style={{
                      width: '100%',
                      height: '38px',
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      color: '#fafafa',
                      padding: '0 12px',
                    }}
                  >
                    <option value="GCS">GCS</option>
                    <option value="FIRESTORE">FIRESTORE</option>
                    <option value="BIGQUERY">BIGQUERY</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="modal-config">YAML Config Template *</label>
                  <select
                    id="modal-config"
                    value={newConfigId}
                    onChange={(e) => setNewConfigId(e.target.value)}
                    style={{
                      width: '100%',
                      height: '38px',
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      color: '#fafafa',
                      padding: '0 12px',
                    }}
                  >
                    {configs.map((c) => (
                      <option key={c.config_id} value={c.config_id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="modal-desc">Description</label>
                <textarea
                  id="modal-desc"
                  rows={2}
                  placeholder="Provide context regarding the data coming from this source..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
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

              <div>
                <label htmlFor="modal-conn">Connection details (JSON) *</label>
                <textarea
                  id="modal-conn"
                  rows={4}
                  value={newConnDetails}
                  onChange={(e) => setNewConnDetails(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#0ea5e9',
                    fontFamily: 'monospace',
                    padding: '10px 12px',
                    fontSize: '12px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <button type="submit" className="btn" style={{ width: '100%', marginTop: '8px', height: '40px' }}>
                Create Source
              </button>
            </form>
          </div>
        </div>
      )}


      {/* Modal: View Configuration Template */}
      {selectedConfig && (
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
              maxWidth: '600px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
              maxHeight: '90vh',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <button
              onClick={() => setSelectedConfig(null)}
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

            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa' }}>
                {selectedConfig.name}
              </h3>
              <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '4px' }}>
                Template Config ID: <span style={{ fontFamily: 'monospace' }}>{selectedConfig.config_id}</span> (v{selectedConfig.version})
              </p>
            </div>

            <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
              <div>
                <span style={{ color: '#71717a' }}>Type: </span>
                <span style={{ color: '#fafafa', fontWeight: 500 }}>{selectedConfig.config_type}</span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>Subtype: </span>
                <span style={{ color: '#fafafa', fontWeight: 500 }}>{selectedConfig.config_subtype}</span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>Status: </span>
                <span style={{ color: '#10b981', fontWeight: 500 }}>{selectedConfig.status}</span>
              </div>
            </div>

            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: '#a1a1aa' }}>Configuration Content (JSON):</span>
              <pre
                style={{
                  margin: 0,
                  padding: '16px',
                  fontSize: '12px',
                  backgroundColor: '#09090b',
                  border: '1px solid #27272a',
                  borderRadius: '6px',
                  color: '#0ea5e9',
                  overflowY: 'auto',
                  flex: 1,
                  fontFamily: 'monospace',
                }}
              >
                <code>{JSON.stringify(selectedConfig.config_content, null, 2)}</code>
              </pre>
            </div>

            <button
              onClick={() => setSelectedConfig(null)}
              className="btn btn-secondary"
              style={{ alignSelf: 'flex-end', height: '36px' }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Modal: Swap Source Config */}
      {isSwapOpen && swappingSource && (
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
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <button
              onClick={() => setIsSwapOpen(false)}
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

            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
              Swap Configuration Template
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
              Select the new ingestion/processing configuration template for source: <strong>{swappingSource.name}</strong>
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <select
                value={nextConfigId}
                onChange={(e) => setNextConfigId(e.target.value)}
                style={{
                  width: '100%',
                  height: '38px',
                  backgroundColor: '#09090b',
                  border: '1px solid #27272a',
                  borderRadius: '6px',
                  color: '#fafafa',
                  padding: '0 12px',
                }}
              >
                {configs.map((c) => (
                  <option key={c.config_id} value={c.config_id}>
                    {c.name}
                  </option>
                ))}
              </select>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsSwapOpen(false)}
                  className="btn btn-secondary"
                  style={{ height: '36px', padding: '0 16px' }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await api.patch(`/sources/${swappingSource.source_id}`, { config_id: nextConfigId });
                      showNotification('Configuration swapped successfully!');
                      setIsSwapOpen(false);
                      fetchData();
                    } catch (err: any) {
                      showNotification(err.message || 'Failed to swap configuration', 'error');
                    }
                  }}
                  className="btn"
                  style={{ height: '36px', padding: '0 16px', backgroundColor: '#0ea5e9', color: '#fff', border: 'none' }}
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Pre-ingestion Active Config Review */}
      {isReviewOpen && reviewSource && (
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
              maxWidth: '520px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <button
              onClick={() => setIsReviewOpen(false)}
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

            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
              Review Ingestion Configuration
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
              Please review the active settings for source <strong>{reviewSource.name}</strong> before triggering the ingestion job.
            </p>

            {(() => {
              const cfg = configs.find((c) => c.config_id === reviewSource.config_id);
              if (!cfg) {
                return (
                  <div style={{ color: '#ef4444', fontSize: '13px' }}>
                    Active configuration details not loaded.
                  </div>
                );
              }

              const content = cfg.config_content || {};
              const dqEnabled = content.data_quality_enabled || false;
              const dqRules = content.data_quality_rules || [];
              const warningTh = content.validation_thresholds?.warning_threshold ?? 0.40;
              const drift = content.drift_thresholds || {};
              const agentic = content.enable_agentic_pipeline || false;

              return (
                <div
                  style={{
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    fontSize: '13px',
                    color: '#a1a1aa',
                  }}
                >
                  <div>
                    <strong style={{ color: '#fafafa' }}>Active Template:</strong> {cfg.name}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <strong style={{ color: '#fafafa' }}>Data Quality Check:</strong>{' '}
                      <span style={{ color: dqEnabled ? '#10b981' : '#71717a', fontWeight: 600 }}>
                        {dqEnabled ? 'ENABLED' : 'DISABLED'}
                      </span>
                    </div>
                    <div>
                      <strong style={{ color: '#fafafa' }}>DQ Rules Configured:</strong>{' '}
                      <span style={{ color: '#fafafa' }}>{dqRules.length}</span>
                    </div>
                    <div>
                      <strong style={{ color: '#fafafa' }}>Validation Warn Limit:</strong>{' '}
                      <span style={{ color: '#fafafa' }}>{warningTh * 100}%</span>
                    </div>
                    <div>
                      <strong style={{ color: '#fafafa' }}>Drift Warn/Critical:</strong>{' '}
                      <span style={{ color: '#fafafa' }}>
                        {drift.warning_threshold ?? 10} / {drift.critical_threshold ?? 30} columns
                      </span>
                    </div>
                  </div>
                  <div>
                    <strong style={{ color: '#fafafa' }}>Pipeline Recommendation Style:</strong>{' '}
                    <span style={{ color: agentic ? '#0ea5e9' : '#71717a', fontWeight: 600 }}>
                      {agentic ? 'Vertex AI Agent' : 'Standard Heuristics'}
                    </span>
                  </div>
                </div>
              );
            })()}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '10px' }}>
              <button
                type="button"
                onClick={() => setIsReviewOpen(false)}
                className="btn btn-secondary"
                style={{ height: '36px', padding: '0 16px' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsReviewOpen(false);
                  handleTriggerIngest(reviewSource.source_id);
                }}
                className="btn"
                style={{ height: '36px', padding: '0 16px', backgroundColor: '#0ea5e9', color: '#fff', border: 'none' }}
              >
                Proceed Ingestion
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
