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

interface ParentJobSummary {
  job_id: string;
  status: string;
  parent_job_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
  stages?: StageHistory[];
  parent_job?: ParentJobSummary | null;
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
  inference: {
    inference_id: string;
    confidence_score: number;
    column_mapping: any;
    unmapped_source_columns: string[] | null;
    missing_target_columns: string[] | null;
    partitioning_recommendation: string | null;
    reasoning: string;
    requires_review: boolean;
    created_at: string | null;
    matched_target_table: string | null;
    matched_target_id: string | null;
  } | null;
  validation: {
    validation_id: string;
    validation_status: string;
    coverage_percentage: number;
    target_match_percentage: number;
    mapped_column_count: number;
    source_column_count: number;
    target_column_count: number;
    report_json: any;
    created_at: string | null;
  } | null;
  drift: {
    drift_id: string;
    drift_status: string;
    drift_score: number;
    drift_summary: any;
    created_at: string | null;
  } | null;
  recommendation: {
    recommendation_id: string;
    recommendation_status: string;
    deterministic_findings: any;
    recommendations_list: any;
    partitioning_recommendation: string | null;
    explanation: string | null;
    created_at: string | null;
  } | null;
  fallback: {
    request_id: string;
    request_reason: string;
    request_status: string;
    backup_table_name: string | null;
    approved_by: string | null;
    approved_at: string | null;
    rejected_by: string | null;
    rejected_at: string | null;
    review_notes: string | null;
    created_at: string | null;
  } | null;
  target: {
    target_id: string;
    target_name: string;
    target_type: string;
    schema_definition: any;
  } | null;
  data_quality: {
    report_id: string;
    job_id: string;
    status: string;
    rules_executed: number;
    rules_failed: number;
    report_json: any;
    created_at: string;
  } | null;
}

interface JobDetailsResponse {
  job: Job;
  stages: StageHistory[];
  parent_job: ParentJobSummary | null;
  artifacts: ArtifactLineageDetails[];
  source_schema: any;
  target_schema: any;
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
  const [expandedDetails, setExpandedDetails] = useState<JobDetailsResponse | null>(null);
  const [expandedStages, setExpandedStages] = useState<StageHistory[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  // Graph page view tracking states
  const [activeGraphJobId, setActiveGraphJobId] = useState<string | null>(null);
  const [activeGraphDetails, setActiveGraphDetails] = useState<JobDetailsResponse | null>(null);
  const [selectedGraphArtifactId, setSelectedGraphArtifactId] = useState<string | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState<string | null>('source');
  const [zoomScale, setZoomScale] = useState<number>(1.0);

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

  const renderInteractiveGraph = () => {
    if (!activeGraphDetails) return null;
    
    const artLineage = activeGraphDetails.artifacts.find(
      (a) => a.artifact_id === selectedGraphArtifactId
    ) || activeGraphDetails.artifacts[0];

    if (!artLineage) {
      return (
        <div style={{ padding: '20px', color: '#a1a1aa' }}>
          <h3>No Artifacts Found</h3>
          <button onClick={() => { setActiveGraphJobId(null); setActiveGraphDetails(null); }} className="btn btn-secondary">
            Back to Job list
          </button>
        </div>
      );
    }

    const formatJSONVal = (val: any) => {
      if (!val) return 'None';
      try {
        return JSON.stringify(val, null, 2);
      } catch (e) {
        return String(val);
      }
    };

    const getParentStatusColor = () => {
      const status = activeGraphDetails.parent_job?.status?.toUpperCase() || 'UNKNOWN';
      if (status === 'COMPLETED') return '#10b981';
      if (status === 'FAILED') return '#ef4444';
      return '#f59e0b';
    };

    const getDQStatusColor = (art: ArtifactLineageDetails) => {
      if (!art.data_quality) return '#71717a';
      const status = art.data_quality.status?.toUpperCase();
      if (status === 'PASSED') return '#10b981';
      if (status === 'WARNING') return '#f59e0b';
      if (status === 'FAILED') return '#ef4444';
      return '#71717a';
    };

    const getInferenceStatusColor = (art: ArtifactLineageDetails) => {
      if (!art.inference) return '#71717a';
      return art.inference.confidence_score >= 0.7 ? '#10b981' : '#f59e0b';
    };

    const getValidationStatusColor = (art: ArtifactLineageDetails) => {
      if (!art.validation) return '#71717a';
      return art.validation.validation_status === 'VALID' ? '#10b981' : '#ef4444';
    };

    const getDriftStatusColor = (art: ArtifactLineageDetails) => {
      if (!art.drift) return '#71717a';
      const status = art.drift.drift_status?.toUpperCase();
      if (status === 'NO_DRIFT') return '#10b981';
      if (status === 'CRITICAL') return '#ef4444';
      return '#f59e0b';
    };

    const getFinalStatusColor = (art: ArtifactLineageDetails) => {
      if (art.fallback) {
        const st = art.fallback.request_status?.toUpperCase();
        if (st === 'APPROVED') return '#10b981';
        if (st === 'REJECTED') return '#ef4444';
        return '#f59e0b';
      }
      if (art.recommendation) {
        const st = art.recommendation.recommendation_status?.toUpperCase();
        if (st === 'COMPLETED') return '#10b981';
        return '#f59e0b';
      }
      return art.target ? '#10b981' : '#71717a';
    };

    const getExtractionStatusColor = (art: ArtifactLineageDetails) => {
      if (art.artifact_metadata) return '#10b981';
      if (art.status?.toUpperCase() === 'FAILED' && !art.inference) return '#ef4444';
      const acqLog = activeGraphDetails.stages?.find(s => s.stage_name.toLowerCase() === 'dataset acquisition');
      if (acqLog && acqLog.status === 'COMPLETED') return '#0ea5e9';
      return '#71717a';
    };

    const getVectorizationStatusColor = (art: ArtifactLineageDetails) => {
      if (art.inference) return '#10b981';
      if (art.status?.toUpperCase() === 'FAILED' && art.artifact_metadata && !art.inference) return '#ef4444';
      if (art.artifact_metadata) return '#0ea5e9';
      return '#71717a';
    };

    const getStageAttemptCount = (stageDbName: string): number => {
      let count = 0;
      if (activeGraphDetails.stages) {
        count += activeGraphDetails.stages.filter(
          (s) => s.stage_name.toLowerCase() === stageDbName.toLowerCase()
        ).length;
      }
      let parent: ParentJobSummary | null | undefined = activeGraphDetails.parent_job;
      while (parent) {
        if (parent.stages) {
          count += parent.stages.filter(
            (s) => s.stage_name.toLowerCase() === stageDbName.toLowerCase()
          ).length;
        }
        parent = parent.parent_job;
      }
      return count;
    };

    const renderRetryBadge = (stageDbName: string) => {
      const attempts = getStageAttemptCount(stageDbName);
      if (attempts > 1) {
        return (
          <span
            style={{
              marginLeft: '6px',
              fontSize: '9px',
              backgroundColor: 'rgba(245, 158, 11, 0.12)',
              color: '#f59e0b',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              padding: '1px 4px',
              borderRadius: '3px',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '2px',
            }}
            title={`Executed ${attempts} times across all run retries`}
          >
            <span>↻</span> Retry #{attempts - 1}
          </span>
        );
      }
      return null;
    };

    const targetNameStr = artLineage.target?.target_name || artLineage.inference?.matched_target_table || 'Unassigned Catalog';

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minHeight: '80vh' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #27272a', paddingBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                onClick={() => {
                  setActiveGraphJobId(null);
                  setActiveGraphDetails(null);
                }}
                className="btn btn-secondary"
                style={{ height: '32px', fontSize: '12px' }}
              >
                ➔ Back to Ledger
              </button>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                Interactive Pipeline Graph
              </h2>
            </div>
            <span style={{ fontSize: '13px', color: '#a1a1aa', display: 'block', marginTop: '6px' }}>
              Tracing Job: <strong style={{ fontFamily: 'monospace' }}>{activeGraphDetails.job.job_id}</strong> • Source: <strong>{artLineage.artifact_name}</strong>
            </span>
          </div>

          {/* Artifact Selector Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '12px', color: '#a1a1aa', fontWeight: 500 }}>Select File Artifact:</span>
            <select
              value={selectedGraphArtifactId || ''}
              onChange={(e) => {
                setSelectedGraphArtifactId(e.target.value);
                setSelectedGraphNode('source');
              }}
              style={{
                width: '260px',
                height: '36px',
                backgroundColor: '#18181b',
                borderColor: '#27272a',
                color: '#fafafa',
                borderRadius: '6px',
                fontSize: '13px',
              }}
            >
              {activeGraphDetails.artifacts.map((art) => (
                <option key={art.artifact_id} value={art.artifact_id}>
                  {art.artifact_name} ({art.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* View Grid */}
        <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: 0 }}>
          {/* Node Chart Panel (Left) */}
          <div
            style={{
              flex: 1,
              backgroundColor: '#09090b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '24px',
              position: 'relative',
              overflow: 'auto',
              minHeight: '500px',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Legend */}
            <div style={{ position: 'absolute', top: '16px', left: '16px', display: 'flex', gap: '16px', fontSize: '11px', color: '#71717a', zIndex: 5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} /> Passed</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f59e0b' }} /> Requires Review / Drift</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} /> Failed / Rejected</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#71717a' }} /> Pending</div>
            </div>

            {/* Zoom Controls */}
            <div
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                zIndex: 10,
                display: 'flex',
                gap: '6px',
                alignItems: 'center',
                backgroundColor: '#18181b',
                border: '1px solid #27272a',
                padding: '4px 8px',
                borderRadius: '6px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
              }}
            >
              <button
                onClick={() => setZoomScale((s) => Math.max(0.4, s - 0.1))}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: '#a1a1aa',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  padding: '2px 6px',
                }}
                title="Zoom Out"
              >
                -
              </button>
              <span style={{ fontSize: '11px', color: '#fafafa', minWidth: '36px', textAlign: 'center', fontFamily: 'monospace' }}>
                {Math.round(zoomScale * 100)}%
              </span>
              <button
                onClick={() => setZoomScale((s) => Math.min(1.6, s + 0.1))}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: '#a1a1aa',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  padding: '2px 6px',
                }}
                title="Zoom In"
              >
                +
              </button>
              <button
                onClick={() => setZoomScale(1.0)}
                style={{
                  backgroundColor: '#27272a',
                  border: 'none',
                  color: '#fafafa',
                  cursor: 'pointer',
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '4px',
                }}
                title="Reset Zoom"
              >
                Reset
              </button>
            </div>

            {/* Scrollable Spacer Container */}
            <div
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'flex-start',
                minWidth: `${activeGraphDetails.artifacts.length * 280 * zoomScale}px`,
                minHeight: `${750 * zoomScale}px`,
                marginTop: '40px',
              }}
            >
              <div
                style={{
                  transform: `scale(${zoomScale})`,
                  transformOrigin: 'top center',
                  transition: 'transform 0.15s ease-out',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: `${activeGraphDetails.artifacts.length * 280}px`,
                }}
              >
                {/* Node 0: Parent attempt (if any) */}
                {activeGraphDetails.parent_job && (
                  <>
                    <div
                      onClick={() => setSelectedGraphNode('parent')}
                      style={{
                        width: '320px',
                        backgroundColor: selectedGraphNode === 'parent' ? 'rgba(239, 68, 68, 0.05)' : '#18181b',
                        border: `1px solid ${selectedGraphNode === 'parent' ? '#ef4444' : '#27272a'}`,
                        borderRadius: '8px',
                        padding: '16px',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        boxShadow: selectedGraphNode === 'parent' ? '0 0 12px rgba(239, 68, 68, 0.2)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', justifyItems: 'center', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '10px', fontWeight: 600, color: getParentStatusColor(), textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Parent Run (Attempt 1)
                        </span>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: getParentStatusColor() }} />
                      </div>
                      <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#fafafa', marginTop: '6px' }}>
                        Previous Job attempt
                      </h4>
                      <span style={{ fontSize: '11px', color: '#71717a', display: 'block', fontFamily: 'monospace', marginTop: '4px' }}>
                        {activeGraphDetails.parent_job.job_id.substring(0, 8)}...
                      </span>
                    </div>
                    <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a', position: 'relative' }}>
                      <div style={{ position: 'absolute', bottom: '-4px', left: '-3px', width: '8px', height: '8px', borderRight: '2px solid #27272a', borderBottom: '2px solid #27272a', transform: 'rotate(45deg)' }} />
                    </div>
                  </>
                )}

                {/* Node 1: Ingestion Shared Root (Dataset Ingestion) */}
                <div
                  onClick={() => setSelectedGraphNode('source')}
                  style={{
                    width: '320px',
                    backgroundColor: selectedGraphNode === 'source' ? 'rgba(14, 165, 233, 0.05)' : '#18181b',
                    border: `1px solid ${selectedGraphNode === 'source' ? '#0ea5e9' : '#27272a'}`,
                    borderRadius: '8px',
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: selectedGraphNode === 'source' ? '0 0 12px rgba(14, 165, 233, 0.2)' : 'none',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ display: 'flex', justifyItems: 'center', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '10px', fontWeight: 600, color: '#0ea5e9', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center' }}>
                      Stage 1: Dataset Ingestion
                      {renderRetryBadge('Dataset Acquisition')}
                    </span>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                  </div>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, color: '#fafafa', marginTop: '6px' }}>
                    Dataset Acquisition Triggered
                  </h4>
                  <span style={{ fontSize: '11px', color: '#71717a', display: 'block', marginTop: '4px' }}>
                    Job: {activeGraphDetails.job.job_id.substring(0, 8)}...
                  </span>
                </div>

                {/* SVG Branch Connectors Canvas */}
                <svg width="100%" height="40" style={{ display: 'block' }}>
                  {activeGraphDetails.artifacts.map((art, idx) => {
                    const N = activeGraphDetails.artifacts.length;
                    const xStart = '50%';
                    const xEnd = `${((idx + 0.5) / N) * 100}%`;
                    return (
                      <line
                        key={art.artifact_id}
                        x1={xStart}
                        y1="0"
                        x2={xEnd}
                        y2="100%"
                        stroke="#27272a"
                        strokeWidth="2"
                      />
                    );
                  })}
                </svg>

                {/* Columns Row representing parallel file artifacts */}
                <div style={{ display: 'flex', width: '100%', gap: '20px' }}>
                  {activeGraphDetails.artifacts.map((art, idx) => {
                    const isSelectedArtifact = selectedGraphArtifactId === art.artifact_id || (!selectedGraphArtifactId && idx === 0);
                    
                    const isSourceSelected = isSelectedArtifact && selectedGraphNode === 'source';
                    const isExtractionSelected = isSelectedArtifact && selectedGraphNode === 'extraction';
                    const isVectorizationSelected = isSelectedArtifact && selectedGraphNode === 'vectorization';
                    const isInferenceSelected = isSelectedArtifact && selectedGraphNode === 'inference';
                    const isValidationSelected = isSelectedArtifact && selectedGraphNode === 'validation';
                    const isDriftSelected = isSelectedArtifact && selectedGraphNode === 'drift';
                    const isFinalSelected = isSelectedArtifact && selectedGraphNode === 'final';

                    const artifactTargetName = art.target?.target_name || art.inference?.matched_target_table || 'Unassigned Catalog';

                    const renderPipelineStages = () => {
                      return (
                        <>
                          {/* Node 2: Metadata Extraction */}
                          {art.artifact_metadata && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('extraction');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isExtractionSelected ? 'rgba(168, 85, 247, 0.05)' : '#18181b',
                                  border: `1px solid ${isExtractionSelected ? '#a855f7' : '#27272a'}`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isExtractionSelected ? '0 0 10px rgba(168, 85, 247, 0.15)' : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#a855f7', textTransform: 'uppercase', display: 'flex', alignItems: 'center' }}>
                                    Stage 2: Extraction
                                    {renderRetryBadge('Metadata Extraction')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getExtractionStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px' }}>
                                  Profile Generated
                                </h6>
                              </div>
                            </>
                          )}

                          {/* Node 3: Metadata Vectorization */}
                          {(art.inference || (art.status === 'FAILED' && art.artifact_metadata)) && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('vectorization');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isVectorizationSelected ? 'rgba(236, 72, 153, 0.05)' : '#18181b',
                                  border: `1px solid ${isVectorizationSelected ? '#ec4899' : '#27272a'}`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isVectorizationSelected ? '0 0 10px rgba(236, 72, 153, 0.15)' : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#ec4899', textTransform: 'uppercase', display: 'flex', alignItems: 'center' }}>
                                    Stage 3: Vectorization
                                    {renderRetryBadge('Metadata Vectorization')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getVectorizationStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px' }}>
                                  {art.inference ? 'Index Synced' : 'Vectorization Failed'}
                                </h6>
                              </div>
                            </>
                          )}

                          {/* Node 4: Target Selection */}
                          {art.inference && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('inference');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isInferenceSelected ? 'rgba(139, 92, 246, 0.05)' : '#18181b',
                                  border: `1px solid ${isInferenceSelected ? '#8b5cf6' : '#27272a'}`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isInferenceSelected ? '0 0 10px rgba(139, 92, 246, 0.15)' : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#8b5cf6', textTransform: 'uppercase', display: 'flex', alignItems: 'center' }}>
                                    Stage 4: Inference
                                    {renderRetryBadge('Target Inference')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getInferenceStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={artifactTargetName}>
                                  Matched: {artifactTargetName}
                                </h6>
                              </div>
                            </>
                          )}

                          {/* Node 5: Schema Validation */}
                          {art.validation && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('validation');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isValidationSelected ? 'rgba(16, 185, 129, 0.05)' : '#18181b',
                                  border: `1px solid ${isValidationSelected ? '#10b981' : '#27272a'}`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isValidationSelected ? '0 0 10px rgba(16, 185, 129, 0.15)' : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#10b981', textTransform: 'uppercase', display: 'flex', alignItems: 'center' }}>
                                    Stage 5: Validation
                                    {renderRetryBadge('Schema Validation')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getValidationStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px' }}>
                                  Status: {art.validation.validation_status}
                                </h6>
                              </div>
                            </>
                          )}

                          {/* Node 6: Drift Check */}
                          {art.drift && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('drift');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isDriftSelected ? 'rgba(245, 158, 11, 0.05)' : '#18181b',
                                  border: `1px solid ${isDriftSelected ? '#f59e0b' : '#27272a'}`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isDriftSelected ? '0 0 10px rgba(245, 158, 11, 0.15)' : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#f59e0b', textTransform: 'uppercase', display: 'flex', alignItems: 'center' }}>
                                    Stage 6: Drift Check
                                    {renderRetryBadge('Schema Drift Detection')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getDriftStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px' }}>
                                  Drift: {art.drift.drift_status}
                                </h6>
                              </div>
                            </>
                          )}

                          {/* Node 7: Final Landing Outcome */}
                          {(art.recommendation || art.fallback || art.target) && (
                            <>
                              {/* Connector */}
                              <div style={{ height: '20px', width: '2px', backgroundColor: '#27272a' }} />
                              <div
                                onClick={() => {
                                  setSelectedGraphArtifactId(art.artifact_id);
                                  setSelectedGraphNode('final');
                                }}
                                style={{
                                  width: '100%',
                                  backgroundColor: isFinalSelected 
                                    ? (art.fallback?.request_status === 'REJECTED' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(16, 185, 129, 0.05)')
                                    : '#18181b',
                                  border: `1px solid ${
                                    isFinalSelected 
                                      ? (art.fallback?.request_status === 'REJECTED' ? '#ef4444' : '#10b981') 
                                      : '#27272a'
                                  }`,
                                  borderRadius: '8px',
                                  padding: '12px',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  boxShadow: isFinalSelected 
                                    ? (art.fallback?.request_status === 'REJECTED' ? '0 0 10px rgba(239, 68, 68, 0.15)' : '0 0 10px rgba(16, 185, 129, 0.15)')
                                    : 'none',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ 
                                    fontSize: '9px', 
                                    fontWeight: 600, 
                                    color: art.fallback 
                                      ? (art.fallback.request_status === 'APPROVED' ? '#10b981' : art.fallback.request_status === 'REJECTED' ? '#ef4444' : '#f59e0b')
                                      : '#10b981', 
                                    textTransform: 'uppercase', 
                                    display: 'inline-flex', 
                                    alignItems: 'center' 
                                  }}>
                                    {art.fallback ? 'Fallback Decision' : 'Stage 7: Landing Outcome'}
                                    {!art.fallback && renderRetryBadge('Schema Recommendation Generation')}
                                  </span>
                                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getFinalStatusColor(art) }} />
                                </div>
                                <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {art.fallback
                                    ? (art.fallback.request_status === 'APPROVED'
                                        ? 'Accepted'
                                        : art.fallback.request_status === 'REJECTED'
                                        ? 'Denied'
                                        : 'Pending Review')
                                    : art.recommendation
                                    ? `Altered Schema (${art.recommendation.recommendation_status})`
                                    : art.target
                                    ? `Land in ${art.target.target_name}`
                                    : 'Awaiting completion'}
                                </h6>
                              </div>
                            </>
                          )}
                        </>
                      );
                    };

                    return (
                      <div
                        key={art.artifact_id}
                        style={{
                          flex: 1,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          minWidth: '250px',
                        }}
                      >
                        {/* Artifact header card */}
                        <div
                          onClick={() => {
                            setSelectedGraphArtifactId(art.artifact_id);
                            setSelectedGraphNode('source');
                          }}
                          style={{
                            width: '100%',
                            backgroundColor: isSourceSelected ? 'rgba(14, 165, 233, 0.05)' : '#18181b',
                            border: `1px solid ${isSourceSelected ? '#0ea5e9' : '#27272a'}`,
                            borderRadius: '8px',
                            padding: '12px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            boxShadow: isSourceSelected ? '0 0 10px rgba(14, 165, 233, 0.15)' : 'none',
                          }}
                        >
                          <div style={{ fontSize: '9px', fontWeight: 600, color: '#a1a1aa', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            File Ingestion
                          </div>
                          <h5 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={art.artifact_name}>
                            {art.artifact_name}
                          </h5>
                          <span style={{ fontSize: '10px', color: art.status === 'PROCESSED' ? '#10b981' : art.status === 'FAILED' ? '#ef4444' : '#71717a', display: 'block', marginTop: '2px' }}>
                            {art.status}
                          </span>
                        </div>

                        {art.data_quality ? (
                          <>
                            {/* Fork Connector SVG */}
                            <svg width="100%" height="32" style={{ display: 'block' }}>
                              <line x1="50%" y1="0" x2="50%" y2="12" stroke="#27272a" strokeWidth="2" />
                              <line x1="25%" y1="12" x2="75%" y2="12" stroke="#27272a" strokeWidth="2" />
                              <line x1="25%" y1="12" x2="25%" y2="32" stroke="#27272a" strokeWidth="2" />
                              <line x1="75%" y1="12" x2="75%" y2="32" stroke="#27272a" strokeWidth="2" />
                            </svg>

                            {/* Parallel split container */}
                            <div style={{ display: 'flex', width: '100%', gap: '16px', alignItems: 'flex-start' }}>
                              {/* Left column: Data Quality check node */}
                              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '120px' }}>
                                <div
                                  onClick={() => {
                                    setSelectedGraphArtifactId(art.artifact_id);
                                    setSelectedGraphNode('data_quality');
                                  }}
                                  style={{
                                    width: '100%',
                                    backgroundColor: selectedGraphNode === 'data_quality' && isSelectedArtifact ? 'rgba(244, 63, 94, 0.05)' : '#18181b',
                                    border: `1px solid ${selectedGraphNode === 'data_quality' && isSelectedArtifact ? '#f43f5e' : '#27272a'}`,
                                    borderRadius: '8px',
                                    padding: '12px',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease',
                                    boxShadow: selectedGraphNode === 'data_quality' && isSelectedArtifact ? '0 0 10px rgba(244, 63, 94, 0.15)' : 'none',
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontSize: '9px', fontWeight: 600, color: '#f43f5e', textTransform: 'uppercase' }}>
                                      Data Quality
                                    </span>
                                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getDQStatusColor(art) }} />
                                  </div>
                                  <h6 style={{ fontSize: '11px', fontWeight: 600, color: '#fafafa', marginTop: '4px' }}>
                                    {art.data_quality.status}
                                  </h6>
                                  <span style={{ fontSize: '9px', color: '#71717a', display: 'block', marginTop: '2px' }}>
                                    Rules: {art.data_quality.rules_executed} exec
                                  </span>
                                </div>
                              </div>

                              {/* Right column: Main Ingestion pipeline */}
                              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '120px' }}>
                                {renderPipelineStages()}
                              </div>
                            </div>
                          </>
                        ) : (
                          renderPipelineStages()
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Details drawer panel (Right) */}
          <div
            style={{
              width: '450px',
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              minHeight: '100%',
              minWidth: '400px',
              overflowY: 'auto',
            }}
          >
            {selectedGraphNode === 'data_quality' && artLineage.data_quality && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f43f5e' }}>Data Quality Check</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Status:</span> <span style={{ color: getDQStatusColor(artLineage), fontWeight: 600 }}>{artLineage.data_quality.status}</span></div>
                  <div><span style={{ color: '#71717a' }}>Job ID:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.data_quality.job_id}</span></div>
                  <div><span style={{ color: '#71717a' }}>Executed At:</span> <span style={{ color: '#fafafa' }}>{new Date(artLineage.data_quality.created_at).toLocaleString()}</span></div>
                  <div><span style={{ color: '#71717a' }}>Rules Run:</span> <span style={{ color: '#fafafa' }}>{artLineage.data_quality.rules_executed} total ({artLineage.data_quality.rules_failed} failed)</span></div>
                </div>

                {artLineage.data_quality.report_json?.rules && (
                  <div>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>Rules Log</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {artLineage.data_quality.report_json.rules.map((rule: any, idx: number) => {
                        const passed = rule.status === 'PASSED';
                        const warning = rule.status === 'WARNING';
                        let rColor = '#ef4444';
                        let rBg = 'rgba(239, 68, 68, 0.05)';
                        let rBorder = '1px solid rgba(239, 68, 68, 0.2)';
                        if (passed) {
                          rColor = '#10b981';
                          rBg = 'rgba(16, 185, 129, 0.05)';
                          rBorder = '1px solid rgba(16, 185, 129, 0.2)';
                        } else if (warning) {
                          rColor = '#f59e0b';
                          rBg = 'rgba(245, 158, 11, 0.05)';
                          rBorder = '1px solid rgba(245, 158, 11, 0.2)';
                        }

                        return (
                          <div
                            key={idx}
                            style={{
                              padding: '10px 14px',
                              backgroundColor: rBg,
                              border: rBorder,
                              borderRadius: '6px',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '4px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa' }}>
                                {rule.type.replace(/_/g, ' ').toUpperCase()}
                              </span>
                              <span style={{ fontSize: '10px', fontWeight: 700, color: rColor }}>
                                {rule.status}
                              </span>
                            </div>
                            <span style={{ fontSize: '11px', color: '#a1a1aa' }}>
                              Columns: {Array.isArray(rule.columns) ? rule.columns.join(', ') : typeof rule.columns === 'object' ? Object.keys(rule.columns).join(', ') : rule.column || 'N/A'}
                            </span>
                            {rule.failure_count !== undefined && rule.failure_count > 0 && (
                              <span style={{ fontSize: '11px', color: '#ef4444', fontWeight: 500 }}>
                                Failures: {rule.failure_count} rows failed
                              </span>
                            )}
                            {rule.details && (
                              <span style={{ fontSize: '11px', color: '#71717a', fontStyle: 'italic' }}>
                                {rule.details}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div>
                  <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>DQ Report JSON:</h4>
                  <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#a1a1aa', overflowX: 'auto', maxHeight: '250px' }}>
                    <code>{formatJSONVal(artLineage.data_quality.report_json)}</code>
                  </pre>
                </div>
              </div>
            )}

            {selectedGraphNode === 'parent' && activeGraphDetails.parent_job && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#ef4444' }}>Parent Job execution</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Parent Job ID:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{activeGraphDetails.parent_job.job_id}</span></div>
                  <div><span style={{ color: '#71717a' }}>Execution Status:</span> <span style={{ color: getParentStatusColor(), fontWeight: 600 }}>{activeGraphDetails.parent_job.status}</span></div>
                  <div><span style={{ color: '#71717a' }}>Started At:</span> <span style={{ color: '#fafafa' }}>{activeGraphDetails.parent_job.started_at ? new Date(activeGraphDetails.parent_job.started_at).toLocaleString() : 'N/A'}</span></div>
                  <div><span style={{ color: '#71717a' }}>Completed At:</span> <span style={{ color: '#fafafa' }}>{activeGraphDetails.parent_job.completed_at ? new Date(activeGraphDetails.parent_job.completed_at).toLocaleString() : 'N/A'}</span></div>
                </div>

                {activeGraphDetails.parent_job.error_message && (
                  <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '12px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace' }}>
                    <strong>Error Message:</strong><br/>{activeGraphDetails.parent_job.error_message}
                  </div>
                )}

                {activeGraphDetails.parent_job.stages && activeGraphDetails.parent_job.stages.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', textTransform: 'uppercase', marginBottom: '8px' }}>Stage Lineage Logs</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {activeGraphDetails.parent_job.stages.map((st) => (
                        <div key={st.stage_history_id} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #27272a', paddingBottom: '4px', fontSize: '12px' }}>
                          <span style={{ color: '#a1a1aa' }}>{st.stage_name}</span>
                          <span style={{ color: st.status === 'COMPLETED' ? '#10b981' : st.status === 'FAILED' ? '#ef4444' : '#f59e0b' }}>{st.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {selectedGraphNode === 'source' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#0ea5e9' }}>Dataset File Ingestion</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>File Name:</span> <span style={{ color: '#fafafa', fontWeight: 600 }}>{artLineage.artifact_name}</span></div>
                  <div><span style={{ color: '#71717a' }}>Artifact ID:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.artifact_id}</span></div>
                  <div><span style={{ color: '#71717a' }}>Ingestion Status:</span> <span style={{ color: artLineage.status === 'PROCESSED' ? '#10b981' : artLineage.status === 'FAILED' ? '#ef4444' : '#f59e0b', fontWeight: 600 }}>{artLineage.status}</span></div>
                  {artLineage.external_artifact_id && (
                    <div><span style={{ color: '#71717a' }}>External ID:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.external_artifact_id}</span></div>
                  )}
                  <div><span style={{ color: '#71717a' }}>Discovered At:</span> <span style={{ color: '#fafafa' }}>{artLineage.discovered_at ? new Date(artLineage.discovered_at).toLocaleString() : 'N/A'}</span></div>
                  <div><span style={{ color: '#71717a' }}>Processed At:</span> <span style={{ color: '#fafafa' }}>{artLineage.processed_at ? new Date(artLineage.processed_at).toLocaleString() : 'N/A'}</span></div>
                </div>

                {artLineage.failure_reason && (
                  <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '12px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace' }}>
                    <strong>Ingestion Failure Reason:</strong><br/>{artLineage.failure_reason}
                  </div>
                )}

                <div style={{ borderTop: '1px solid #27272a', paddingTop: '12px' }}>
                  <span style={{ fontSize: '12px', color: '#71717a', display: 'block', marginBottom: '8px' }}>All Job Artifacts ({activeGraphDetails.artifacts.length}):</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {activeGraphDetails.artifacts.map((art) => (
                      <div
                        key={art.artifact_id}
                        onClick={() => setSelectedGraphArtifactId(art.artifact_id)}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '6px 10px',
                          backgroundColor: selectedGraphArtifactId === art.artifact_id ? 'rgba(14, 165, 233, 0.08)' : 'rgba(255,255,255,0.02)',
                          border: `1px solid ${selectedGraphArtifactId === art.artifact_id ? '#0ea5e9' : '#27272a'}`,
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '12px',
                        }}
                      >
                        <span style={{ color: '#fafafa', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '200px' }}>{art.artifact_name}</span>
                        <span style={{ color: art.status === 'PROCESSED' ? '#10b981' : '#ef4444' }}>{art.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {selectedGraphNode === 'extraction' && artLineage.artifact_metadata && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#a855f7' }}>Stage 2: Metadata Profile Extraction</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  {artLineage.artifact_metadata.bucket && (
                    <div><span style={{ color: '#71717a' }}>GCS Bucket:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.bucket}</span></div>
                  )}
                  {artLineage.artifact_metadata.object_name && (
                    <div><span style={{ color: '#71717a' }}>File Path:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.artifact_metadata.object_name}</span></div>
                  )}
                  {artLineage.artifact_metadata.collection && (
                    <div><span style={{ color: '#71717a' }}>Firestore Collection:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.collection}</span></div>
                  )}
                  {artLineage.artifact_metadata.sampled_count !== undefined && (
                    <div><span style={{ color: '#71717a' }}>Sampled Records:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.sampled_count}</span></div>
                  )}
                  {artLineage.artifact_metadata.size_bytes !== undefined && (
                    <div><span style={{ color: '#71717a' }}>File Size:</span> <span style={{ color: '#fafafa' }}>{(artLineage.artifact_metadata.size_bytes / 1024).toFixed(2)} KB</span></div>
                  )}
                  {artLineage.artifact_metadata.row_count !== undefined && (
                    <div><span style={{ color: '#71717a' }}>Row Count:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.row_count}</span></div>
                  )}
                  {artLineage.artifact_metadata.column_count !== undefined && (
                    <div><span style={{ color: '#71717a' }}>Column Count:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.column_count}</span></div>
                  )}
                </div>

                <div>
                  <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>Extracted Metadata Profile JSON:</h4>
                  <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#a855f7', overflowX: 'auto', maxHeight: '350px' }}>
                    <code>{formatJSONVal(artLineage.artifact_metadata)}</code>
                  </pre>
                </div>
              </div>
            )}

            {selectedGraphNode === 'vectorization' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#ec4899' }}>Stage 3: Metadata Vectorization</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Semantic Vector Index:</span> <span style={{ color: '#10b981', fontWeight: 600 }}>Active / Synced</span></div>
                  <div><span style={{ color: '#71717a' }}>Embedding Model:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>text-embedding-3-small</span></div>
                  <div><span style={{ color: '#71717a' }}>Vector Store:</span> <span style={{ color: '#fafafa' }}>Schema Catalog Embedding Database</span></div>
                  {artLineage.artifact_metadata && artLineage.artifact_metadata.column_count !== undefined && (
                    <div><span style={{ color: '#71717a' }}>Indexed Columns:</span> <span style={{ color: '#fafafa' }}>{artLineage.artifact_metadata.column_count} fields</span></div>
                  )}
                </div>

                <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.04)', border: '1px solid rgba(236, 72, 153, 0.15)', padding: '12px', borderRadius: '6px', fontSize: '12px', lineHeight: 1.5, color: '#a1a1aa' }}>
                  <strong style={{ color: '#ec4899', display: 'block', marginBottom: '4px' }}>RAG Ingestion Context</strong>
                  The schema fields extracted during Stage 2 are vectorized and registered in the catalog store. During Stage 4, semantic search will match these embeddings against active catalog schemas to compute candidate scores.
                </div>
              </div>
            )}

            {selectedGraphNode === 'inference' && artLineage.inference && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#8b5cf6' }}>LLM Landing Inference</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Matched Table:</span> <span style={{ color: '#fafafa', fontWeight: 600 }}>{targetNameStr}</span></div>
                  <div><span style={{ color: '#71717a' }}>Confidence Score:</span> <span style={{ color: '#fafafa' }}>{Math.round(artLineage.inference.confidence_score * 100)}%</span></div>
                  <div><span style={{ color: '#71717a' }}>Requires Audit:</span> <span style={{ color: artLineage.inference.requires_review ? '#f59e0b' : '#10b981', fontWeight: 600 }}>{artLineage.inference.requires_review ? 'Yes' : 'No'}</span></div>
                </div>

                <div>
                  <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginBottom: '6px' }}>LLM Matching Reasoning:</h4>
                  <p style={{ fontSize: '13px', color: '#a1a1aa', lineHeight: 1.5, backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid #27272a', padding: '12px', borderRadius: '4px', margin: 0 }}>
                    {artLineage.inference.reasoning}
                  </p>
                </div>

                {artLineage.inference.partitioning_recommendation && (
                  <div>
                    <span style={{ fontSize: '12px', color: '#71717a', display: 'block', marginBottom: '4px' }}>Inferred Partition Columns:</span>
                    <span style={{ fontSize: '13px', color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.inference.partitioning_recommendation}</span>
                  </div>
                )}

                {artLineage.inference.column_mapping && (
                  <div>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>Column mapping:</h4>
                    <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#8b5cf6', overflowX: 'auto', maxHeight: '180px' }}>
                      <code>{formatJSONVal(artLineage.inference.column_mapping)}</code>
                    </pre>
                  </div>
                )}
              </div>
            )}

            {selectedGraphNode === 'validation' && artLineage.validation && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#10b981' }}>Schema validation</h3>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Status:</span> <span style={{ color: artLineage.validation.validation_status === 'VALID' ? '#10b981' : '#ef4444', fontWeight: 600 }}>{artLineage.validation.validation_status}</span></div>
                  <div><span style={{ color: '#71717a' }}>Match Rate:</span> <span style={{ color: '#fafafa' }}>{Math.round(artLineage.validation.target_match_percentage)}%</span></div>
                  <div><span style={{ color: '#71717a' }}>Coverage:</span> <span style={{ color: '#fafafa' }}>{Math.round(artLineage.validation.coverage_percentage)}%</span></div>
                  <div><span style={{ color: '#71717a' }}>Mapped:</span> <span style={{ color: '#fafafa' }}>{artLineage.validation.mapped_column_count} / {artLineage.validation.source_column_count} cols</span></div>
                </div>

                {artLineage.validation.report_json && artLineage.validation.report_json.invalid_mappings && (
                  <div>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#ef4444', marginBottom: '8px' }}>Validation errors list:</h4>
                    <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: 'rgba(239,68,68,0.02)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '4px', color: '#ef4444', overflowX: 'auto', maxHeight: '180px' }}>
                      <code>{formatJSONVal(artLineage.validation.report_json.invalid_mappings)}</code>
                    </pre>
                  </div>
                )}

                {artLineage.validation.report_json && (
                  <div>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>Validation report JSON:</h4>
                    <pre style={{ margin: 0, padding: '12px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#a1a1aa', overflowX: 'auto', maxHeight: '180px' }}>
                      <code>{formatJSONVal(artLineage.validation.report_json)}</code>
                    </pre>
                  </div>
                )}
              </div>
            )}

            {selectedGraphNode === 'drift' && artLineage.drift && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f59e0b' }}>Schema Drift Check</h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                  <div><span style={{ color: '#71717a' }}>Drift Status:</span> <span style={{ color: artLineage.drift.drift_status === 'CRITICAL' ? '#ef4444' : artLineage.drift.drift_status === 'NO_DRIFT' ? '#10b981' : '#f59e0b', fontWeight: 600 }}>{artLineage.drift.drift_status}</span></div>
                  <div><span style={{ color: '#71717a' }}>Drift Score:</span> <span style={{ color: '#fafafa' }}>{Math.round(artLineage.drift.drift_score)}%</span></div>
                </div>

                {artLineage.drift.drift_summary && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {artLineage.drift.drift_summary.new_columns && artLineage.drift.drift_summary.new_columns.length > 0 && (
                      <div>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: '#10b981', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>+ Added Columns</span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {artLineage.drift.drift_summary.new_columns.map((c: string) => (
                            <span key={c} style={{ fontSize: '11px', fontFamily: 'monospace', backgroundColor: 'rgba(16,185,129,0.1)', color: '#10b981', padding: '2px 6px', borderRadius: '4px' }}>{c}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {artLineage.drift.drift_summary.removed_columns && artLineage.drift.drift_summary.removed_columns.length > 0 && (
                      <div>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: '#ef4444', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>- Missing Columns</span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {artLineage.drift.drift_summary.removed_columns.map((c: string) => (
                            <span key={c} style={{ fontSize: '11px', fontFamily: 'monospace', backgroundColor: 'rgba(239,68,68,0.1)', color: '#ef4444', padding: '2px 6px', borderRadius: '4px' }}>{c}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {artLineage.drift.drift_summary.datatype_changes && Object.keys(artLineage.drift.drift_summary.datatype_changes).length > 0 && (
                      <div>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: '#f59e0b', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>⚠ Datatype Drifts</span>
                        <pre style={{ margin: 0, padding: '8px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#f59e0b', overflowX: 'auto' }}>
                          <code>{formatJSONVal(artLineage.drift.drift_summary.datatype_changes)}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {selectedGraphNode === 'final' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#10b981' }}>Final Landing Catalog status</h3>
                
                {artLineage.fallback && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      <div><span style={{ color: '#71717a' }}>Fallback Review:</span> <span style={{ color: getFinalStatusColor(artLineage), fontWeight: 600 }}>{artLineage.fallback.request_status}</span></div>
                      <div><span style={{ color: '#71717a' }}>Fallback Table:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.fallback.backup_table_name || 'raw_landing'}</span></div>
                      <div><span style={{ color: '#71717a' }}>Requested:</span> <span style={{ color: '#fafafa' }}>{artLineage.fallback.created_at ? new Date(artLineage.fallback.created_at).toLocaleString() : 'N/A'}</span></div>
                      {artLineage.fallback.approved_by && <div><span style={{ color: '#71717a' }}>Approved By:</span> <span style={{ color: '#fafafa' }}>{artLineage.fallback.approved_by}</span></div>}
                      {artLineage.fallback.rejected_by && <div><span style={{ color: '#71717a' }}>Rejected By:</span> <span style={{ color: '#fafafa' }}>{artLineage.fallback.rejected_by}</span></div>}
                    </div>

                    <div style={{ backgroundColor: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', padding: '12px', borderRadius: '4px', fontSize: '12px' }}>
                      <strong style={{ color: '#f59e0b' }}>Fallback Reason:</strong><br/>
                      <span style={{ color: '#fafafa' }}>{artLineage.fallback.request_reason}</span>
                    </div>

                    {artLineage.fallback.review_notes && (
                      <div style={{ backgroundColor: '#09090b', border: '1px solid #27272a', padding: '12px', borderRadius: '4px', fontSize: '12px' }}>
                        <strong>Review Notes:</strong><br/>
                        <span style={{ color: '#a1a1aa' }}>{artLineage.fallback.review_notes}</span>
                      </div>
                    )}
                  </div>
                )}

                {!artLineage.fallback && artLineage.recommendation && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      <div><span style={{ color: '#71717a' }}>Recommendation Status:</span> <span style={{ color: '#10b981', fontWeight: 600 }}>{artLineage.recommendation.recommendation_status}</span></div>
                    </div>

                    {artLineage.recommendation.explanation && (
                      <div>
                        <strong style={{ fontSize: '12px', color: '#fafafa' }}>AI Explanation:</strong>
                        <p style={{ fontSize: '13px', color: '#a1a1aa', lineHeight: 1.5, margin: '4px 0 0' }}>
                          {artLineage.recommendation.explanation}
                        </p>
                      </div>
                    )}

                    {artLineage.recommendation.deterministic_findings && (
                      <div>
                        <strong style={{ fontSize: '12px', color: '#fafafa', display: 'block', marginBottom: '4px' }}>Deterministic findings:</strong>
                        <pre style={{ margin: 0, padding: '8px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#a1a1aa', overflowX: 'auto', maxHeight: '150px' }}>
                          <code>{formatJSONVal(artLineage.recommendation.deterministic_findings)}</code>
                        </pre>
                      </div>
                    )}

                    {artLineage.recommendation.recommendations_list && (
                      <div>
                        <strong style={{ fontSize: '12px', color: '#fafafa', display: 'block', marginBottom: '4px' }}>Inferred adjustments:</strong>
                        <pre style={{ margin: 0, padding: '8px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#8b5cf6', overflowX: 'auto', maxHeight: '150px' }}>
                          <code>{formatJSONVal(artLineage.recommendation.recommendations_list)}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                )}

                {artLineage.target && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      <div><span style={{ color: '#71717a' }}>Table Name:</span> <span style={{ color: '#fafafa', fontWeight: 600 }}>{artLineage.target.target_name}</span></div>
                      <div><span style={{ color: '#71717a' }}>Engine:</span> <span style={{ color: '#fafafa' }}>{artLineage.target.target_type}</span></div>
                      <div><span style={{ color: '#71717a' }}>Catalog ID:</span> <span style={{ color: '#fafafa', fontFamily: 'monospace' }}>{artLineage.target.target_id}</span></div>
                    </div>

                    {artLineage.target.schema_definition && (
                      <div>
                        <span style={{ fontSize: '12px', color: '#71717a', display: 'block', marginBottom: '4px' }}>Target Table Schema definition:</span>
                        <pre style={{ margin: 0, padding: '10px', fontSize: '11px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '4px', color: '#fafafa', overflowX: 'auto', maxHeight: '250px' }}>
                          <code>{formatJSONVal(artLineage.target.schema_definition)}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Separate jobs into Active vs Completed/Failed/Cancelled/Retried
  const activeJobs = jobs.filter((j) => ['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));
  const historyJobs = jobs.filter((j) => !['RECEIVED', 'VALIDATING', 'RUNNING'].includes(j.status.toUpperCase()));

  if (activeGraphJobId && activeGraphDetails) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {renderInteractiveGraph()}
      </div>
    );
  }

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
                    onOpenGraph={(det) => {
                      setActiveGraphJobId(job.job_id);
                      setActiveGraphDetails(det);
                      if (det.artifacts && det.artifacts.length > 0) {
                        setSelectedGraphArtifactId(det.artifacts[0].artifact_id);
                      }
                      setSelectedGraphNode('source');
                    }}
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
                    onOpenGraph={(det) => {
                      setActiveGraphJobId(job.job_id);
                      setActiveGraphDetails(det);
                      if (det.artifacts && det.artifacts.length > 0) {
                        setSelectedGraphArtifactId(det.artifacts[0].artifact_id);
                      }
                      setSelectedGraphNode('source');
                    }}
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
  details: JobDetailsResponse | null;
  stages: StageHistory[];
  getStatusBadge: (status: string) => React.ReactNode;
  getStatusIcon: (status: string) => React.ReactNode;
  onKill: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  actioning: boolean;
  setActiveTab: (tab: string) => void;
  onOpenGraph: (details: JobDetailsResponse) => void;
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
  onOpenGraph,
}) => {
  const isQualityJob = job.job_type === 'QUALITY';
  return (
    <div style={{ 
      borderBottom: '1px solid #27272a',
      borderLeft: isQualityJob ? '3px solid #f43f5e' : 'none',
    }}>
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
              {isQualityJob && (
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
              {details && details.artifacts && details.artifacts.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                  {/* Data Quality metrics */}
                  {(() => {
                    const artWithDQ = details.artifacts.find((a) => a.data_quality !== null);
                    if (!artWithDQ || !artWithDQ.data_quality) return null;
                    const dqColor = artWithDQ.data_quality.status === 'PASSED' ? '#10b981' : artWithDQ.data_quality.status === 'WARNING' ? '#f59e0b' : '#ef4444';
                    return (
                      <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                        <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Data Quality Check</span>
                        <div
                          style={{
                            fontSize: '20px',
                            fontWeight: 600,
                            color: dqColor,
                            marginTop: '6px',
                          }}
                        >
                          {artWithDQ.data_quality.status}
                        </div>
                        <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                          Passed {artWithDQ.data_quality.rules_executed - artWithDQ.data_quality.rules_failed} / {artWithDQ.data_quality.rules_executed} rules
                        </div>
                      </div>
                    );
                  })()}

                  {/* Validation metrics */}
                  {(() => {
                    const artWithVal = details.artifacts.find((a) => a.validation !== null);
                    if (!artWithVal || !artWithVal.validation) return null;
                    return (
                      <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                        <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Schema Validation</span>
                        <div style={{ fontSize: '20px', fontWeight: 600, color: '#fafafa', marginTop: '6px' }}>
                          {(artWithVal.validation.target_match_percentage ?? 0).toFixed(0)}% Match
                        </div>
                        <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                          Mapped {artWithVal.validation.mapped_column_count} / {artWithVal.validation.source_column_count} source columns
                        </div>
                      </div>
                    );
                  })()}

                  {/* Drift metrics */}
                  {(() => {
                    const artWithDrift = details.artifacts.find((a) => a.drift !== null);
                    if (!artWithDrift || !artWithDrift.drift) return null;
                    return (
                      <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                        <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>Schema Drift</span>
                        <div
                          style={{
                            fontSize: '20px',
                            fontWeight: 600,
                            color: artWithDrift.drift.drift_status === 'CRITICAL' ? '#ef4444' : artWithDrift.drift.drift_status === 'DRIFTED' ? '#f59e0b' : '#10b981',
                            marginTop: '6px',
                          }}
                        >
                          {artWithDrift.drift.drift_status}
                        </div>
                        <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                          Drift Score: {(artWithDrift.drift.drift_score ?? 0).toFixed(1)}%
                        </div>
                      </div>
                    );
                  })()}

                  {/* LLM Confidence */}
                  {(() => {
                    const artWithInference = details.artifacts.find((a) => a.inference !== null);
                    if (!artWithInference || !artWithInference.inference) return null;
                    return (
                      <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '6px', padding: '16px' }}>
                        <span style={{ fontSize: '11px', color: '#71717a', fontWeight: 600, textTransform: 'uppercase' }}>LLM Target Inference</span>
                        <div style={{ fontSize: '20px', fontWeight: 600, color: '#8b5cf6', marginTop: '6px' }}>
                          {((artWithInference.inference.confidence_score ?? 0) * 100).toFixed(0)}% Confidence
                        </div>
                        <div style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '4px' }}>
                          {artWithInference.inference.requires_review ? 'Requires manual audit' : 'Automatic confidence check passed'}
                        </div>
                      </div>
                    );
                  })()}
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

                          {/* Horizontal Progress Lineage Chain */}
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                              marginTop: '8px',
                              padding: '6px 12px',
                              backgroundColor: 'rgba(255,255,255,0.02)',
                              borderRadius: '4px',
                              border: '1px solid rgba(255,255,255,0.03)',
                            }}
                          >
                            <span style={{ fontSize: '10px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Lineage:</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              {/* Stage 1: Inference */}
                              {(() => {
                                let color = '#71717a';
                                let bg = 'rgba(113, 113, 122, 0.1)';
                                let tooltip = 'Inference Pending';
                                if (art.inference) {
                                  const isHighConf = art.inference.confidence_score >= 0.7;
                                  const review = art.inference.requires_review;
                                  if (isHighConf && !review) {
                                    color = '#10b981';
                                    bg = 'rgba(16, 185, 129, 0.15)';
                                    tooltip = `Inference: Passed (Conf: ${Math.round(art.inference.confidence_score * 100)}%)`;
                                  } else {
                                    color = '#f59e0b';
                                    bg = 'rgba(245, 158, 11, 0.15)';
                                    tooltip = `Inference: Review Required (Conf: ${Math.round(art.inference.confidence_score * 100)}%)`;
                                  }
                                }
                                return (
                                  <span title={tooltip} style={{ fontSize: '10px', fontWeight: 600, color, backgroundColor: bg, padding: '2px 6px', borderRadius: '4px', border: `1px solid ${color}33`, cursor: 'help' }}>
                                    Inference
                                  </span>
                                );
                              })()}

                              {/* Arrow */}
                              <span style={{ color: '#27272a', fontSize: '10px' }}>➔</span>

                              {/* Stage 2: Validation */}
                              {(() => {
                                let color = '#71717a';
                                let bg = 'rgba(113, 113, 122, 0.1)';
                                let tooltip = 'Validation Pending';
                                if (art.validation) {
                                  const valid = art.validation.validation_status === 'VALID';
                                  if (valid) {
                                    color = '#10b981';
                                    bg = 'rgba(16, 185, 129, 0.15)';
                                    tooltip = `Validation: Valid (${Math.round(art.validation.target_match_percentage)}% match)`;
                                  } else {
                                    color = '#ef4444';
                                    bg = 'rgba(239, 68, 68, 0.15)';
                                    tooltip = `Validation: Invalid (${Math.round(art.validation.target_match_percentage)}% match)`;
                                  }
                                }
                                return (
                                  <span title={tooltip} style={{ fontSize: '10px', fontWeight: 600, color, backgroundColor: bg, padding: '2px 6px', borderRadius: '4px', border: `1px solid ${color}33`, cursor: 'help' }}>
                                    Validation
                                  </span>
                                );
                              })()}

                              {/* Arrow */}
                              <span style={{ color: '#27272a', fontSize: '10px' }}>➔</span>

                              {/* Stage 3: Drift */}
                              {(() => {
                                let color = '#71717a';
                                let bg = 'rgba(113, 113, 122, 0.1)';
                                let tooltip = 'Drift Pending';
                                if (art.drift) {
                                  const status = art.drift.drift_status?.toUpperCase();
                                  if (status === 'NO_DRIFT') {
                                    color = '#10b981';
                                    bg = 'rgba(16, 185, 129, 0.15)';
                                    tooltip = 'Drift: No Drift';
                                  } else if (status === 'CRITICAL') {
                                    color = '#ef4444';
                                    bg = 'rgba(239, 68, 68, 0.15)';
                                    tooltip = `Drift: Critical Drift (Score: ${Math.round(art.drift.drift_score)}%)`;
                                  } else {
                                    color = '#f59e0b';
                                    bg = 'rgba(245, 158, 11, 0.15)';
                                    tooltip = `Drift: Drifted (Score: ${Math.round(art.drift.drift_score)}%)`;
                                  }
                                }
                                return (
                                  <span title={tooltip} style={{ fontSize: '10px', fontWeight: 600, color, backgroundColor: bg, padding: '2px 6px', borderRadius: '4px', border: `1px solid ${color}33`, cursor: 'help' }}>
                                    Drift
                                  </span>
                                );
                              })()}

                              {/* Arrow */}
                              <span style={{ color: '#27272a', fontSize: '10px' }}>➔</span>

                              {/* Stage 4: Outcome */}
                              {(() => {
                                let color = '#71717a';
                                let bg = 'rgba(113, 113, 122, 0.1)';
                                let tooltip = 'Outcome Pending';
                                if (art.fallback) {
                                  const status = art.fallback.request_status?.toUpperCase();
                                  if (status === 'APPROVED') {
                                    color = '#10b981';
                                    bg = 'rgba(16, 185, 129, 0.15)';
                                    tooltip = `Outcome: Fallback Approved (Table: ${art.fallback.backup_table_name || 'raw_landing'})`;
                                  } else if (status === 'REJECTED') {
                                    color = '#ef4444';
                                    bg = 'rgba(239, 68, 68, 0.15)';
                                    tooltip = 'Outcome: Fallback Rejected';
                                  } else {
                                    color = '#f59e0b';
                                    bg = 'rgba(245, 158, 11, 0.15)';
                                    tooltip = 'Outcome: Fallback Pending Review';
                                  }
                                } else if (art.recommendation) {
                                  const status = art.recommendation.recommendation_status?.toUpperCase();
                                  if (status === 'COMPLETED') {
                                    color = '#10b981';
                                    bg = 'rgba(16, 185, 129, 0.15)';
                                    tooltip = 'Outcome: Recommendation Completed';
                                  } else {
                                    color = '#f59e0b';
                                    bg = 'rgba(245, 158, 11, 0.15)';
                                    tooltip = `Outcome: Recommendation (${art.recommendation.recommendation_status})`;
                                  }
                                } else if (art.target) {
                                  color = '#10b981';
                                  bg = 'rgba(16, 185, 129, 0.15)';
                                  tooltip = `Outcome: Landed (Table: ${art.target.target_name})`;
                                }
                                return (
                                  <span title={tooltip} style={{ fontSize: '10px', fontWeight: 600, color, backgroundColor: bg, padding: '2px 6px', borderRadius: '4px', border: `1px solid ${color}33`, cursor: 'help' }}>
                                    Outcome
                                  </span>
                                );
                              })()}
                            </div>
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

                {details && details.artifacts && details.artifacts.some((art) => art.recommendation !== null) && (
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

                {details && (
                  <button
                    onClick={() => onOpenGraph(details)}
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
                    <span>Open Interactive Stage Graph</span>
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
