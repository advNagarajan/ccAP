import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  Sparkles,
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Send,
} from 'lucide-react';

interface ReviewProps {
  jobId: string;
  onClose: () => void;
}

interface JobDetails {
  job: any;
  inference: {
    confidence_score: number;
    column_mapping: Record<string, string>;
    unmapped_source_columns: string[] | null;
    missing_target_columns: string[] | null;
    reasoning: string | null;
    requires_review: boolean;
  } | null;
  validation: {
    validation_status: string;
    coverage_percentage: number;
    target_match_percentage: number;
    mapped_column_count: number;
    source_column_count: number;
    target_column_count: number;
    report_json: any;
  } | null;
  drift: {
    drift_status: string;
    drift_score: number;
    drift_summary: string | null;
  } | null;
  recommendation: {
    recommendation_status: string;
    deterministic_findings: any[];
    recommendations_list: any[];
    partitioning_recommendation: string | null;
    explanation: string | null;
  } | null;
  source_schema: any;
  target_schema: any;
}

export const Review: React.FC<ReviewProps> = ({ jobId, onClose }) => {
  const [details, setDetails] = useState<JobDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [userAction, setUserAction] = useState('APPROVE');
  const [notes, setNotes] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get(`/jobs/${jobId}/details`);
      setDetails(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch job recommendations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [jobId]);

  const handleSubmitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!details) return;

    setSubmitLoading(true);
    try {
      // Gather target ID safely from details
      let targetId = null;
      if (details.validation?.report_json?.target_id) {
        targetId = details.validation.report_json.target_id;
      }

      // Collect source paths
      const paths = details.source_schema ? Object.keys(details.source_schema) : [];

      await api.post('/feedback', {
        job_id: jobId,
        target_id: targetId,
        observed_flattened_paths: paths,
        user_action: userAction,
        engineer_notes: notes,
        stage: 'recommendation',
        response_in_question: details.recommendation || {},
      });

      showNotification('Feedback successfully submitted. Model prompt context updated.');
      setNotes('');
    } catch (err: any) {
      showNotification(err.message || 'Failed to submit feedback', 'error');
    } finally {
      setSubmitLoading(false);
    }
  };

  // Helper to compile diffs / findings
  const getChangeBadge = (action: string) => {
    let color = '#71717a';
    let bg = 'rgba(255,255,255,0.05)';

    switch (action.toUpperCase()) {
      case 'ADD_COLUMN':
      case 'ADD':
        color = '#10b981';
        bg = 'rgba(16, 185, 129, 0.1)';
        break;
      case 'REMOVE_COLUMN':
      case 'REMOVE':
        color = '#ef4444';
        bg = 'rgba(239, 68, 68, 0.1)';
        break;
      case 'MODIFY_TYPE':
      case 'TYPE_DRIFT':
      case 'CHANGE':
        color = '#f59e0b';
        bg = 'rgba(245, 158, 11, 0.1)';
        break;
    }

    return (
      <span
        style={{
          fontSize: '10px',
          fontWeight: 700,
          backgroundColor: bg,
          color: color,
          padding: '2px 6px',
          borderRadius: '4px',
          textTransform: 'uppercase',
        }}
      >
        {action}
      </span>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Back Button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#a1a1aa',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '13px',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = '#fafafa')}
          onMouseLeave={(e) => (e.currentTarget.style.color = '#a1a1aa')}
        >
          <ArrowLeft size={16} />
          <span>Back to Jobs</span>
        </button>
        <div style={{ height: '24px', width: '1px', backgroundColor: '#27272a' }}></div>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={18} color="#a78bfa" />
          Review Schema Inferences & LLM Recommendations
        </h2>
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

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading recommendation profiles...</span>
        </div>
      ) : error || !details ? (
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
          <span>{error || 'Failed to load details'}</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '28px', alignItems: 'flex-start' }}>
          
          {/* Left Column: Recommendations & Schema Comparisons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* AI Explanation card */}
            {details.recommendation && (
              <div
                style={{
                  backgroundColor: '#18181b',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#a78bfa', fontSize: '14px', fontWeight: 600 }}>
                  <Sparkles size={16} />
                  <span>AI Inference Reasoning</span>
                </div>
                <p style={{ color: '#fafafa', fontSize: '14px', lineHeight: '1.6', margin: 0 }}>
                  {details.recommendation.explanation || 'No detailed explanation generated.'}
                </p>
                {details.recommendation.partitioning_recommendation && (
                  <div style={{ fontSize: '12px', color: '#a1a1aa', borderTop: '1px solid #27272a', paddingTop: '12px', marginTop: '4px' }}>
                    <strong>Partitioning Recommendation:</strong> {details.recommendation.partitioning_recommendation}
                  </div>
                )}
              </div>
            )}

            {/* Diffs / Deterministic Findings List */}
            {details.recommendation && details.recommendation.recommendations_list && (
              <div
                style={{
                  backgroundColor: '#18181b',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                }}
              >
                <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  Schema Drift Alterations
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {details.recommendation.recommendations_list.map((rec: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        padding: '12px 16px',
                        backgroundColor: '#09090b',
                        border: '1px solid #27272a',
                        borderRadius: '6px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#fafafa', fontFamily: 'monospace' }}>
                          {rec.column_name || rec.field}
                        </span>
                        <span style={{ fontSize: '12px', color: '#a1a1aa' }}>
                          {rec.reason || rec.explanation}
                        </span>
                      </div>
                      <div>{getChangeBadge(rec.action || rec.operation || 'MODIFY_TYPE')}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Flat Source Schema details */}
            {details.source_schema && (
              <div
                style={{
                  backgroundColor: '#18181b',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  padding: '24px',
                }}
              >
                <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fafafa', marginBottom: '16px' }}>
                  Source Metadata Specification
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #27272a', color: '#71717a' }}>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Field Path</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Inferred Type</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Sample Values</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(details.source_schema).map(([key, val]: [string, any]) => (
                        <tr key={key} style={{ borderBottom: '1px solid #27272a' }}>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#fafafa', fontWeight: 500 }}>
                            {key}
                          </td>
                          <td style={{ padding: '8px 12px', color: '#0ea5e9' }}>
                            {val.type || val.data_type || 'unknown'}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              color: '#a1a1aa',
                              maxWidth: '240px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {val.sample_values ? JSON.stringify(val.sample_values) : 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          </div>

          {/* Right Column: Feedback Loop Submitter */}
          <div
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              position: 'sticky',
              top: '24px',
            }}
          >
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa' }}>Model Feedback Loop</h3>
              <p style={{ color: '#a1a1aa', fontSize: '13px', marginTop: '4px' }}>
                Annotate recommendations. Approved/rejected states feed historical context back to future LLM pipeline runs.
              </p>
            </div>

            <form onSubmit={handleSubmitFeedback} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label htmlFor="feed-action">Feedback Decision Action</label>
                <select
                  id="feed-action"
                  value={userAction}
                  onChange={(e) => setUserAction(e.target.value)}
                  style={{
                    width: '100%',
                    height: '38px',
                    backgroundColor: '#09090b',
                    border: '1px solid #27272a',
                    borderRadius: '6px',
                    color: '#fafafa',
                    padding: '0 12px',
                    fontSize: '13px',
                  }}
                >
                  <option value="APPROVE">APPROVE RECOMMENDATIONS</option>
                  <option value="REJECT">REJECT SCHEMA SHIFTS</option>
                  <option value="ADJUST">ADJUST PROMPT EMBEDDINGS</option>
                </select>
              </div>

              <div>
                <label htmlFor="feed-notes">Engineer Corrective Notes *</label>
                <textarea
                  id="feed-notes"
                  rows={6}
                  placeholder="e.g. Column 'phone' is string data. Cast target column to VARCHAR instead of bigint, or mapping matches incorrect domain..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
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
                disabled={submitLoading || !notes}
                className="btn"
                style={{
                  width: '100%',
                  height: '40px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  backgroundColor: '#8b5cf6',
                  borderColor: '#8b5cf6',
                }}
              >
                {submitLoading ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <>
                    <Send size={16} />
                    <span>Submit to Feedback Loop</span>
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
