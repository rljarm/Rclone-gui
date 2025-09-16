# Backend hub setup

This guide covers installing and running the hub service.  The hub is implemented with [FastAPI](https://fastapi.tiangolo.com/), an asynchronous Python framework, and uses [Uvicorn](https://www.uvicorn.org/) as the ASGI server.  It communicates with rclone agents over HTTP using the `httpx` library.

## Installing dependencies

The hub runs on Python 3.9 or newer.  Use your system package manager to install Python, then create a virtual environment (recommended) and install the required packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi  # minimal dependencies【219828334669581†L300-L305】
pip install 'uvicorn[standard]'  # ASGI server with optional extras【818938954835850†L139-L148】
pip install httpx
```

If you prefer to pin versions, use `requirements.txt` from this repository.  It lists `fastapi`, `uvicorn[standard]` and `httpx`.

## Configuration file

The hub reads a JSON configuration file that lists all rclone agents in your tailnet.  Copy `backend/config.example.json` to `backend/config.json` and edit it to match your environment.  An example configuration looks like this:

```json
{
  "nodes": [
    {
      "id": "home-nas",
      "name": "Home NAS",
      "ip": "100.84.76.84",
      "port": 55743
    },
    {
      "id": "vps-backup",
      "name": "VPS Backup",
      "ip": "100.92.7.29",
      "port": 55744
    }
  ],
  "api_key": ""  
}
```

* `id` – short identifier used in API paths.
* `name` – human readable label displayed in the UI.
* `ip` and `port` – the Tailscale IP and port where the rclone daemon is listening (`--rc‑addr` on the agent【691721010393831†L75-L79】).  Use different ports for each node.
* `api_key` – optional API key that must be provided by clients (e.g., as `X‑API‑Key` header).  Leave empty to disable API key authentication.

## Running the hub

### Development

From the repository root, run the hub directly with Uvicorn:

```bash
cd rclone-gui/backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag automatically reloads the server when code changes.  Use `--host 0.0.0.0` so that the service listens on all network interfaces, including your tailnet.

If you set `HUB_CONFIG` or `HUB_DB_PATH` environment variables they will override the defaults (`config.json` and `./hub.db` respectively).

### Docker deployment

For production you can build and run the hub inside a container.  The provided `docker-compose.yml` defines a service named `hub`.  It mounts the backend code and a data volume for the SQLite database, and runs Uvicorn on port 8000.  Launch it as follows:

```bash
cd rclone-gui
docker compose up -d --build
```

Ensure that Docker has access to your Tailscale interface or that you run the container with `network_mode: host`.  If you prefer not to use host networking, map port 8000 and let the hub dial agents over the tailnet.

### API endpoints

The hub exposes a versioned API under `/v1`.  Important endpoints include:

* `GET /v1/nodes` – returns health and basic stats for each configured node.
* `GET /v1/remotes?node=<id>` – lists rclone remotes on the specified node (calls `config/listremotes` on the agent).
* `GET /v1/jobs/<uid>` – returns status and progress for a job.
* `POST /v1/jobs/{kind}` – starts a new job (`kind` = `copy`, `move` or `sync`).  The request body must include `node`, `src`, `dst` and an optional `flags` object.  If your request modifies data you must first call the plan/dry‑run endpoint (to be implemented) and then set `dryRunConfirmed` in the flags.
* `POST /v1/jobs/<uid>/stop` – stops a running job (todo in the skeleton).
* `GET /v1/stream` – an NDJSON WebSocket endpoint streaming real‑time node stats and job events.  Each line is a JSON object containing a timestamp and either statistics or an error flag.

Future endpoints will support scheduling cron‑like jobs, listing job history, and retrieving logs.

## Database

The hub stores persistent state in a SQLite database.  On startup it creates a `jobs` table if none exists.  WAL mode is enabled for concurrent readers and writers.  If you need to migrate the schema or add new tables (e.g., for checkpoints or events) you can modify `app.py` accordingly.  The default location is `backend/hub.db`, but it is better to store the database on a persistent volume (e.g., `/srv/rclone‑hub`) when running in Docker.

## Extending the hub

* **Additional flags** – The `start_op` helper maps a small set of flags from the frontend to rclone payload fields.  You can extend this mapping to support more rclone options such as `dryRun`, `ignoreExisting`, `fastList`, `bwlimit` etc.
* **Job stopping** – To stop a job you can call `job/stop` on the rclone agent with the corresponding job ID.  Implement a `POST /v1/jobs/<uid>/stop` endpoint in `app.py` to relay this call.
* **Dry‑run plan** – The skeleton includes a placeholder for a preview/plan cache.  Implement an endpoint that calls rclone with `--dry‑run` and stores the planned actions; require a confirmation token before running a destructive operation.
* **Authentication** – Add middleware to FastAPI that checks the `X‑API‑Key` header against the key in your configuration file.  You could also integrate with OAuth or OIDC for multi‑user environments.
