from typing import Any

import psycopg

from app.chao.config import DATABASE_URL
from app.chao.services.tool_calls import DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES


def _rows_to_counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    return {name: count for name, count in rows}


def _route_value(route_result: dict[str, Any] | None, key: str) -> Any:
    if not route_result:
        return None

    return route_result.get(key)


def get_console_overview(
    limit: int = 10,
    *,
    search: str | None = None,
    status: str | None = None,
    task_level: str | None = None,
) -> dict[str, Any]:
    where_clauses = []
    params: list[Any] = []

    if search:
        pattern = f"%{search}%"
        where_clauses.append("(task_code ilike %s or title ilike %s)")
        params.extend([pattern, pattern])

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    if task_level:
        where_clauses.append("task_level = %s")
        params.append(task_level)

    where_sql = ""
    if where_clauses:
        where_sql = "where " + " and ".join(where_clauses)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, count(*)
                from tasks
                group by status
                order by status asc
                """
            )
            task_status_rows = cur.fetchall()

            cur.execute(
                """
                select task_level, count(*)
                from tasks
                group by task_level
                order by task_level asc
                """
            )
            task_level_rows = cur.fetchall()

            cur.execute(
                """
                select count(*)
                from confirmations
                where status = 'APPROVED'
                """
            )
            approved_confirmations = cur.fetchone()[0]

            cur.execute("select count(*) from artifacts")
            artifact_count = cur.fetchone()[0]

            cur.execute("select count(*) from data_assets")
            data_asset_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from llm_egress_authorizations
                where status = 'APPROVED'
                  and expires_at > now()
                """
            )
            active_llm_egress_authorization_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where lower(coalesce(result_status, '')) not in ('success', 'started')
                """
            )
            failed_tool_call_count = cur.fetchone()[0]

            cur.execute(
                f"""
                select
                    task_code,
                    title,
                    task_level,
                    status,
                    owner,
                    created_at::text
                from tasks
                {where_sql}
                order by created_at desc
                limit %s
                """,
                (*params, limit),
            )
            recent_task_rows = cur.fetchall()

    return {
        "filters": {
            "search": search,
            "status": status,
            "task_level": task_level,
        },
        "task_status_counts": _rows_to_counts(task_status_rows),
        "task_level_counts": _rows_to_counts(task_level_rows),
        "approved_confirmations": approved_confirmations,
        "artifact_count": artifact_count,
        "data_asset_count": data_asset_count,
        "active_llm_egress_authorization_count": active_llm_egress_authorization_count,
        "failed_tool_call_count": failed_tool_call_count,
        "recent_tasks": [
            {
                "task_code": row[0],
                "title": row[1],
                "task_level": row[2],
                "status": row[3],
                "owner": row[4],
                "created_at": row[5],
            }
            for row in recent_task_rows
        ],
    }


def get_console_approval_queue(limit: int = 20) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.task_code,
                    t.title,
                    t.task_level,
                    t.status,
                    t.owner,
                    t.created_at::text,
                    tr.route_json
                from tasks t
                left join lateral (
                    select route_json
                    from task_routes
                    where task_id = t.id
                    order by created_at desc
                    limit 1
                ) tr on true
                where t.status = 'NEED_CONFIRMATION'
                order by t.created_at asc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "task_code": row[0],
            "title": row[1],
            "task_level": row[2],
            "status": row[3],
            "owner": row[4],
            "created_at": row[5],
            "required_confirmation": _route_value(row[6], "required_confirmation"),
            "required_skills": _route_value(row[6], "required_skills") or [],
            "required_skill_paths": _route_value(row[6], "required_skill_paths") or [],
        }
        for row in rows
    ]


def get_console_audit(limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.task_code,
                    e.event_type,
                    e.from_status,
                    e.to_status,
                    e.summary,
                    e.created_by,
                    e.created_at::text
                from task_events e
                join tasks t on t.id = e.task_id
                order by e.created_at desc
                limit %s
                """,
                (limit,),
            )
            event_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.risk_flag,
                    tc.started_at::text
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                order by tc.started_at desc
                limit %s
                """,
                (limit,),
            )
            tool_call_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    a.artifact_type,
                    a.artifact_uri,
                    a.access_level,
                    a.retention_days,
                    a.created_at::text
                from artifacts a
                join tasks t on t.id = a.task_id
                order by a.created_at desc
                limit %s
                """,
                (limit,),
            )
            artifact_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    da.asset_name,
                    da.asset_type,
                    da.classification,
                    da.owner,
                    da.created_at::text
                from data_assets da
                left join tasks t on t.id = da.task_id
                order by da.created_at desc
                limit %s
                """,
                (limit,),
            )
            data_asset_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    gl.link_type,
                    gl.external_id,
                    gl.url,
                    gl.status,
                    gl.created_by,
                    gl.created_at::text
                from github_links gl
                join tasks t on t.id = gl.task_id
                order by gl.created_at desc
                limit %s
                """,
                (limit,),
            )
            github_link_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    lea.provider,
                    lea.model,
                    lea.data_classification,
                    lea.status,
                    lea.authorized_by,
                    lea.expires_at::text,
                    (lea.status = 'APPROVED' and lea.expires_at > now()) as active,
                    lea.created_at::text
                from llm_egress_authorizations lea
                join tasks t on t.id = lea.task_id
                order by lea.created_at desc
                limit %s
                """,
                (limit,),
            )
            llm_egress_authorization_rows = cur.fetchall()

    return {
        "events": [
            {
                "task_code": row[0],
                "event_type": row[1],
                "from_status": row[2],
                "to_status": row[3],
                "summary": row[4],
                "created_by": row[5],
                "created_at": row[6],
            }
            for row in event_rows
        ],
        "tool_calls": [
            {
                "task_code": row[0],
                "agent_name": row[1],
                "tool_name": row[2],
                "permission_policy": row[3],
                "result_status": row[4],
                "risk_flag": row[5],
                "started_at": row[6],
            }
            for row in tool_call_rows
        ],
        "artifacts": [
            {
                "task_code": row[0],
                "artifact_type": row[1],
                "artifact_uri": row[2],
                "access_level": row[3],
                "retention_days": row[4],
                "created_at": row[5],
            }
            for row in artifact_rows
        ],
        "data_assets": [
            {
                "task_code": row[0],
                "asset_name": row[1],
                "asset_type": row[2],
                "classification": row[3],
                "owner": row[4],
                "created_at": row[5],
            }
            for row in data_asset_rows
        ],
        "github_links": [
            {
                "task_code": row[0],
                "link_type": row[1],
                "external_id": row[2],
                "url": row[3],
                "status": row[4],
                "created_by": row[5],
                "created_at": row[6],
            }
            for row in github_link_rows
        ],
        "llm_egress_authorizations": [
            {
                "task_code": row[0],
                "provider": row[1],
                "model": row[2],
                "data_classification": row[3],
                "status": row[4],
                "authorized_by": row[5],
                "expires_at": row[6],
                "active": row[7],
                "created_at": row[8],
            }
            for row in llm_egress_authorization_rows
        ],
    }


def get_console_github_sync(limit: int = 20) -> dict[str, Any]:
    failed_statuses = ("failure", "failed", "error", "cancelled")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from github_links")
            github_link_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(distinct task_id)
                from github_links
                """
            )
            linked_task_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from task_events
                where event_type = 'github_delivery_recorded'
                """
            )
            github_delivery_event_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from github_links
                where lower(coalesce(status, '')) in ('failure', 'failed', 'error', 'cancelled')
                """
            )
            failed_github_link_count = cur.fetchone()[0]

            cur.execute(
                """
                select link_type, count(*)
                from github_links
                group by link_type
                order by link_type asc
                """
            )
            link_type_rows = cur.fetchall()

            cur.execute(
                """
                select coalesce(nullif(status, ''), 'unknown') as status_name, count(*)
                from github_links
                group by status_name
                order by status_name asc
                """
            )
            status_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    t.title,
                    gl.link_type,
                    gl.external_id,
                    gl.url,
                    gl.status,
                    gl.created_by,
                    gl.created_at::text
                from github_links gl
                join tasks t on t.id = gl.task_id
                order by gl.created_at desc
                limit %s
                """,
                (limit,),
            )
            recent_link_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    e.summary,
                    e.created_by,
                    e.created_at::text
                from task_events e
                join tasks t on t.id = e.task_id
                where e.event_type = 'github_delivery_recorded'
                order by e.created_at desc
                limit %s
                """,
                (limit,),
            )
            recent_event_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    t.title,
                    gl.link_type,
                    gl.external_id,
                    gl.url,
                    gl.status,
                    gl.created_at::text
                from github_links gl
                join tasks t on t.id = gl.task_id
                where lower(coalesce(gl.status, '')) in ('failure', 'failed', 'error', 'cancelled')
                order by gl.created_at desc
                limit %s
                """,
                (limit,),
            )
            failed_link_rows = cur.fetchall()

    return {
        "summary": {
            "github_link_count": github_link_count,
            "linked_task_count": linked_task_count,
            "github_delivery_event_count": github_delivery_event_count,
            "failed_github_link_count": failed_github_link_count,
        },
        "link_type_counts": _rows_to_counts(link_type_rows),
        "status_counts": _rows_to_counts(status_rows),
        "recent_links": [
            {
                "task_code": row[0],
                "title": row[1],
                "link_type": row[2],
                "external_id": row[3],
                "url": row[4],
                "status": row[5],
                "created_by": row[6],
                "created_at": row[7],
            }
            for row in recent_link_rows
        ],
        "recent_delivery_events": [
            {
                "task_code": row[0],
                "summary": row[1],
                "created_by": row[2],
                "created_at": row[3],
            }
            for row in recent_event_rows
        ],
        "failed_links": [
            {
                "task_code": row[0],
                "title": row[1],
                "link_type": row[2],
                "external_id": row[3],
                "url": row[4],
                "status": row[5],
                "created_at": row[6],
            }
            for row in failed_link_rows
        ],
        "failed_statuses": list(failed_statuses),
    }


def get_console_gates(limit: int = 20) -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, count(*)
                from gate_results
                group by status
                order by status asc
                """
            )
            gate_status_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    g.gate_name,
                    g.status,
                    g.command,
                    g.created_at::text
                from gate_results g
                join tasks t on t.id = g.task_id
                order by g.created_at desc
                limit %s
                """,
                (limit,),
            )
            recent_gate_rows = cur.fetchall()

            cur.execute(
                """
                select count(*)
                from tool_calls
                where permission_policy is null or permission_policy = ''
                """
            )
            missing_tool_policy_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where permission_decision = '{}'::jsonb
                """
            )
            empty_tool_decision_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where lower(coalesce(result_status, '')) not in ('success', 'started')
                """
            )
            failed_tool_call_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where lower(coalesce(result_status, '')) = 'started'
                  and finished_at is null
                """
            )
            pending_tool_call_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where lower(coalesce(result_status, '')) = 'started'
                  and finished_at is null
                  and started_at < now() - (%s::int * interval '1 minute')
                """,
                (DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES,),
            )
            stale_tool_call_count = cur.fetchone()[0]

            cur.execute("select count(*) from storage_policies")
            storage_policy_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from data_assets
                where classification is null
                   or classification not in ('D0', 'D1', 'D2', 'D3')
                """
            )
            invalid_data_asset_classification_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from context_chunks
                where data_classification is null
                   or data_classification not in ('D0', 'D1', 'D2', 'D3')
                """
            )
            invalid_context_classification_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from context_chunks
                where ingest_allowed is true and redacted is false
                """
            )
            unredacted_ingest_allowed_count = cur.fetchone()[0]

    return {
        "gate_status_counts": _rows_to_counts(gate_status_rows),
        "recent_gate_results": [
            {
                "task_code": row[0],
                "gate_name": row[1],
                "status": row[2],
                "command": row[3],
                "created_at": row[4],
            }
            for row in recent_gate_rows
        ],
        "tool_permission_audit": {
            "missing_policy_count": missing_tool_policy_count,
            "empty_decision_count": empty_tool_decision_count,
            "failed_tool_call_count": failed_tool_call_count,
            "pending_tool_call_count": pending_tool_call_count,
            "stale_tool_call_count": stale_tool_call_count,
        },
        "data_boundary_audit": {
            "storage_policy_count": storage_policy_count,
            "invalid_data_asset_classification_count": invalid_data_asset_classification_count,
            "invalid_context_classification_count": invalid_context_classification_count,
            "unredacted_ingest_allowed_count": unredacted_ingest_allowed_count,
        },
    }


def get_console_risks(limit: int = 20) -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    task_code,
                    title,
                    task_level,
                    status,
                    owner,
                    created_at::text
                from tasks
                where status in (
                    'NEED_CONFIRMATION',
                    'VALIDATION_FAILED',
                    'MILESTONE_PLANNING'
                )
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            blocked_task_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    g.gate_name,
                    g.status,
                    g.command,
                    g.created_at::text
                from gate_results g
                join tasks t on t.id = g.task_id
                where lower(g.status) not in ('pass', 'passed', 'success', 'ok')
                order by g.created_at desc
                limit %s
                """,
                (limit,),
            )
            failed_gate_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    a.artifact_type,
                    a.artifact_uri,
                    a.created_at::text
                from artifacts a
                join tasks t on t.id = a.task_id
                where a.artifact_type = 'runner_failure_feedback'
                order by a.created_at desc
                limit %s
                """,
                (limit,),
            )
            runner_failure_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.risk_flag,
                    tc.started_at::text
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                where lower(coalesce(tc.result_status, '')) not in ('success', 'started')
                   or tc.permission_policy is null
                   or tc.permission_policy = ''
                   or tc.permission_decision = '{}'::jsonb
                order by tc.started_at desc
                limit %s
                """,
                (limit,),
            )
            tool_risk_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.started_at::text
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                where lower(coalesce(tc.result_status, '')) = 'started'
                  and tc.finished_at is null
                order by tc.started_at desc
                limit %s
                """,
                (limit,),
            )
            pending_tool_call_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.started_at::text,
                    floor(extract(epoch from (now() - tc.started_at)) / 60)::int
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                where lower(coalesce(tc.result_status, '')) = 'started'
                  and tc.finished_at is null
                  and tc.started_at < now() - (%s::int * interval '1 minute')
                order by tc.started_at asc
                limit %s
                """,
                (DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES, limit),
            )
            stale_tool_call_rows = cur.fetchall()

            cur.execute(
                """
                select count(*)
                from data_assets
                where classification is null
                   or classification not in ('D0', 'D1', 'D2', 'D3')
                """
            )
            invalid_data_asset_classification_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from context_chunks
                where data_classification is null
                   or data_classification not in ('D0', 'D1', 'D2', 'D3')
                """
            )
            invalid_context_classification_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from context_chunks
                where ingest_allowed is true and redacted is false
                """
            )
            unredacted_ingest_allowed_count = cur.fetchone()[0]

            cur.execute(
                """
                select
                    t.task_code,
                    gl.link_type,
                    gl.external_id,
                    gl.url,
                    gl.status,
                    gl.created_at::text
                from github_links gl
                join tasks t on t.id = gl.task_id
                where lower(coalesce(gl.status, '')) in (
                    'failure',
                    'failed',
                    'error',
                    'cancelled'
                )
                order by gl.created_at desc
                limit %s
                """,
                (limit,),
            )
            github_risk_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    lea.provider,
                    lea.model,
                    lea.data_classification,
                    lea.status,
                    lea.expires_at::text,
                    lea.authorized_by
                from llm_egress_authorizations lea
                join tasks t on t.id = lea.task_id
                where lea.status in ('APPROVED', 'EXPIRED')
                  and lea.expires_at <= now()
                order by lea.expires_at desc
                limit %s
                """,
                (limit,),
            )
            expired_llm_egress_authorization_rows = cur.fetchall()

    data_boundary_risks = {
        "invalid_data_asset_classification_count": invalid_data_asset_classification_count,
        "invalid_context_classification_count": invalid_context_classification_count,
        "unredacted_ingest_allowed_count": unredacted_ingest_allowed_count,
    }

    return {
        "blocked_tasks": [
            {
                "task_code": row[0],
                "title": row[1],
                "task_level": row[2],
                "status": row[3],
                "owner": row[4],
                "created_at": row[5],
            }
            for row in blocked_task_rows
        ],
        "failed_gates": [
            {
                "task_code": row[0],
                "gate_name": row[1],
                "status": row[2],
                "command": row[3],
                "created_at": row[4],
            }
            for row in failed_gate_rows
        ],
        "runner_failures": [
            {
                "task_code": row[0],
                "artifact_type": row[1],
                "artifact_uri": row[2],
                "created_at": row[3],
            }
            for row in runner_failure_rows
        ],
        "tool_risks": [
            {
                "task_code": row[0],
                "agent_name": row[1],
                "tool_name": row[2],
                "permission_policy": row[3],
                "result_status": row[4],
                "risk_flag": row[5],
                "started_at": row[6],
            }
            for row in tool_risk_rows
        ],
        "pending_tool_calls": [
            {
                "task_code": row[0],
                "agent_name": row[1],
                "tool_name": row[2],
                "permission_policy": row[3],
                "result_status": row[4],
                "started_at": row[5],
            }
            for row in pending_tool_call_rows
        ],
        "stale_tool_calls": [
            {
                "task_code": row[0],
                "agent_name": row[1],
                "tool_name": row[2],
                "permission_policy": row[3],
                "result_status": row[4],
                "started_at": row[5],
                "age_minutes": row[6],
            }
            for row in stale_tool_call_rows
        ],
        "data_boundary_risks": data_boundary_risks,
        "github_risks": [
            {
                "task_code": row[0],
                "link_type": row[1],
                "external_id": row[2],
                "url": row[3],
                "status": row[4],
                "created_at": row[5],
            }
            for row in github_risk_rows
        ],
        "expired_llm_egress_authorizations": [
            {
                "task_code": row[0],
                "provider": row[1],
                "model": row[2],
                "data_classification": row[3],
                "status": row[4],
                "expires_at": row[5],
                "authorized_by": row[6],
            }
            for row in expired_llm_egress_authorization_rows
        ],
        "summary": {
            "blocked_task_count": len(blocked_task_rows),
            "failed_gate_count": len(failed_gate_rows),
            "runner_failure_count": len(runner_failure_rows),
            "tool_risk_count": len(tool_risk_rows),
            "pending_tool_call_count": len(pending_tool_call_rows),
            "stale_tool_call_count": len(stale_tool_call_rows),
            "data_boundary_risk_count": sum(data_boundary_risks.values()),
            "github_risk_count": len(github_risk_rows),
            "expired_llm_egress_authorization_count": len(expired_llm_egress_authorization_rows),
        },
    }
