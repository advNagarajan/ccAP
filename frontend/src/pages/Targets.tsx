import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  Database,
  Plus,
  X,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Calendar,
  Grid,
  RotateCcw,
  Trash2,
} from 'lucide-react';

interface Target {
  target_id: string;
  target_name: string;
  target_type: string;
  business_domain: string | null;
  connection_details: any;
  schema_definition: any;
  is_system_generated: boolean;
  description: string | null;
  target_status: string;
  created_at: string;
  updated_at: string;
}

export const Targets: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);

  // Edit Modal State
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingTarget, setEditingTarget] = useState<Target | null>(null);
  const [editTargetName, setEditTargetName] = useState('');
  const [editTargetType, setEditTargetType] = useState('POSTGRESQL');
  const [editBusinessDomain, setEditBusinessDomain] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editConnectionDetails, setEditConnectionDetails] = useState('');
  const [editSchemaDefinition, setEditSchemaDefinition] = useState('');

  // Register Form State
  const [targetName, setTargetName] = useState('');
  const [targetType, setTargetType] = useState('POSTGRESQL');
  const [businessDomain, setBusinessDomain] = useState('');
  const [desc, setDesc] = useState('');
  const [connectionDetails, setConnectionDetails] = useState('{\n  "host": "localhost",\n  "port": 5432,\n  "database": "warehouse_db",\n  "schema": "public"\n}');
  const [schemaDefinition, setSchemaDefinition] = useState('{\n  "type": "object",\n  "properties": {}\n}');

  // Notifications
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchTargets = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.get('/targets');
      setTargets(list || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch target catalogs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTargets();
  }, []);

  const handleEditTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTarget) return;

    if (!editTargetName) {
      showNotification('Please provide a target name', 'error');
      return;
    }

    let parsedConn = {};
    let parsedSchema = {};
    try {
      parsedConn = JSON.parse(editConnectionDetails);
    } catch (err) {
      showNotification('Connection details must be valid JSON', 'error');
      return;
    }

    if (editSchemaDefinition) {
      try {
        parsedSchema = JSON.parse(editSchemaDefinition);
      } catch (err) {
        showNotification('Schema definition must be valid JSON', 'error');
        return;
      }
    }

    try {
      setLoading(true);
      await api.patch(`/targets/${editingTarget.target_id}`, {
        target_name: editTargetName,
        target_type: editTargetType,
        business_domain: editBusinessDomain || null,
        description: editDesc || null,
        connection_details: parsedConn,
        schema_definition: editSchemaDefinition ? parsedSchema : null,
      });

      showNotification('Target catalog updated successfully!');
      setIsEditOpen(false);
      fetchTargets();
    } catch (err: any) {
      showNotification(err.message || 'Failed to update target catalog', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTarget = async (targetId: string) => {
    if (!window.confirm('Are you sure you want to delete this target catalog?')) {
      return;
    }

    try {
      setLoading(true);
      await api.delete(`/targets/${targetId}`);
      showNotification('Target catalog deleted successfully!');
      setIsEditOpen(false);
      fetchTargets();
    } catch (err: any) {
      showNotification(err.message || 'Failed to delete target catalog', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetName) {
      showNotification('Please provide a target name', 'error');
      return;
    }

    let parsedConn = {};
    let parsedSchema = {};
    try {
      parsedConn = JSON.parse(connectionDetails);
    } catch (err) {
      showNotification('Connection details must be valid JSON', 'error');
      return;
    }

    if (schemaDefinition) {
      try {
        parsedSchema = JSON.parse(schemaDefinition);
      } catch (err) {
        showNotification('Schema definition must be valid JSON', 'error');
        return;
      }
    }

    try {
      setLoading(true);
      await api.post('/targets', {
        target_name: targetName,
        target_type: targetType,
        business_domain: businessDomain || null,
        description: desc || null,
        connection_details: parsedConn,
        schema_definition: schemaDefinition ? parsedSchema : null,
        is_system_generated: false,
      });

      showNotification('Target registered successfully!');
      setIsRegisterOpen(false);
      // Reset form
      setTargetName('');
      setBusinessDomain('');
      setDesc('');
      fetchTargets();
    } catch (err: any) {
      showNotification(err.message || 'Failed to register target catalog', 'error');
    } finally {
      setLoading(false);
    }
  };

  const formatJSON = (json: any) => {
    return JSON.stringify(json, null, 2);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Panel */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa' }}>Target Catalog</h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Browse registered target databases, schemas, and metadata catalogs.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={fetchTargets}
            disabled={loading}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', height: '36px' }}
          >
            <RotateCcw size={14} className={loading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setIsRegisterOpen(true)}
            className="btn"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', height: '36px' }}
          >
            <Plus size={16} />
            <span>Register Target Catalog</span>
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

      {/* Grid listing */}
      {loading && targets.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading destinations...</span>
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
      ) : targets.length === 0 ? (
        <div
          style={{
            border: '1px dashed #27272a',
            borderRadius: '8px',
            padding: '60px 20px',
            textAlign: 'center',
            backgroundColor: '#18181b',
          }}
        >
          <Database size={40} color="#71717a" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>No Target Catalogs</h3>
          <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto 20px' }}>
            Create target catalogs representing data warehouses or databases to land data.
          </p>
          <button
            onClick={() => setIsRegisterOpen(true)}
            className="btn"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <Plus size={16} />
            <span>Register target</span>
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: '20px',
          }}
        >
          {targets.map((target) => (
            <div
              key={target.target_id}
              style={{
                backgroundColor: '#18181b',
                border: '1px solid #27272a',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '16px',
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
                    {target.target_name}
                  </h3>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      backgroundColor: 'rgba(245, 158, 11, 0.1)',
                      color: '#f59e0b',
                      border: '1px solid rgba(245, 158, 11, 0.2)',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {target.target_type}
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
                  {target.description || 'No description provided.'}
                </p>
              </div>

              {/* Details & Accents */}
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
                  <Grid size={14} />
                  <span>Domain:</span>
                  <span style={{ color: '#fafafa', fontWeight: 500 }}>
                    {target.business_domain || 'Unassigned'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#a1a1aa' }}>
                  <Calendar size={14} />
                  <span>Registered:</span>
                  <span style={{ color: '#fafafa', fontWeight: 500 }}>
                    {new Date(target.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Hoverable details panel */}
              <div className="hover-config-parent">
                <span
                  style={{
                    fontSize: '12px',
                    color: '#f59e0b',
                    cursor: 'pointer',
                    fontWeight: 500,
                    alignSelf: 'flex-start',
                  }}
                >
                  Hover to view target details
                </span>
                <div className="hover-config-child">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ fontSize: '11px', color: '#fafafa', fontWeight: 600 }}>Connection parameters:</div>
                    <pre
                      style={{
                        margin: 0,
                        padding: '8px',
                        fontSize: '10px',
                        backgroundColor: '#09090b',
                        border: '1px solid #27272a',
                        borderRadius: '4px',
                        color: '#f59e0b',
                        overflowX: 'auto',
                        maxHeight: '100px',
                      }}
                    >
                      <code>{formatJSON(target.connection_details)}</code>
                    </pre>

                    {target.schema_definition && (
                      <>
                        <div style={{ fontSize: '11px', color: '#fafafa', fontWeight: 600, marginTop: '4px' }}>
                          Target Schema:
                        </div>
                        <pre
                          style={{
                            margin: 0,
                            padding: '8px',
                            fontSize: '10px',
                            backgroundColor: '#09090b',
                            border: '1px solid #27272a',
                            borderRadius: '4px',
                            color: '#a1a1aa',
                            overflowX: 'auto',
                            maxHeight: '100px',
                          }}
                        >
                          <code>{formatJSON(target.schema_definition)}</code>
                        </pre>
                      </>
                    )}
                  </div>
                </div>
              </div>
              {/* Edit Target Button */}
              <button
                onClick={() => {
                  setEditingTarget(target);
                  setEditTargetName(target.target_name);
                  setEditTargetType(target.target_type);
                  setEditBusinessDomain(target.business_domain || '');
                  setEditDesc(target.description || '');
                  setEditConnectionDetails(JSON.stringify(target.connection_details, null, 2));
                  setEditSchemaDefinition(target.schema_definition ? JSON.stringify(target.schema_definition, null, 2) : '');
                  setIsEditOpen(true);
                }}
                className="btn btn-secondary"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  backgroundColor: 'transparent',
                  border: '1px solid #27272a',
                  color: '#fafafa',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  height: '38px',
                  marginTop: 'auto',
                }}
              >
                Edit Target
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Modal Form: Register Target */}
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
              maxWidth: '520px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '28px',
              position: 'relative',
              maxHeight: '90vh',
              overflowY: 'auto',
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
              Register Target Database
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Set up destinations where schema-drift managed datasets will land.
            </p>

            <form onSubmit={handleRegisterTarget} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label htmlFor="modal-tname">Target Table/Catalog Name *</label>
                <input
                  id="modal-tname"
                  type="text"
                  placeholder="e.g. analytics_user_sessions"
                  value={targetName}
                  onChange={(e) => setTargetName(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label htmlFor="modal-ttype">Database Engine *</label>
                  <select
                    id="modal-ttype"
                    value={targetType}
                    onChange={(e) => setTargetType(e.target.value)}
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
                    <option value="POSTGRESQL">POSTGRESQL</option>
                    <option value="MYSQL">MYSQL</option>
                    <option value="BIGQUERY">BIGQUERY</option>
                    <option value="SNOWFLAKE">SNOWFLAKE</option>
                    <option value="DELTA">DELTA</option>
                    <option value="GCS">GCS</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="modal-domain">Business Domain</label>
                  <input
                    id="modal-domain"
                    type="text"
                    placeholder="e.g. Marketing, Sales"
                    value={businessDomain}
                    onChange={(e) => setBusinessDomain(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="modal-tdesc">Description</label>
                <textarea
                  id="modal-tdesc"
                  rows={2}
                  placeholder="Provide warehouse destination context..."
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
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
                <label htmlFor="modal-tconn">Connection parameters (JSON) *</label>
                <textarea
                  id="modal-tconn"
                  rows={4}
                  value={connectionDetails}
                  onChange={(e) => setConnectionDetails(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#f59e0b',
                    fontFamily: 'monospace',
                    padding: '10px 12px',
                    fontSize: '12px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div>
                <label htmlFor="modal-tschema">Schema Definition Schema JSON (Optional)</label>
                <textarea
                  id="modal-tschema"
                  rows={4}
                  value={schemaDefinition}
                  onChange={(e) => setSchemaDefinition(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#a1a1aa',
                    fontFamily: 'monospace',
                    padding: '10px 12px',
                    fontSize: '12px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <button type="submit" className="btn" style={{ width: '100%', marginTop: '8px', height: '40px' }}>
                Register Target
              </button>
            </form>
          </div>
        </div>
      )}
      {/* Modal Form: Edit Target */}
      {isEditOpen && editingTarget && (
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
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
          >
            <button
              onClick={() => setIsEditOpen(false)}
              style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                background: 'none',
                border: 'none',
                color: '#a1a1aa',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
              Edit Target Catalog
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Modify the target's parameters, domain, or schema definition.
            </p>

            <form onSubmit={handleEditTarget} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>
                  Target Name <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  value={editTargetName}
                  onChange={(e) => setEditTargetName(e.target.value)}
                  style={{
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#fafafa',
                    fontSize: '14px',
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>
                    Target Type <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <select
                    value={editTargetType}
                    onChange={(e) => setEditTargetType(e.target.value)}
                    style={{
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      color: '#fafafa',
                      fontSize: '14px',
                    }}
                  >
                    <option value="POSTGRESQL">PostgreSQL</option>
                    <option value="MYSQL">MySQL</option>
                    <option value="BIGQUERY">BigQuery</option>
                    <option value="GCS">Google Cloud Storage</option>
                    <option value="S3">Amazon S3</option>
                    <option value="DELTA">Delta Lake</option>
                    <option value="SNOWFLAKE">Snowflake</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>Business Domain</label>
                  <input
                    type="text"
                    value={editBusinessDomain}
                    onChange={(e) => setEditBusinessDomain(e.target.value)}
                    placeholder="e.g. Finance, Marketing"
                    style={{
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      color: '#fafafa',
                      fontSize: '14px',
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>Description</label>
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  rows={2}
                  style={{
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#fafafa',
                    fontSize: '14px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>
                  Connection Parameters (JSON) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <textarea
                  required
                  value={editConnectionDetails}
                  onChange={(e) => setEditConnectionDetails(e.target.value)}
                  rows={4}
                  style={{
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#f59e0b',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fafafa' }}>
                  Schema Definition JSON (Optional)
                </label>
                <textarea
                  value={editSchemaDefinition}
                  onChange={(e) => setEditSchemaDefinition(e.target.value)}
                  rows={4}
                  style={{
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#a1a1aa',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => handleDeleteTarget(editingTarget.target_id)}
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#ef4444',
                    borderRadius: '6px',
                    padding: '8px 16px',
                    fontSize: '14px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Trash2 size={16} />
                  <span>Delete Target</span>
                </button>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setIsEditOpen(false)}
                    className="btn btn-secondary"
                    style={{ padding: '8px 16px' }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn"
                    style={{ padding: '8px 16px', backgroundColor: '#0ea5e9', color: '#fff', border: 'none' }}
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
