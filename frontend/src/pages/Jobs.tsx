import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import {
  CheckCircle2,
  XCircle,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
  Loader2,
  GitCommit,
  Flame,
  RotateCcw,
  Sparkles,
  ExternalLink,
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

interface Artifact {
  artifact_id: string;
  source_id: string;
  external_artifact_id: string | null;
  artifact_name: string;
  status: string;
  processed_at: string | null;
  discovered_at: string | null;
  failure_reason: string | null;
  artifact_metadata: any;
}

interface JobDetails {
  job: Job;
  inference: {
    confidence_score: number;
    column_mapping: any;
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
    deterministic_findings: any;
    recommendations_list: any;
    partitioning_recommendation: string | null;
    explanation: string | null;
  } | null;
  source_schema: any;
  target_schema: any;
  artifacts?: Artifact[];
}

interface JobsProps {
  setActiveTab: (tab: string) => void;
}

export const Jobs: React.FC<JobsProps> = ({ setActiveTab }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded job tracking states
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [expandedDetails, setExpandedDetails] = useState<JobDetails | null>(null);
  const [expandedStages, setExpandedStages] = useState<StageHistory[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  // Triggering actions loading states
  const [actioningJobId, setActioningJobId] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get('/jobs');
      // Sort jobs descending by created_at
      const sorted = (data || []).sort(
        (a: Job, b: Job) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setJobs(sorted);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch job history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    // Poll active jobs progress every 10 seconds
    const interval = setInterval(() => {
      fetchJobs();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleExpandJob = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      setExpandedDetails(null);
      setExpandedStages([]);
      return;
    }

    setExpandedJobId(jobId);
    setExpandedDetails(null);
    setExpandedStages([]);
    setDetailsLoading(true);

    try {
      const [details, stages] = await Promise.all([
        api.get(`/jobs/${jobId}/details`),
        api.get(`/jobs/${jobId}/stages`),
      ]);
      setExpandedDetails(details);
      setExpandedStages(stages || []);
    } catch (err) {
      console.error('Failed to load job details', err);
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleKillJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to manually terminate this job?')) return;
    setActioningJobId(jobId);
    try {
      await api.post(`/jobs/${jobId}/kill`);
      fetchJobs();
      if (expandedJobId === jobId) {
        // Reload details
        const [details, stages] = await Promise.all([
          api.get(`/jobs/${jobId}/details`),
          api.get(`/jobs/${jobId}/stages`),
        ]);
        setExpandedDetails(details);
        setExpandedStages(stages || []);
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
      case 'VALIDATING':
        bg = 'rgba(139, 92, 246, 0.1)';
        color = '#8b5cf6';
        break;
      case 'RECEIVED':
        bg = 'rgba(236, 72, 153, 0.1)';
        color = '#ec4899';
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

  // Separate jobs into Active vs Completed/Failed/Cancelled/Retried
  const activeJobs = jobs.filter((j) => ['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));
  const historyJobs = jobs.filter((j) => !['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa' }}>Pipeline Ingestion Jobs</h2>
        <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
          Monitor running ingestion schemas, LLM inferences, validations, and manual recoveries.
        </p>
      </div>

      {loading && jobs.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading pipeline jobs...</span>
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
      ) : (
        <>
          {/* Active Job Executions */}
          {activeJobs.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#0ea5e9', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="indicator-dot blinking" style={{ backgroundColor: '#0ea5e9' }}></span>
                Active Executions ({activeJobs.length})
              </h3>
              <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', overflow: 'hidden' }}>
                {activeJobs.map((job) => (
                  <JobRow
                    key={job.job_id}
                    job={job}
                    isExpanded={expandedJobId === job.job_id}
                    onExpand={() => handleExpandJob(job.job_id)}
                    detailsLoading={detailsLoading && expandedJobId === job.job_id}
                    details={expandedJobId === job.job_id ? expandedDetails : null}
                    stages={expandedJobId === job.job_id ? expandedStages : []}
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
              Completed & Historical Jobs ({historyJobs.length})
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
                No completed jobs. Trigger an ingestion to start processing.
              </div>
            ) : (
              <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', overflow: 'hidden' }}>
                {historyJobs.map((job) => (
                  <JobRow
                    key={job.job_id}
                    job={job}
                    isExpanded={expandedJobId === job.job_id}
                    onExpand={() => handleExpandJob(job.job_id)}
                    detailsLoading={detailsLoading && expandedJobId === job.job_id}
                    details={expandedJobId === job.job_id ? expandedDetails : null}
                    stages={expandedJobId === job.job_id ? expandedStages : []}
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

// Row component for Job entries
interface JobRowProps {
  job: Job;
  isExpanded: boolean;
  onExpand: () => void;
  detailsLoading: boolean;
  details: JobDetails | null;
  stages: StageHistory[];
  getStatusBadge: (status: string) => React.ReactNode;
  getStatusIcon: (status: string) => React.ReactNode;
  onKill: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  actioning: boolean;
  setActiveTab: (tab: string) => void;
}

const JobRow: React.FC<JobRowProps> = ({
  job,
  isExpanded,
  onExpand,
  detailsLoading,
  details,
  stages,
  getStatusBadge,
  getStatusIcon,
  onKill,
  onRetry,
  actioning,
  setActiveTab,
}) => {
  return (
    <div style={{ borderBottom: '1px solid #27272a' }}>
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
              {job.parent_job_id && (
                <span
                  style={{
                    fontSize: '10px',
                    color: '#71717a',
                    backgroundColor: '#27272a',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  title={`Parent job: ${job.parent_job_id}`}
                >
                  <GitCommit size={10} />
                  Retried from {job.parent_job_id.substring(0, 8)}
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
              <span>Fetching unified metrics and lineage...</span>
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

              {/* Stage Lineage progress bar */}
              <div>
                <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                  Execution Stage Lineage
                </h4>
                {stages.length === 0 ? (
                  <span style={{ fontSize: '13px', color: '#a1a1aa' }}>No stage logs generated.</span>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {stages.map((stage) => {
                      const completed = stage.status.toUpperCase() === 'COMPLETED';
                      const failed = stage.status.toUpperCase() === 'FAILED';
                      const active = stage.status.toUpperCase() === 'RUNNING';

                      let color = '#71717a';
                      let bg = '#18181b';
                      let border = '1px solid #27272a';

                      if (completed) {
                        color = '#10b981';
                        bg = 'rgba(16, 185, 129, 0.05)';
                        border = '1px solid rgba(16, 185, 129, 0.2)';
                      } else if (failed) {
                        color = '#ef4444';
                        bg = 'rgba(239, 68, 68, 0.05)';
                        border = '1px solid rgba(239, 68, 68, 0.2)';
                      } else if (active) {
                        color = '#0ea5e9';
                        bg = 'rgba(14, 165, 233, 0.05)';
                        border = '1px solid rgba(14, 165, 233, 0.2)';
                      }

                      return (
                        <div
                          key={stage.stage_history_id}
                          style={{
                            padding: '8px 12px',
                            borderRadius: '6px',
                            backgroundColor: bg,
                            border: border,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '4px',
                            minWidth: '140px',
                          }}
                        >
                          <span style={{ fontSize: '12px', fontWeight: 600, color: color }}>
                            {stage.stage_name}
                          </span>
                          <span style={{ fontSize: '10px', color: '#71717a' }}>
                            {stage.completed_at
                              ? `${Math.round(
                                  (new Date(stage.completed_at).getTime() - new Date(stage.started_at).getTime()) / 1000
                                )}s duration`
                              : active
                              ? 'In Progress...'
                              : 'Pending'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Data Validation & Schema Drift Metrics grid */}
              {details && (details.validation || details.drift || details.inference) && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                  {/* Validation metrics */}
                  {details.validation && (
                    <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                      <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Schema Validation</span>
                      <div style={{ fontSize: '20px', fontWeight: 600, color: '#fafafa', marginTop: '6px' }}>
                        {(details.validation.target_match_percentage ?? 0).toFixed(0)}% Match
                      </div>
                      <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                        Mapped {details.validation.mapped_column_count} / {details.validation.source_column_count} source columns
                      </div>
                    </div>
                  )}

                  {/* Drift metrics */}
                  {details.drift && (
                    <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                      <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Schema Drift</span>
                      <div
                        style={{
                          fontSize: '20px',
                          fontWeight: 600,
                          color: details.drift.drift_status === 'CRITICAL' ? '#ef4444' : details.drift.drift_status === 'DRIFTED' ? '#f59e0b' : '#10b981',
                          marginTop: '6px',
                        }}
                      >
                        {details.drift.drift_status}
                      </div>
                      <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                        Drift Score: {(details.drift.drift_score ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  )}

                  {/* LLM Confidence */}
                  {details.inference && (
                    <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                      <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>LLM Target Inference</span>
                      <div style={{ fontSize: '20px', fontWeight: 600, color: '#8b5cf6', marginTop: '6px' }}>
                        {((details.inference.confidence_score ?? 0) * 100).toFixed(0)}% Confidence
                      </div>
                      <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                        {details.inference.requires_review ? 'Requires manual audit' : 'Automatic confidence check passed'}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Constituent Artifacts section */}
              {details && details.artifacts && details.artifacts.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.05em' }}>
                    Constituent File Artifacts ({details.artifacts.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {details.artifacts.map((art) => {
                      const isProcessed = art.status.toUpperCase() === 'PROCESSED';
                      const isFailed = art.status.toUpperCase() === 'FAILED';
                      let statusColor = '#a1a1aa';
                      let statusBg = 'rgba(255, 255, 255, 0.05)';
                      let statusBorder = '1px solid rgba(255, 255, 255, 0.1)';

                      if (isProcessed) {
                        statusColor = '#10b981';
                        statusBg = 'rgba(16, 185, 129, 0.1)';
                        statusBorder = '1px solid rgba(16, 185, 129, 0.2)';
                      } else if (isFailed) {
                        statusColor = '#ef4444';
                        statusBg = 'rgba(239, 68, 68, 0.1)';
                        statusBorder = '1px solid rgba(239, 68, 68, 0.2)';
                      }

                      return (
                        <div
                          key={art.artifact_id}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            backgroundColor: '#18181b',
                            border: '1px solid #27272a',
                            borderRadius: '6px',
                            padding: '12px 16px',
                            gap: '6px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '13px', fontWeight: 500, color: '#fafafa' }}>
                              {art.artifact_name}
                            </span>
                            <span
                              style={{
                                fontSize: '11px',
                                fontWeight: 600,
                                color: statusColor,
                                backgroundColor: statusBg,
                                border: statusBorder,
                                padding: '2px 8px',
                                borderRadius: '4px',
                              }}
                            >
                              {art.status}
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#71717a' }}>
                            <span>ID: {(art.artifact_id || '').substring(0, 8)}...</span>
                            {art.discovered_at && (
                              <span>Discovered: {new Date(art.discovered_at).toLocaleString()}</span>
                            )}
                            {art.processed_at && (
                              <span>Processed: {new Date(art.processed_at).toLocaleString()}</span>
                            )}
                          </div>
                          {art.failure_reason && (
                            <div style={{ fontSize: '12px', color: '#ef4444', marginTop: '4px', fontFamily: 'monospace' }}>
                              <strong>Failure Reason:</strong> {art.failure_reason}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
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
                    <span>Recover / Retry Job</span>
                  </button>
                )}

                {details && details.recommendation && (
                  <button
                    onClick={() => setActiveTab(`review:${job.job_id}`)}
                    className="btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      backgroundColor: 'rgba(139, 92, 246, 0.15)',
                      borderColor: 'rgba(139, 92, 246, 0.3)',
                      color: '#a78bfa',
                    }}
                  >
                    <Sparkles size={16} />
                    <span>Review Schema & Submit Feedback</span>
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
