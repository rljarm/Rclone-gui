"""Rclone hub backend implemented with FastAPI.

This service provides a friendly REST API on top of rclone's remote‑control protocol.
It reads a JSON configuration file listing the target nodes (rclone agents) and
optionally an API key for authentication.  Jobs are stored in a SQLite database
so that progress can survive restarts.

Run with:

    uvicorn app:app --host 0.0.0.0 --port 8000

When deploying in Docker, mount a volume at /data for the SQLite database and
provide HUB_CONFIG and HUB_DB_PATH environment variables if desired.
"""

import asyncio
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

CONFIG_PATH = os.environ.get("HUB_CONFIG", os.path.join(os.path.dirname(__file__), "config.json"))
DB_PATH = os.environ.get("HUB_DB_PATH", os.path.join(os.path.dirname(__file__), "hub.db"))


def load_config() -> Dict[str, Any]:
    """Load the JSON configuration file.

    The configuration has the following structure:
        {
            "nodes": [
                {"id": "home-nas", "name": "Home NAS", "ip": "100.x.y.z", "port": 55743},
                ...
            ],
            "api_key": "optional-secret"
        }
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"nodes": [], "api_key": ""}
    # index by id for quick lookup
    nodes = {}
    for node in data.get("nodes", []):
        nodes[node["id"]] = node
    return {"nodes": nodes, "api_key": data.get("api_key", "")}


CONFIG = load_config()


def reload_config() -> None:
    """Reload configuration from file (can be called on demand)."""
    global CONFIG
    CONFIG = load_config()


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Return a thread‑safe SQLite connection in WAL mode."""
    con = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    # create jobs table if it doesn't exist
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs(
            uid TEXT PRIMARY KEY,
            node TEXT,
            kind TEXT,
            src TEXT,
            dst TEXT,
            flags TEXT,
            rc_jobid INTEGER,
            status TEXT,
            bytes_done INTEGER,
            files_done INTEGER,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    return con


DB_CONN = get_db()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

async def rc_call(node: Dict[str, Any], path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 300.0) -> Any:
    """Call a JSON‑RPC method on the specified rclone node.

    :param node: a node dictionary with keys `ip` and `port`
    :param path: rc path like "operations/list"
    :param payload: JSON payload to send (will be {} if None)
    :param timeout: request timeout in seconds
    :raises HTTPException: on HTTP or rclone error
    :returns: the JSON decoded response
    """
    url = f"http://{node['ip']}:{node['port']}/rc/{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, json=payload or {})
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Error contacting {node['id']}: {exc}") from exc
    if response.status_code != 200:
        raise HTTPException(502, f"rc error {response.status_code}: {response.text}")
    return response.json()


def save_job(job: Dict[str, Any]) -> None:
    """Insert or update a job record in the database."""
    DB_CONN.execute(
        """
        INSERT OR REPLACE INTO jobs(uid, node, kind, src, dst, flags, rc_jobid, status, bytes_done, files_done, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job["uid"],
            job["node"],
            job["kind"],
            job["src"],
            job["dst"],
            json.dumps(job.get("flags", {})),
            job.get("rc_jobid"),
            job.get("status", "running"),
            job.get("bytes_done", 0),
            job.get("files_done", 0),
            job.get("created_at", int(time.time())),
            int(time.time()),
        ),
    )


async def start_operation(kind: str, node_id: str, src: str, dst: str, flags: Dict[str, Any]) -> Dict[str, str]:
    """Start a copy/move/sync operation on a node and record it as a job.

    The function maps a small set of flags from the API into the rclone RC payload.
    It then calls the appropriate rclone endpoint (`operations/copyfs`, `operations/movefs` or
    `sync/sync`) with `_async` set to true.  The returned rclone `jobid` is stored
    along with a generated job UID.
    """
    node = CONFIG["nodes"].get(node_id)
    if not node:
        raise HTTPException(404, f"Unknown node {node_id}")
    uid = str(uuid.uuid4())
    # map input flags to rclone payload
    op_payload: Dict[str, Any] = {"_async": True, "srcFs": src, "dstFs": dst}
    # whitelist of supported flags and their RC equivalents
    flag_map = {
        "checksum": "checksum",
        "sizeOnly": "sizeOnly",
        "transfers": "transfers",
        "checkers": "checkers",
        "bwlimit": "bwlimit",
        "dryRun": "dryRun",
        "ignoreExisting": "ignoreExisting",
        "fastList": "fastList",
    }
    for key, value in flags.items():
        if key in flag_map:
            op_payload[flag_map[key]] = value
    # determine RC path based on kind
    path_map = {"copy": "operations/copyfs", "move": "operations/movefs", "sync": "sync/sync"}
    if kind not in path_map:
        raise HTTPException(400, f"Unsupported job type: {kind}")
    rc_path = path_map[kind]
    # call rclone
    result = await rc_call(node, rc_path, op_payload)
    rc_jobid = result.get("jobid")
    job_record = {
        "uid": uid,
        "node": node_id,
        "kind": kind,
        "src": src,
        "dst": dst,
        "flags": flags,
        "rc_jobid": rc_jobid,
        "status": "running",
        "created_at": int(time.time()),
    }
    save_job(job_record)
    return {"jobUid": uid}


# ---------------------------------------------------------------------------
# FastAPI app and dependencies
# ---------------------------------------------------------------------------

app = FastAPI(title="Rclone Hub API", version="1.0.0")


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Dependency to verify optional API key."""
    expected = CONFIG.get("api_key")
    if expected:
        if x_api_key != expected:
            raise HTTPException(401, "Invalid API key")


@app.on_event("startup")
async def on_startup() -> None:
    """Reload configuration on startup."""
    reload_config()


@app.get("/v1/nodes", dependencies=[Depends(verify_api_key)])
async def list_nodes() -> Any:
    """Return health and stats for each configured node.

    Calls `core/stats` on each node.  If a node cannot be reached an object
    with `ok: false` will be returned.
    """
    results = []
    for node_id, node in CONFIG["nodes"].items():
        entry: Dict[str, Any] = {"id": node_id, "name": node.get("name")}
        try:
            stats = await rc_call(node, "core/stats", {})
            entry.update({"ok": True, "stats": stats})
        except HTTPException:
            entry.update({"ok": False})
        results.append(entry)
    return results


@app.get("/v1/remotes", dependencies=[Depends(verify_api_key)])
async def list_remotes(node: str = Query(..., description="Node ID")) -> Any:
    """List rclone remotes on a given node (config/listremotes)."""
    target = CONFIG["nodes"].get(node)
    if not target:
        raise HTTPException(404, f"Unknown node {node}")
    return await rc_call(target, "config/listremotes", {})


@app.post("/v1/jobs/{kind}", dependencies=[Depends(verify_api_key)])
async def create_job(
    kind: str,
    body: Dict[str, Any],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Any:
    """Start a new copy, move or sync job.

    The request body must include `node`, `src` and `dst` fields, and may include
    a `flags` dictionary.  If an Idempotency-Key header is provided and a job
    with the same UID exists, the existing job ID is returned.
    """
    if kind not in ("copy", "move", "sync"):
        raise HTTPException(400, "Invalid job kind")
    node = body.get("node")
    src = body.get("src")
    dst = body.get("dst")
    flags = body.get("flags", {})
    if not node or not src or not dst:
        raise HTTPException(400, "Missing required fields: node, src, dst")
    # Idempotency: return existing job if key matches
    if idempotency_key:
        row = DB_CONN.execute("SELECT uid FROM jobs WHERE uid=?", (idempotency_key,)).fetchone()
        if row:
            return {"jobUid": row[0]}
    # start the job
    result = await start_operation(kind, node, src, dst, flags)
    # If idempotency key provided, overwrite job UID
    if idempotency_key:
        DB_CONN.execute("UPDATE jobs SET uid=? WHERE uid=?", (idempotency_key, result["jobUid"]))
        result["jobUid"] = idempotency_key
    return result


@app.get("/v1/jobs/{uid}", dependencies=[Depends(verify_api_key)])
def job_status(uid: str) -> Any:
    """Return status and progress information for a job."""
    row = DB_CONN.execute(
        "SELECT uid,node,kind,src,dst,flags,rc_jobid,status,bytes_done,files_done,created_at,updated_at FROM jobs WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return {
        "uid": row[0],
        "node": row[1],
        "kind": row[2],
        "src": row[3],
        "dst": row[4],
        "flags": json.loads(row[5] or "{}"),
        "rc_jobid": row[6],
        "status": row[7],
        "bytesDone": row[8],
        "filesDone": row[9],
        "createdAt": row[10],
        "updatedAt": row[11],
    }


@app.post("/v1/jobs/{uid}/stop", dependencies=[Depends(verify_api_key)])
async def stop_job(uid: str) -> Any:
    """Stop a running job on its node (not yet implemented)."""
    # Look up the job and node
    row = DB_CONN.execute("SELECT node, rc_jobid, status FROM jobs WHERE uid=?", (uid,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    node_id, rc_jobid, status = row
    if status != "running":
        return {"uid": uid, "stopped": False, "message": f"Job status is {status}, nothing to stop"}
    node = CONFIG["nodes"].get(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")
    # send stop request
    try:
        await rc_call(node, "job/stop", {"jobid": rc_jobid})
    except HTTPException as exc:
        raise exc
    # update status in DB
    DB_CONN.execute("UPDATE jobs SET status=?, updated_at=? WHERE uid=?", ("stopped", int(time.time()), uid))
    return {"uid": uid, "stopped": True}


@app.get("/v1/stream", dependencies=[Depends(verify_api_key)])
async def stream_events() -> StreamingResponse:
    """Stream node stats and job events as newline‑delimited JSON (NDJSON).

    The client should read the response line by line.  Each line is a JSON
    object with at least `t` (timestamp) and `node`.  When stats are
    unavailable the line will contain `error: true`.
    """

    async def event_generator():
        while True:
            for node_id, node in CONFIG["nodes"].items():
                try:
                    stats = await rc_call(node, "core/stats", {})
                    yield json.dumps({"t": int(time.time()), "node": node_id, "stats": stats}) + "\n"
                except Exception:
                    yield json.dumps({"t": int(time.time()), "node": node_id, "error": True}) + "\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/")
def root() -> Dict[str, str]:
    """Provide a simple landing message."""
    return {"message": "Rclone hub is running. See /v1 for API."}
