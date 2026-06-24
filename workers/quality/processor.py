import json
import logging
import re
import math
from datetime import datetime, UTC
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.artifact_record import ArtifactRecord
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.data_quality_job import DataQualityJob
from app.models.db.data_quality_report import DataQualityReport
from app.constants.job_status import JobStatus

from app.connectors.registry import CONNECTORS
from app.parsers.registry import PARSERS
from app.services.job_stage_service import start_stage, complete_stage, fail_stage

logger = logging.getLogger("data_quality")


def process_data_quality(
    job_id: str,
    parent_job_id: str,
    source_id: str,
    artifact_id: str,
    db: Session
) -> DataQualityReport:
    job_uuid = UUID(job_id)
    parent_job_uuid = UUID(parent_job_id)
    source_uuid = UUID(source_id)
    artifact_uuid = UUID(artifact_id)

    logger.info(f"Processor starting data quality validation for quality_job={job_id} parent_job={parent_job_id}")
    
    # Update Job status and start stage
    job = db.get(Job, job_uuid)
    if job is None:
        raise ValueError(f"Quality Job not found: {job_id}")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.current_stage = "Data Quality Processing"
    db.commit()

    stage = start_stage(job_uuid, "Data Quality Validation", db)

    try:
        source = db.get(Source, source_uuid)
        if source is None:
            raise ValueError(f"Source not found: {source_id}")

        artifact_record = db.get(ArtifactRecord, artifact_uuid)
        if artifact_record is None:
            raise ValueError(f"ArtifactRecord not found: {artifact_id}")

        config = source.configuration
        if not config:
            raise ValueError("Processing configuration not found for source")

        # Load sampling configuration
        dq_sampling = config.config_content.get("data_quality_sampling", {})
        sample_ratio = dq_sampling.get("sample_ratio", None)
        random_sample = dq_sampling.get("random_sample", False)

        # Retrieve connector and extract raw data
        connector = CONNECTORS.get(source.source_type)
        if connector is None:
            raise Exception(f"No connector registered for source type: {source.source_type}")

        # Map ArtifactRecord back to Domain Artifact for connector
        from app.models.domain.artifact import Artifact
        domain_artifact = Artifact(
            external_id=artifact_record.external_artifact_id,
            artifact_name=artifact_record.artifact_name,
            last_modified=artifact_record.discovered_at.isoformat(),
            metadata=artifact_record.artifact_metadata
        )

        logger.info(f"Extracting dataset (sample_ratio={sample_ratio}, random={random_sample})")
        raw_data = connector.extract_full(
            source=source,
            artifact=domain_artifact,
            sample_ratio=sample_ratio,
            random_sample=random_sample
        )

        # Parse raw data
        parser = PARSERS.get(raw_data.format_type)
        if parser is None:
            raise Exception(f"No parser registered for format: {raw_data.format_type}")

        dataset = parser.parse(raw_data)
        records = dataset.records or []
        total_rows = len(records)
        logger.info(f"Loaded {total_rows} records for validation.")

        rules = config.config_content.get("data_quality_rules", [])
        rules_executed = 0
        rules_failed = 0
        rule_results = []
        highest_severity_failed = None  # INFO, WARNING, FAILED

        # Query previous successful run row count for Volume Change Check
        prev_row_count = 0
        prev_job_stmt = (
            select(Job)
            .where(
                Job.source_id == source_uuid,
                Job.status == JobStatus.COMPLETED
            )
        )
        if job.created_at:
            prev_job_stmt = prev_job_stmt.where(Job.created_at < job.created_at)
        prev_job_stmt = prev_job_stmt.order_by(Job.created_at.desc())
        prev_job = db.execute(prev_job_stmt).scalars().first()
        if prev_job:
            # Look inside Dataset Acquisition stage history details
            prev_stage = db.execute(
                select(JobStageHistory)
                .where(
                    JobStageHistory.job_id == prev_job.job_id,
                    JobStageHistory.stage_name == "Dataset Acquisition"
                )
            ).scalar_one_or_none()
            if prev_stage and prev_stage.details and "artifacts" in prev_stage.details:
                for art in prev_stage.details["artifacts"]:
                    if art.get("external_id") == artifact_record.external_artifact_id or art.get("name") == artifact_record.artifact_name:
                        prev_row_count = art.get("record_count", 0)
                        break

        # Process each rule
        for rule in rules:
            rule_type = rule.get("type")
            severity = rule.get("severity", "FAILED").upper()
            rule_passed = True
            failure_count = 0
            metric_details = {}

            rules_executed += 1

            if rule_type == "null_check":
                columns = rule.get("columns", [])
                allowed_null_ratio = rule.get("allowed_null_ratio", 0.0)
                metric_details["null_ratios"] = {}
                
                for col in columns:
                    null_count = sum(1 for r in records if r.get(col) is None or str(r.get(col)).strip() == "")
                    null_ratio = null_count / total_rows if total_rows > 0 else 0.0
                    metric_details["null_ratios"][col] = {
                        "null_count": null_count,
                        "null_ratio": null_ratio
                    }
                    if null_ratio > allowed_null_ratio:
                        rule_passed = False
                        failure_count += null_count

            elif rule_type == "uniqueness_check":
                columns = rule.get("columns", [])
                keys = []
                for r in records:
                    key = tuple(r.get(col) for col in columns)
                    keys.append(key)
                
                unique_keys = set(keys)
                duplicate_count = len(keys) - len(unique_keys)
                metric_details["duplicate_count"] = duplicate_count
                if duplicate_count > 0:
                    rule_passed = False
                    failure_count = duplicate_count

            elif rule_type == "data_type_validity_check" or rule_type == "type_validity_check":
                # Expects 'columns' to be dict mapping column to expected type: {"age": "int", "price": "float"}
                columns_config = rule.get("columns", {})
                metric_details["type_failures"] = {}

                for col, expected_type in columns_config.items():
                    col_failures = 0
                    for r in records:
                        val = r.get(col)
                        if val is None or str(val).strip() == "":
                            continue  # skip nulls; completeness handles this
                        
                        try:
                            if expected_type == "int":
                                int(str(val))
                            elif expected_type == "float":
                                float(str(val))
                            elif expected_type == "boolean":
                                val_str = str(val).lower().strip()
                                if val_str not in ["true", "false", "1", "0", "yes", "no"]:
                                    raise ValueError()
                            elif expected_type == "datetime":
                                # Support ISO parses
                                datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                        except Exception:
                            col_failures += 1

                    metric_details["type_failures"][col] = col_failures
                    if col_failures > 0:
                        rule_passed = False
                        failure_count += col_failures

            elif rule_type == "boundary_range_check" or rule_type == "boundary_check":
                # Expects 'columns' to be dict mapping column to limits: {"age": {"min": 0, "max": 120}}
                columns_config = rule.get("columns", {})
                metric_details["boundary_failures"] = {}

                for col, limits in columns_config.items():
                    col_failures = 0
                    min_val = limits.get("min", -math.inf)
                    max_val = limits.get("max", math.inf)

                    for r in records:
                        val = r.get(col)
                        if val is None or str(val).strip() == "":
                            continue
                        try:
                            num_val = float(str(val))
                            if num_val < min_val or num_val > max_val:
                                col_failures += 1
                        except ValueError:
                            col_failures += 1  # count non-numeric as failure

                    metric_details["boundary_failures"][col] = col_failures
                    if col_failures > 0:
                        rule_passed = False
                        failure_count += col_failures

            elif rule_type == "regex_pattern_check" or rule_type == "regex_check":
                # Expects 'columns' to be dict mapping column to regex: {"email": "^\\S+@\\S+\\.\\S+$"}
                columns_config = rule.get("columns", {})
                metric_details["regex_failures"] = {}

                for col, pattern in columns_config.items():
                    col_failures = 0
                    regex = re.compile(pattern)

                    for r in records:
                        val = r.get(col)
                        if val is None:
                            col_failures += 1
                            continue
                        if not regex.match(str(val)):
                            col_failures += 1

                    metric_details["regex_failures"][col] = col_failures
                    if col_failures > 0:
                        rule_passed = False
                        failure_count += col_failures

            elif rule_type == "set_membership_check" or rule_type == "set_membership":
                # Expects 'columns' to be dict mapping column to list of allowed values: {"status": ["ACTIVE", "INACTIVE"]}
                columns_config = rule.get("columns", {})
                metric_details["membership_failures"] = {}

                for col, allowed_list in columns_config.items():
                    col_failures = 0
                    allowed_set = set(allowed_list)

                    for r in records:
                        val = r.get(col)
                        if val not in allowed_set:
                            col_failures += 1

                    metric_details["membership_failures"][col] = col_failures
                    if col_failures > 0:
                        rule_passed = False
                        failure_count += col_failures

            elif rule_type == "freshness_check":
                column = rule.get("column")
                max_age_hours = rule.get("max_age_hours", 24.0)
                newest_dt = None

                for r in records:
                    val = r.get(column)
                    if val is not None and str(val).strip() != "":
                        try:
                            # Replace Z with UTC offset
                            parsed_dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                            if newest_dt is None or parsed_dt > newest_dt:
                                newest_dt = parsed_dt
                        except ValueError:
                            pass

                metric_details["column"] = column
                if newest_dt is None:
                    rule_passed = False
                    metric_details["newest_timestamp"] = None
                    metric_details["age_hours"] = None
                    failure_count = 1
                else:
                    newest_dt_utc = newest_dt.astimezone(UTC)
                    now_utc = datetime.now(UTC)
                    age_hours = (now_utc - newest_dt_utc).total_seconds() / 3600.0
                    metric_details["newest_timestamp"] = newest_dt_utc.isoformat()
                    metric_details["age_hours"] = age_hours
                    if age_hours > max_age_hours:
                        rule_passed = False
                        failure_count = 1

            elif rule_type == "volume_change_check":
                max_change_percentage = rule.get("max_change_percentage", 25.0)
                metric_details["current_count"] = total_rows
                metric_details["previous_count"] = prev_row_count

                if prev_row_count > 0:
                    percentage_change = abs(total_rows - prev_row_count) / prev_row_count * 100.0
                else:
                    percentage_change = 0.0

                metric_details["percentage_change"] = percentage_change
                if percentage_change > max_change_percentage:
                    rule_passed = False
                    failure_count = 1

            # Save result entry
            result_status = "PASSED" if rule_passed else "FAILED"
            rule_results.append({
                "rule_type": rule_type,
                "severity": severity,
                "status": result_status,
                "failure_count": failure_count,
                "metrics": metric_details
            })

            if not rule_passed:
                rules_failed += 1
                # Update highest severity failed
                if severity == "FAILED":
                    highest_severity_failed = "FAILED"
                elif severity == "WARNING" and highest_severity_failed != "FAILED":
                    highest_severity_failed = "WARNING"
                elif severity == "INFO" and highest_severity_failed not in ["FAILED", "WARNING"]:
                    highest_severity_failed = "INFO"

        # Determine report overall status
        if rules_failed == 0:
            final_status = "PASSED"
        else:
            if highest_severity_failed == "FAILED":
                final_status = "FAILED"
            elif highest_severity_failed == "WARNING":
                final_status = "WARNING"
            else:
                final_status = "PASSED"  # INFO alone does not fail the run

        report_json = {
            "overall_status": final_status,
            "total_rows": total_rows,
            "rules_executed": rules_executed,
            "rules_failed": rules_failed,
            "rules": rule_results,
            "validated_at": datetime.now(UTC).isoformat()
        }

        # Idempotent write: Check if a report already exists for this quality job ID and update/overwrite it
        existing_report = db.execute(
            select(DataQualityReport).where(DataQualityReport.job_id == job_uuid)
        ).scalar_one_or_none()

        if existing_report:
            existing_report.status = final_status
            existing_report.rules_executed = rules_executed
            existing_report.rules_failed = rules_failed
            existing_report.report_json = report_json
            existing_report.created_at = datetime.now(UTC)
            report = existing_report
            logger.info(f"Updated existing Data Quality Report {report.report_id}")
        else:
            report = DataQualityReport(
                job_id=job_uuid,
                artifact_id=artifact_uuid,
                status=final_status,
                rules_executed=rules_executed,
                rules_failed=rules_failed,
                report_json=report_json
            )
            db.add(report)
            logger.info(f"Created new Data Quality Report")

        db.commit()
        db.refresh(report)

        # Complete job & stage
        job.status = JobStatus.COMPLETED if final_status != "FAILED" else JobStatus.FAILED
        job.completed_at = datetime.now(UTC)
        job.current_stage = "Data Quality Completed"
        db.commit()

        complete_stage(
            stage.stage_history_id,
            db,
            {
                "report_id": str(report.report_id),
                "status": final_status,
                "rules_executed": rules_executed,
                "rules_failed": rules_failed
            }
        )

        # Publish quality-check-completed event
        from app.pubsub.publisher import publish_quality_check_completed
        try:
            publish_quality_check_completed(
                job_id=job.job_id,
                source_id=job.source_id,
                artifact_id=artifact_record.artifact_id,
                status=final_status,
                rules_executed=rules_executed,
                rules_failed=rules_failed
            )
        except Exception as pub_err:
            logger.error(f"Failed to publish quality-check-completed event: {pub_err}")

        logger.info(f"Data Quality validation complete. Status={final_status}")
        return report

    except Exception as e:
        logger.error(f"Error during data quality validation: {e}")
        try:
            fail_stage(stage.stage_history_id, e, db)
        except Exception:
            pass
        
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(UTC)
        job.error_message = str(e)
        db.commit()
        raise
