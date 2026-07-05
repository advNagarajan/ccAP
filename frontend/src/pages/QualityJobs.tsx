import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  CheckCircle2,
  XCircle,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
  Loader2,
  RotateCcw,
  ExternalLink,
  Flame,
  GitCommit,
} from 'lucide-react';

interface Job {
  job_id: string;
  source_id: string;
  status: string;
  current_stage: string | null;
  retry_count: number;
  parent_job_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  job_type?: string;
}

interface StageHistory {
  stage_history_id: string;
  job_id: string;
  stage_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

interface DataQualityReportSummary {
  report_id: string;
  job_id: string;
  status: string;
  rules_executed: number;
  rules_failed: number;
  report_json: any;
  created_at: string;
}

interface ArtifactLineageDetails {
  artifact_id: string;
  source_id: string;
  external_artifact_id: string | null;
  artifact_name: string;
  status: string;
  processed_at: string | null;
  discovered_at: string | null;
  failure_reason: string | null;
  artifact_metadata: any;
  data_quality: DataQualityReportSummary | null;
}

interface JobDetailsResponse {
  job: Job;
  stages: StageHistory[];
  parent_job: any;
  artifacts: ArtifactLineageDetails[];
}

interface QualityJobsProps {
  setActiveTab: (tab: string) => void;
}

export const QualityJobs: React.FC<QualityJobsProps> = ({ setActiveTab }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded job tracking states
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [expandedDetails, setExpandedDetails] = useState<JobDetailsResponse | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  // Actions loading states
  const [actioningJobId, setActioningJobId] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get('/jobs');
      // Filter for Quality Jobs only
      const qualityJobs = (data || []).filter((j: Job) => j.job_type === 'QUALITY');
      // Sort jobs descending by created_at
      const sorted = qualityJobs.sort(
        (a: Job, b: Job) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setJobs(sorted);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch quality jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => {
      fetchJobs();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleExpandJob = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      setExpandedDetails(null);
      return;
    }

    setExpandedJobId(jobId);
    setExpandedDetails(null);
    setDetailsLoading(true);

    try {
      const details = await api.get(`/jobs/${jobId}/details`);
      setExpandedDetails(details);
    } catch (err) {
      console.error('Failed to load job details', err);
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleKillJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to terminate this quality job?')) return;
    setActioningJobId(jobId);
    try {
      await api.post(`/jobs/${jobId}/kill`);
      fetchJobs();
      if (expandedJobId === jobId) {
        const details = await api.get(`/jobs/${jobId}/details`);
        setExpandedDetails(details);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to terminate job');
    } finally {
      setActioningJobId(null);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    setActioningJobId(jobId);
    try {
      const newJob = await api.post(`/jobs/${jobId}/retry`);
      alert(`Job retry triggered. New job ID: ${newJob.job_id.substring(0, 8)}`);
      fetchJobs();
      setExpandedJobId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to retry job');
    } finally {
      setActioningJobId(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return <CheckCircle2 size={16} color="#10b981" />;
      case 'FAILED':
        return <XCircle size={16} color="#ef4444" />;
      case 'CANCELLED':
        return <AlertOctagon size={16} color="#71717a" />;
      case 'RETRIED':
        return <RotateCcw size={16} color="#f59e0b" />;
      case 'RUNNING':
      case 'VALIDATING':
      case 'RECEIVED':
      default:
        return <Loader2 className="animate-spin" size={16} color="#0ea5e9" />;
    }
  };

  const getStatusBadge = (status: string) => {
    let bg = 'rgba(255,255,255,0.05)';
    let color = '#a1a1aa';
    let label = status;

    switch (status.toUpperCase()) {
      case 'COMPLETED':
        bg = 'rgba(16, 185, 129, 0.1)';
        color = '#10b981';
        break;
      case 'FAILED':
        bg = 'rgba(239, 68, 68, 0.1)';
        color = '#ef4444';
        break;
      case 'CANCELLED':
        bg = 'rgba(113, 113, 122, 0.1)';
        color = '#71717a';
        label = 'KILLED';
        break;
      case 'RETRIED':
        bg = 'rgba(245, 158, 11, 0.1)';
        color = '#f59e0b';
        break;
      case 'RUNNING':
        bg = 'rgba(14, 165, 233, 0.1)';
        color = '#0ea5e9';
        break;
    }

    return (
      <span
        style={{
          fontSize: '11px',
          fontWeight: 700,
          backgroundColor: bg,
          color: color,
          padding: '2px 8px',
          borderRadius: '4px',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </span>
    );
  };

  // Separate jobs into active and history
  const activeJobs = jobs.filter((j) => ['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));
  const historyJobs = jobs.filter((j) => !['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa' }}>Data Quality Check Jobs</h2>
          <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
            Monitor rule-level completeness, uniqueness, and boundary value audits run against incoming datasets.
          </p>
        </div>
        <button
          onClick={fetchJobs}
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

      {loading && jobs.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading quality check jobs...</span>
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
          <AlertOctagon size={20} />
          <span>{error}</span>
        </div>
      ) : jobs.length === 0 ? (
        <div
          style={{
            border: '1px dashed #27272a',
            borderRadius: '8px',
            padding: '40px 20px',
            textAlign: 'center',
            backgroundColor: '#18181b',
            color: '#a1a1aa',
            fontSize: '13px',
          }}
        >
          No data quality jobs found.
        </div>
      ) : (
        <>
          {/* Active Job Executions */}
          {activeJobs.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#f43f5e', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="indicator-dot blinking" style={{ backgroundColor: '#f43f5e' }}></span>
                Active Executions ({activeJobs.length})
              </h3>
              <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', overflow: 'hidden' }}>
                {activeJobs.map((job) => (
                  <QualityJobRow
                    key={job.job_id}
                    job={job}
                    isExpanded={expandedJobId === job.job_id}
                    onExpand={() => handleExpandJob(job.job_id)}
                    detailsLoading={detailsLoading && expandedJobId === job.job_id}
                    details={expandedJobId === job.job_id ? expandedDetails : null}
                    getStatusBadge={getStatusBadge}
                    getStatusIcon={getStatusIcon}
                    onKill={handleKillJob}
                    onRetry={handleRetryJob}
                    actioning={actioningJobId === job.job_id}
                    setActiveTab={setActiveTab}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Historical Runs */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fafafa' }}>
              Completed & Historical Quality Jobs ({historyJobs.length})
            </h3>
            {historyJobs.length === 0 ? (
              <div
                style={{
                  border: '1px dashed #27272a',
                  borderRadius: '8px',
                  padding: '40px 20px',
                  textAlign: 'center',
                  backgroundColor: '#18181b',
                  color: '#a1a1aa',
                  fontSize: '13px',
                }}
              >
                No historical quality jobs.
              </div>
            ) : (
              <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', overflow: 'hidden' }}>
                {historyJobs.map((job) => (
                  <QualityJobRow
                    key={job.job_id}
                    job={job}
                    isExpanded={expandedJobId === job.job_id}
                    onExpand={() => handleExpandJob(job.job_id)}
                    detailsLoading={detailsLoading && expandedJobId === job.job_id}
                    details={expandedJobId === job.job_id ? expandedDetails : null}
                    getStatusBadge={getStatusBadge}
                    getStatusIcon={getStatusIcon}
                    onKill={handleKillJob}
                    onRetry={handleRetryJob}
                    actioning={actioningJobId === job.job_id}
                    setActiveTab={setActiveTab}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

// Row component for Quality Job entries
interface QualityJobRowProps {
  job: Job;
  isExpanded: boolean;
  onExpand: () => void;
  detailsLoading: boolean;
  details: JobDetailsResponse | null;
  getStatusBadge: (status: string) => React.ReactNode;
  getStatusIcon: (status: string) => React.ReactNode;
  onKill: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  actioning: boolean;
  setActiveTab: (tab: string) => void;
}

const QualityJobRow: React.FC<QualityJobRowProps> = ({
  job,
  isExpanded,
  onExpand,
  detailsLoading,
  details,
  getStatusBadge,
  getStatusIcon,
  onKill,
  onRetry,
  actioning,
  setActiveTab,
}) => {
  const formatJSONVal = (val: any) => {
    if (!val) return 'None';
    try {
      return JSON.stringify(val, null, 2);
    } catch (e) {
      return String(val);
    }
  };

  const getDQStatusColor = (status?: string) => {
    if (!status) return '#71717a';
    const s = status.toUpperCase();
    if (s === 'PASSED') return '#10b981';
    if (s === 'WARNING') return '#f59e0b';
    if (s === 'FAILED') return '#ef4444';
    return '#71717a';
  };

  return (
    <div style={{ borderBottom: '1px solid #27272a', borderLeft: '3px solid #f43f5e' }}>
      {/* Row Summary */}
      <div
        onClick={onExpand}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 24px',
          cursor: 'pointer',
          transition: 'background-color 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.01)')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>{getStatusIcon(job.status)}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 600, color: '#fafafa', fontFamily: 'monospace', fontSize: '13px' }}>
                JOB-{job.job_id.substring(0, 8)}
              </span>
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
              {job.parent_job_id && (
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveTab('jobs');
                  }}
                  style={{
                    fontSize: '10px',
                    color: '#a1a1aa',
                    backgroundColor: '#27272a',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    cursor: 'pointer',
                  }}
                  title={`Parent job: ${job.parent_job_id}`}
                >
                  <GitCommit size={10} />
                  Parent Ingestion: {job.parent_job_id.substring(0, 8)}
                </span>
              )}
            </div>
            <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>Source ID: {job.source_id.substring(0, 8)}...</span>
              <span>•</span>
              <span>Triggered: {new Date(job.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div>{getStatusBadge(job.status)}</div>
          <div>{isExpanded ? <ChevronUp size={16} color="#71717a" /> : <ChevronDown size={16} color="#71717a" />}</div>
        </div>
      </div>

      {/* Expanded Pane */}
      {isExpanded && (
        <div style={{ backgroundColor: '#09090b', padding: '24px 32px', borderTop: '1px solid #27272a' }}>
          {detailsLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#a1a1aa', fontSize: '13px' }}>
              <Loader2 className="animate-spin" size={18} />
              <span>Loading data quality execution metrics...</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Job Error message */}
              {job.error_message && (
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    color: '#ef4444',
                    borderRadius: '6px',
                    padding: '14px 18px',
                    fontSize: '13px',
                    fontFamily: 'monospace',
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>Execution Failure Details:</div>
                  {job.error_message}
                </div>
              )}

              {/* Data Quality Report Summary & Rules metrics */}
              {details && details.artifacts && details.artifacts.length > 0 && (
                <>
                  {(() => {
                    const artWithDQ = details.artifacts.find((a) => a.data_quality !== null);
                    if (!artWithDQ || !artWithDQ.data_quality) {
                      return (
                        <div style={{ color: '#a1a1aa', fontSize: '13px' }}>
                          No data quality report generated yet. The job is currently in stage: <strong>{job.current_stage || 'Unknown'}</strong>.
                        </div>
                      );
                    }

                    const dq = artWithDQ.data_quality;
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Summary Cards */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                          <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                            <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Overall DQ Status</span>
                            <div style={{ fontSize: '20px', fontWeight: 600, color: getDQStatusColor(dq.status), marginTop: '6px' }}>
                              {dq.status}
                            </div>
                          </div>

                          <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                            <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Rules Checked</span>
                            <div style={{ fontSize: '20px', fontWeight: 600, color: '#fafafa', marginTop: '6px' }}>
                              {dq.rules_executed} Executed
                            </div>
                          </div>

                          <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                            <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Rules Failed</span>
                            <div style={{ fontSize: '20px', fontWeight: 600, color: dq.rules_failed > 0 ? '#ef4444' : '#10b981', marginTop: '6px' }}>
                              {dq.rules_failed} Failed
                            </div>
                          </div>
                        </div>

                        {/* Rules Log */}
                        {dq.report_json?.rules && (
                          <div>
                            <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                              Data Quality Rules Audit Log
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {dq.report_json.rules.map((rule: any, idx: number) => {
                                const passed = rule.status === 'PASSED';
                                const warning = rule.status === 'WARNING';
                                let rColor = '#ef4444';
                                let rBg = 'rgba(239, 68, 68, 0.03)';
                                let rBorder = '1px solid rgba(239, 68, 68, 0.15)';
                                if (passed) {
                                  rColor = '#10b981';
                                  rBg = 'rgba(16, 185, 129, 0.03)';
                                  rBorder = '1px solid rgba(16, 185, 129, 0.15)';
                                } else if (warning) {
                                  rColor = '#f59e0b';
                                  rBg = 'rgba(245, 158, 11, 0.03)';
                                  rBorder = '1px solid rgba(245, 158, 11, 0.15)';
                                }

                                return (
                                  <div
                                    key={idx}
                                    style={{
                                      padding: '12px 16px',
                                      backgroundColor: rBg,
                                      border: rBorder,
                                      borderRadius: '6px',
                                      display: 'flex',
                                      flexDirection: 'column',
                                      gap: '4px',
                                    }}
                                  >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#fafafa' }}>
                                        {(rule.rule_type || rule.type || 'UNKNOWN_RULE').replace(/_/g, ' ').toUpperCase()}
                                      </span>
                                      <span style={{ fontSize: '11px', fontWeight: 700, color: rColor }}>
                                        {rule.status}
                                      </span>
                                    </div>
                                    <span style={{ fontSize: '12px', color: '#a1a1aa' }}>
                                      Target Columns: {Array.isArray(rule.columns) ? rule.columns.join(', ') : (rule.columns && typeof rule.columns === 'object') ? Object.keys(rule.columns).join(', ') : rule.columns || rule.column || 'N/A'}
                                    </span>
                                    {rule.failure_count !== undefined && rule.failure_count > 0 && (
                                      <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: 500 }}>
                                        Value Violations: {rule.failure_count} rows failed quality constraints
                                      </span>
                                    )}
                                    {rule.details && (
                                      <span style={{ fontSize: '11px', color: '#71717a', fontStyle: 'italic', marginTop: '2px' }}>
                                        Audit details: {rule.details}
                                      </span>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Raw JSON Report */}
                        <div>
                          <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
                            Raw Report Payload
                          </h4>
                          <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#a1a1aa', overflowX: 'auto', maxHeight: '200px' }}>
                            <code>{formatJSONVal(dq.report_json)}</code>
                          </pre>
                        </div>
                      </div>
                    );
                  })()}
                </>
              )}

              {/* Action Operations */}
              <div style={{ display: 'flex', gap: '12px', borderTop: '1px solid #27272a', paddingTop: '20px' }}>
                {['RECEIVED', 'VALIDATING', 'RUNNING'].includes(job.status.toUpperCase()) && (
                  <button
                    onClick={() => onKill(job.job_id)}
                    disabled={actioning}
                    className="btn btn-secondary"
                    style={{
                      borderColor: 'rgba(239, 68, 68, 0.2)',
                      color: '#ef4444',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <Flame size={16} />
                    <span>Kill Execution</span>
                  </button>
                )}

                {job.status.toUpperCase() === 'FAILED' && (
                  <button
                    onClick={() => onRetry(job.job_id)}
                    disabled={actioning}
                    className="btn"
                    style={{
                      backgroundColor: '#f59e0b',
                      borderColor: '#f59e0b',
                      color: '#09090b',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <RotateCcw size={16} />
                    <span>Re-Run Quality Audit</span>
                  </button>
                )}

                {details && (
                  <button
                    onClick={() => {
                      if (job.parent_job_id) {
                        setActiveTab('jobs');
                      }
                    }}
                    className="btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      backgroundColor: 'rgba(16, 185, 129, 0.15)',
                      borderColor: 'rgba(16, 185, 129, 0.3)',
                      color: '#34d399',
                    }}
                  >
                    <GitCommit size={16} />
                    <span>View Parent Ingestion Lineage</span>
                    <ExternalLink size={14} />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
