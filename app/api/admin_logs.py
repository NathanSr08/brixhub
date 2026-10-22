import asyncio
import csv
import io
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.admin import require_admin_auth
from app.core import audit
from app.db.clickhouse import get_redis
from app.repositories import audit_repo, ch_admin, clicks_repo, keys_repo, users_repo

router = APIRouter(prefix="/admin", tags=["admin-logs"])


def _filters(**kw) -> dict:
    f = {k: v for k, v in kw.items() if v not in ("", None, False, 0)}
    if f.get("from_ts"):
        f["from_ts"] = f["from_ts"].replace("T", " ")
    if f.get("to_ts"):
        f["to_ts"] = f["to_ts"].replace("T", " ")
    return f


def _cond_for(table: str, filters: dict) -> str:
    if table.endswith("api_logs"):
        return audit_repo.where_literal(filters or {})
    if table.endswith("profile_clicks"):
        return clicks_repo.where_literal(filters or {})
    return "1"


# ============================== LOGS D'AUDIT ============================== #
@router.get("/api/logs", dependencies=[Depends(require_admin_auth)])
async def api_logs(
    q: str = "", actor_type: str = "all", actor_id: str = "", ip: str = "",
    method: str = "", path: str = "", tag: str = "all", status_class: str = "",
    errors_only: bool = False, min_latency: int = 0,
    from_ts: str = "", to_ts: str = "",
    exclude_panel: bool = True, exclude_admin: bool = True,
    limit: int = 100, offset: int = 0,
):
    f = _filters(q=q, actor_type=actor_type, actor_id=actor_id, ip=ip, method=method,
                 path=path, tag=tag, status_class=status_class, errors_only=errors_only,
                 min_latency=min_latency, from_ts=from_ts, to_ts=to_ts)
    f["exclude_panel"] = exclude_panel
    f["exclude_admin"] = exclude_admin
    limit = max(1, min(limit, 500))
    rows = await run_in_threadpool(audit_repo.list_logs, f, limit, offset)
    total = await run_in_threadpool(audit_repo.count_logs, f)
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


@router.get("/api/logs/stats", dependencies=[Depends(require_admin_auth)])
async def api_logs_stats(hours: int = 24, exclude_admin: bool = True):
    await audit.flush_now()
    return await run_in_threadpool(audit_repo.stats, max(1, min(hours, 720)), exclude_admin)


@router.get("/api/logs/tags", dependencies=[Depends(require_admin_auth)])
async def api_logs_tags():
    return await run_in_threadpool(audit_repo.distinct_tags)


@router.get("/api/logs/partitions", dependencies=[Depends(require_admin_auth)])
async def api_logs_partitions(target: str = "audit"):
    tables = ch_admin.resolve_targets([target])
    if not tables:
        return []
    return await run_in_threadpool(ch_admin.partitions, tables[0])


@router.get("/api/logs/export.csv", dependencies=[Depends(require_admin_auth)])
async def api_logs_export(
    q: str = "", actor_type: str = "all", actor_id: str = "", ip: str = "",
    method: str = "", path: str = "", tag: str = "all", status_class: str = "",
    errors_only: bool = False, min_latency: int = 0,
    from_ts: str = "", to_ts: str = "", max_rows: int = 50000,
):
    f = _filters(q=q, actor_type=actor_type, actor_id=actor_id, ip=ip, method=method,
                 path=path, tag=tag, status_class=status_class, errors_only=errors_only,
                 min_latency=min_latency, from_ts=from_ts, to_ts=to_ts)
    rows = await run_in_threadpool(audit_repo.list_logs, f, min(max_rows, 200000), 0)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ts", "actor_type", "actor_id", "actor_label", "ip", "method", "path",
                "query", "status", "latency_ms", "tag", "request_id", "user_agent",
                "referer", "error"])
    for r in rows:
        w.writerow([r["ts"], r["actor_type"], r["actor_id"], r["actor_label"], r["ip"],
                    r["method"], r["path"], r["query"], r["status"], r["latency_ms"],
                    r["tag"], r["request_id"], r["user_agent"], r["referer"], r["error"]])
    return PlainTextResponse(
        buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="brixhub_logs.csv"'})


@router.get("/api/logs/stream", dependencies=[Depends(require_admin_auth)])
async def api_logs_stream(request: Request, actor_type: str = "all", q: str = "",
                          exclude_admin: bool = True):
    async def gen():
        last = time.time()
        yield "retry: 3000\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                await audit.flush_now()
                rows = await run_in_threadpool(audit_repo.logs_since, last, 200, exclude_admin)
            except Exception:
                rows = []
            if rows:
                last = time.time()
                for r in rows:
                    if actor_type != "all" and r["actor_type"] != actor_type:
                        continue
                    if q and q.lower() not in json.dumps(r, default=str).lower():
                        continue
                    yield f"data: {json.dumps(r, default=str)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.get("/api/logs/{log_id}", dependencies=[Depends(require_admin_auth)])
async def api_log_detail(log_id: str):
    row = await run_in_threadpool(audit_repo.get_log, log_id)
    return row or {"error": "introuvable"}


# ============================== PURGE ============================== #
class PurgeRequest(BaseModel):
    targets: list[str] = ["audit"]
    mode: str = "filter"          # filter | partitions | all
    partitions: list[str] = []
    filters: dict = {}


@router.post("/api/logs/purge/preview", dependencies=[Depends(require_admin_auth)])
async def api_purge_preview(req: PurgeRequest):
    tables = ch_admin.resolve_targets(req.targets)
    out = []
    for t in tables:
        info = await run_in_threadpool(ch_admin.table_info, t)
        item = {"target": t, **info, "a_supprimer": 0, "partitions": []}
        if req.mode == "filter":
            cond = _cond_for(t, req.filters)
            item["a_supprimer"] = await run_in_threadpool(ch_admin.count_where, t, cond)
            item["condition"] = cond[:400]
        elif req.mode == "partitions":
            parts = await run_in_threadpool(ch_admin.partitions, t)
            item["partitions"] = parts
            item["a_supprimer"] = sum(p["lignes"] for p in parts
                                      if p["partition"] in (req.partitions or []))
        else:
            item["a_supprimer"] = info["lignes"]
        out.append(item)
    return {"mode": req.mode, "targets": out}


@router.post("/api/logs/purge", dependencies=[Depends(require_admin_auth)])
async def api_purge(req: PurgeRequest, request: Request):
    tables = ch_admin.resolve_targets(req.targets)
    done = []
    for t in tables:
        if req.mode == "all":
            await run_in_threadpool(ch_admin.truncate, t)
            done.append({"target": t, "action": "truncate"})
        elif req.mode == "partitions":
            n = await run_in_threadpool(ch_admin.drop_partitions, t, req.partitions or [])
            done.append({"target": t, "action": "drop_partitions", "partitions": n})
        else:
            cond = _cond_for(t, req.filters)
            await run_in_threadpool(ch_admin.purge_where, t, cond)
            done.append({"target": t, "action": "delete", "condition": cond[:400]})
    audit_repo.log_admin_action("admin", f"purge_{req.mode}", ",".join(req.targets), "",
                                audit.client_ip(request))
    return {"status": "ok", "done": done}


@router.post("/api/logs/optimize", dependencies=[Depends(require_admin_auth)])
async def api_optimize(req: PurgeRequest):
    tables = ch_admin.resolve_targets(req.targets)
    for t in tables:
        await run_in_threadpool(ch_admin.optimize, t)
    return {"status": "ok", "tables": tables}


# ============================== CLICS FICHES ============================== #
@router.get("/api/clicks", dependencies=[Depends(require_admin_auth)])
async def api_clicks(
    q: str = "", actor_type: str = "all", actor_id: str = "", ip: str = "",
    profile_ref: str = "", from_ts: str = "", to_ts: str = "",
    limit: int = 100, offset: int = 0,
):
    f = _filters(q=q, actor_type=actor_type, actor_id=actor_id, ip=ip,
                 profile_ref=profile_ref, from_ts=from_ts, to_ts=to_ts)
    limit = max(1, min(limit, 500))
    rows = await run_in_threadpool(clicks_repo.list_clicks, f, limit, offset)
    total = await run_in_threadpool(clicks_repo.count_clicks, f)
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


@router.get("/api/clicks/stats", dependencies=[Depends(require_admin_auth)])
async def api_clicks_stats(hours: int = 720):
    return await run_in_threadpool(clicks_repo.stats, max(1, min(hours, 8760)))


@router.get("/api/clicks/actor/{actor_type}/{actor_id}", dependencies=[Depends(require_admin_auth)])
async def api_clicks_actor(actor_type: str, actor_id: str, limit: int = 30):
    return await run_in_threadpool(clicks_repo.clicks_for_actor, actor_type, actor_id, limit)


@router.get("/api/profiles/{profile_ref}", dependencies=[Depends(require_admin_auth)])
async def api_profile(profile_ref: str, hours: int = 2160):
    return await run_in_threadpool(clicks_repo.profile_summary, profile_ref, hours)


# ============================== ACTEURS ============================== #
@router.get("/api/actors/{actor_type}/{actor_id}", dependencies=[Depends(require_admin_auth)])
async def api_actor_profile(actor_type: str, actor_id: str, hours: int = 720):
    prof = await run_in_threadpool(audit_repo.actor_profile, actor_type, actor_id, hours)
    prof["actor_type"] = actor_type
    prof["actor_id"] = actor_id
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = get_redis()

    if actor_type == "user":
        u = await run_in_threadpool(users_repo.get_by_id, actor_id)
        if u:
            prof["entity"] = {"kind": "user", "email": u["email"], "plan": u["plan"],
                              "is_active": u["is_active"], "created_at": u["created_at"],
                              "api_key_id": u.get("api_key_id") or ""}
            try:
                prof["quota_used_today"] = int(await r.get(f"quota:user:{actor_id}:{today}") or 0)
            except Exception:
                prof["quota_used_today"] = 0
            if u.get("api_key_id"):
                k = await run_in_threadpool(keys_repo.get_by_id, u["api_key_id"])
                if k:
                    prof["linked_key"] = {"key_id": k["key_id"], "label": k["label"],
                                          "plan": k["plan"], "is_active": k["is_active"]}

    elif actor_type == "api":
        k = await run_in_threadpool(keys_repo.get_by_id, actor_id)
        if k:
            prof["entity"] = {"kind": "api_key", "label": k["label"],
                              "owner_email": k["owner_email"], "plan": k["plan"],
                              "is_active": k["is_active"], "created_at": k["created_at"]}

    elif actor_type in ("guest", "bot"):
        prof["entity"] = {"kind": "guest", "label": "Visiteur anonyme"}
        try:
            prof["quota_used_today"] = int(await r.get(f"quota:ip:{actor_id}:{today}") or 0)
        except Exception:
            prof["quota_used_today"] = 0

    prof["recent_logs"] = await run_in_threadpool(audit_repo.actor_logs, actor_type, actor_id, 50)
    prof["clicks"] = await run_in_threadpool(clicks_repo.clicks_for_actor, actor_type, actor_id, 30)
    return prof


@router.post("/api/actors/{actor_type}/{actor_id}/reset-quota",
             dependencies=[Depends(require_admin_auth)])
async def api_actor_reset_quota(actor_type: str, actor_id: str, request: Request):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = get_redis()
    if actor_type == "user":
        await r.delete(f"quota:user:{actor_id}:{today}")
    elif actor_type in ("guest", "bot"):
        await r.delete(f"quota:ip:{actor_id}:{today}")
    elif actor_type == "api":
        ks = await r.keys(f"quota:{actor_id}:*")
        if ks:
            await r.delete(*ks)
    audit_repo.log_admin_action("admin", "reset_quota", actor_type, actor_id,
                                audit.client_ip(request))
    return {"status": "ok"}
