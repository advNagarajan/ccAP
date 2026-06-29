import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  Sliders,
  Upload,
  Eye,
  Edit,
  Trash2,
  X,
  Check,
  AlertTriangle,
  Loader2,
  FileCode,
  SlidersHorizontal,
  RotateCcw,
} from 'lucide-react';

interface Configuration {
  config_id: string;
  name: string;
  description: string | null;
  config_type: string;
  config_subtype: string | null;
  config_content: any;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export const Configurations: React.FC = () => {
  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal States
  const [selectedConfig, setSelectedConfig] = useState<Configuration | null>(null);
  const [editingConfig, setEditingConfig] = useState<Configuration | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Form States for Upload
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Form States for Editing
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editContent, setEditContent] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Notification State
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get('/configurations');
      // Sort configurations by updated_at descending
      const sorted = (data || []).sort(
        (a: any, b: any) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setConfigs(sorted);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch configurations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleConfigUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      await api.post('/configurations', formData);
      showNotification('Configuration YAML uploaded successfully!');
      setIsUploadOpen(false);
      setUploadFile(null);
      fetchConfigs();
    } catch (err: any) {
      showNotification(err.message || 'Failed to upload YAML config', 'error');
    } finally {
      setUploading(false);
    }
  };

  const startEditConfig = (config: Configuration) => {
    setEditingConfig(config);
    setEditName(config.name);
    setEditDescription(config.description || '');
    setEditContent(JSON.stringify(config.config_content, null, 2));
    setEditError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingConfig) return;
    setEditError(null);

    // Validate JSON
    let parsedContent = {};
    try {
      parsedContent = JSON.parse(editContent);
    } catch (e: any) {
      setEditError(`Invalid JSON structure: ${e.message}`);
      return;
    }

    if (!editName.trim()) {
      setEditError('Name is required');
      return;
    }

    setSaving(true);
    try {
      await api.patch(`/configurations/${editingConfig.config_id}`, {
        name: editName,
        description: editDescription || null,
        config_content: parsedContent,
      });
      showNotification('Configuration updated successfully!');
      setEditingConfig(null);
      fetchConfigs();
    } catch (err: any) {
      setEditError(err.message || 'Failed to update configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfig = async (configId: string) => {
    if (!window.confirm('Are you sure you want to delete this configuration?')) return;
    try {
      await api.delete(`/configurations/${configId}`);
      showNotification('Configuration deleted successfully!');
      fetchConfigs();
    } catch (err: any) {
      showNotification(err.message || 'Failed to delete configuration', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', position: 'relative' }}>
      {/* Toast Notification */}
      {notification && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            backgroundColor: notification.type === 'success' ? '#10b981' : '#ef4444',
            color: '#fff',
            padding: '12px 24px',
            borderRadius: '6px',
            zIndex: 99999,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
          }}
        >
          {notification.type === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}
          <span style={{ fontSize: '14px', fontWeight: 500 }}>{notification.message}</span>
        </div>
      )}

      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sliders size={22} color="#0ea5e9" />
            Ingestion & Processing Configurations
          </h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            View, upload, and update templates containing validation rules, drift thresholds, and data quality checks.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={fetchConfigs}
            disabled={loading}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', height: '36px' }}
          >
            <RotateCcw size={14} className={loading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="btn"
            style={{
              height: '36px',
              padding: '0 16px',
              backgroundColor: '#0ea5e9',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Upload size={14} />
            <span>Upload YAML Configuration</span>
          </button>
        </div>
      </div>

      {loading && configs.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading configurations...</span>
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
      ) : configs.length === 0 ? (
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
          <SlidersHorizontal size={40} color="#71717a" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>No Configurations Found</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto' }}>
            Click the upload button to ingest a new YAML processing configuration template.
          </p>
        </div>
      ) : (
        /* Configuration Table */
        <div
          style={{
            backgroundColor: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #27272a', backgroundColor: '#1c1c1f', color: '#a1a1aa' }}>
                <th style={{ padding: '14px 20px' }}>Name / ID</th>
                <th style={{ padding: '14px 20px' }}>Type</th>
                <th style={{ padding: '14px 20px' }}>Subtype</th>
                <th style={{ padding: '14px 20px' }}>Version</th>
                <th style={{ padding: '14px 20px' }}>Status</th>
                <th style={{ padding: '14px 20px' }}>Updated</th>
                <th style={{ padding: '14px 20px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {configs.map((config) => (
                <tr
                  key={config.config_id}
                  style={{ borderBottom: '1px solid #27272a', color: '#a1a1aa', transition: 'background-color 0.15s' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.01)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '14px 20px' }}>
                    <div style={{ fontWeight: 600, color: '#fafafa' }}>{config.name}</div>
                    <div style={{ fontSize: '11px', color: '#71717a', fontFamily: 'monospace', marginTop: '2px' }}>
                      {config.config_id}
                    </div>
                  </td>
                  <td style={{ padding: '14px 20px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        backgroundColor: config.config_type === 'SOURCE' ? 'rgba(14, 165, 233, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                        color: config.config_type === 'SOURCE' ? '#38bdf8' : '#34d399',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontWeight: 600,
                      }}
                    >
                      {config.config_type}
                    </span>
                  </td>
                  <td style={{ padding: '14px 20px', color: '#fafafa' }}>
                    {config.config_subtype || 'N/A'}
                  </td>
                  <td style={{ padding: '14px 20px' }}>v{config.version}</td>
                  <td style={{ padding: '14px 20px' }}>
                    <span style={{ color: config.status === 'ACTIVE' ? '#10b981' : '#71717a', fontWeight: 500 }}>
                      {config.status}
                    </span>
                  </td>
                  <td style={{ padding: '14px 20px' }}>
                    {new Date(config.updated_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '14px 20px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => setSelectedConfig(config)}
                        title="View raw configuration"
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '6px',
                          borderRadius: '6px',
                          color: '#a1a1aa',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <Eye size={16} />
                      </button>
                      <button
                        onClick={() => startEditConfig(config)}
                        title="Edit configuration parameters"
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '6px',
                          borderRadius: '6px',
                          color: '#0ea5e9',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <Edit size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteConfig(config.config_id)}
                        title="Delete configuration"
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '6px',
                          borderRadius: '6px',
                          color: '#ef4444',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal: View Configuration Detail */}
      {selectedConfig && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '12px',
              padding: '30px',
              width: '600px',
              maxWidth: '90%',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  {selectedConfig.name}
                </h3>
                <span style={{ fontSize: '11px', color: '#71717a', fontFamily: 'monospace' }}>
                  {selectedConfig.config_id} (v{selectedConfig.version})
                </span>
              </div>
              <button
                onClick={() => setSelectedConfig(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#71717a',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <X size={16} />
              </button>
            </div>

            {selectedConfig.description && (
              <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
                {selectedConfig.description}
              </p>
            )}

            <div style={{ flex: 1, overflowY: 'auto' }}>
              <pre
                style={{
                  margin: 0,
                  padding: '16px',
                  backgroundColor: '#09090b',
                  border: '1px solid #27272a',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#0ea5e9',
                  overflowX: 'auto',
                }}
              >
                <code>{JSON.stringify(selectedConfig.config_content, null, 2)}</code>
              </pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setSelectedConfig(null)}
                className="btn-secondary"
                style={{
                  height: '36px',
                  padding: '0 16px',
                  fontSize: '13px',
                  borderRadius: '6px',
                  border: '1px solid #27272a',
                  backgroundColor: 'transparent',
                  color: '#fafafa',
                  cursor: 'pointer',
                }}
              >
                Close View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Edit Configuration */}
      {editingConfig && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '12px',
              padding: '30px',
              width: '650px',
              maxWidth: '90%',
              maxHeight: '90vh',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  Edit Configuration Template
                </h3>
                <span style={{ fontSize: '11px', color: '#71717a', fontFamily: 'monospace' }}>
                  ID: {editingConfig.config_id}
                </span>
              </div>
              <button
                onClick={() => setEditingConfig(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#71717a',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <X size={16} />
              </button>
            </div>

            {editError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'rgba(239, 68, 68, 0.05)',
                  border: '1px solid rgba(239, 68, 68, 0.1)',
                  color: '#ef4444',
                  padding: '12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                }}
              >
                <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                <span>{editError}</span>
              </div>
            )}

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '4px' }}>
              {/* Name Field */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: '#a1a1aa', fontWeight: 600 }}>Configuration Name *</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  style={{
                    height: '38px',
                    padding: '0 12px',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#fafafa',
                    fontSize: '13px',
                  }}
                />
              </div>

              {/* Description Field */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: '#a1a1aa', fontWeight: 600 }}>Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={2}
                  style={{
                    padding: '10px 12px',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#fafafa',
                    fontSize: '13px',
                    resize: 'vertical',
                    fontFamily: 'sans-serif',
                  }}
                />
              </div>

              {/* Raw JSON Config Content Field */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
                <label style={{ fontSize: '12px', color: '#a1a1aa', fontWeight: 600 }}>Configuration Parameters (JSON) *</label>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  style={{
                    flex: 1,
                    minHeight: '220px',
                    padding: '12px',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#a78bfa',
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    resize: 'vertical',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setEditingConfig(null)}
                disabled={saving}
                className="btn-secondary"
                style={{
                  height: '36px',
                  padding: '0 16px',
                  fontSize: '13px',
                  borderRadius: '6px',
                  border: '1px solid #27272a',
                  backgroundColor: 'transparent',
                  color: '#fafafa',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={saving}
                className="btn"
                style={{
                  height: '36px',
                  padding: '0 16px',
                  fontSize: '13px',
                  borderRadius: '6px',
                  backgroundColor: '#0ea5e9',
                  color: '#fff',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {saving ? (
                  <>
                    <Loader2 className="animate-spin" size={14} />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Check size={14} />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Upload Configuration YAML */}
      {isUploadOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '12px',
              padding: '30px',
              width: '450px',
              maxWidth: '90%',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Upload size={20} color="#0ea5e9" />
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  Upload Configuration YAML
                </h3>
              </div>
              <button
                onClick={() => {
                  setIsUploadOpen(false);
                  setUploadFile(null);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#71717a',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <X size={16} />
              </button>
            </div>

            <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
              Upload a `.yaml` or `.yml` config file containing your parsing, validation thresholds, and data quality check rules.
            </p>

            <form onSubmit={handleConfigUpload} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div
                style={{
                  border: '2px dashed #27272a',
                  borderRadius: '8px',
                  padding: '30px 20px',
                  textAlign: 'center',
                  backgroundColor: '#09090b',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s',
                }}
                onClick={() => document.getElementById('config-file-input')?.click()}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#0ea5e9')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#27272a')}
              >
                <input
                  type="file"
                  id="config-file-input"
                  accept=".yaml,.yml"
                  style={{ display: 'none' }}
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
                <FileCode size={32} color="#71717a" style={{ margin: '0 auto 12px' }} />
                {uploadFile ? (
                  <div style={{ color: '#0ea5e9', fontWeight: 600, fontSize: '13px' }}>{uploadFile.name}</div>
                ) : (
                  <>
                    <div style={{ color: '#fafafa', fontWeight: 500, fontSize: '13px' }}>Click to select YAML File</div>
                    <span style={{ fontSize: '11px', color: '#71717a', display: 'block', marginTop: '4px' }}>
                      Only .yaml or .yml files supported
                    </span>
                  </>
                )}
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => {
                    setIsUploadOpen(false);
                    setUploadFile(null);
                  }}
                  disabled={uploading}
                  className="btn-secondary"
                  style={{
                    height: '36px',
                    padding: '0 16px',
                    fontSize: '13px',
                    borderRadius: '6px',
                    border: '1px solid #27272a',
                    backgroundColor: 'transparent',
                    color: '#fafafa',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="btn"
                  style={{
                    height: '36px',
                    padding: '0 16px',
                    fontSize: '13px',
                    borderRadius: '6px',
                    backgroundColor: uploading || !uploadFile ? '#27272a' : '#0ea5e9',
                    color: uploading || !uploadFile ? '#71717a' : '#fff',
                    border: 'none',
                    cursor: uploading || !uploadFile ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="animate-spin" size={14} />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <>
                      <Upload size={14} />
                      <span>Upload file</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
