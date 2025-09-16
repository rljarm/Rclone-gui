# Architectural design

This document provides a deeper look at the merged architecture described in the project overview.  It explains how the various components fit together and highlights the design decisions that make the system robust, secure and maintainable.

## High‑level topology

```
User browser (SPA) ──► Hub (API router, FastAPI) ──► rclone rcd on node A
                                         └──► rclone rcd on node B
                                         └──► …

                  ▲                         
                  │                           
                  └─────── Tailscale tailnet ────────┘
```

1. **User Browser / SPA** – The frontend runs in your browser and communicates exclusively with the hub via REST and WebSocket endpoints.  It never talks directly to the rclone daemons, simplifying network rules and enabling the hub to enforce safety policies.
2. **Hub** – The hub is a stateful API router implemented with Python and FastAPI.  It exposes friendly endpoints for listing remotes, browsing files, starting copy/move/sync operations, streaming progress and stopping jobs.  Behind the scenes it translates these requests into JSON‑RPC calls to the appropriate rclone `rcd` daemon and manages job state and concurrency.
3. **Rclone agents** – Each target server runs `rclone rcd` bound to its Tailscale IP and a dedicated port.  Only a safe subset of rclone’s remote‑control namespace is exposed (jobs, core/stats, operations/*, sync/*, bisync/*, config/listremotes).  Agents should be configured with `--rc‑addr` to listen on the tailnet interface and may be run with `--rc‑serve` to allow browsing of files【691721010393831†L75-L131】.  Authentication can be disabled with `--rc‑no‑auth` if ACLs restrict access【691721010393831†L210-L217】.

## Security and networking

* **Tailscale‑only network** – All rclone agents listen on `tailscale0` and are not exposed publicly.  This eliminates the need for complex reverse proxies or firewall rules.  Use Tailscale ACL tags to restrict which users and services can access the hub and agents.
* **Hub API key** – Optionally configure an API key on the hub to add another layer of authentication.  Keys can have scoped permissions (e.g., read‑only or read/write) and should be passed via an HTTP header.
* **Path allow‑lists and dry‑run confirmation** – To prevent accidental deletion or overwriting, the hub enforces per‑node path allow‑lists and requires a dry‑run to be executed before a destructive operation proceeds.  This is a critical safety rail that stops `sync` or `move` commands from removing unexpected files.
* **No direct public exposure** – Since the frontend is static, it can be served anywhere (even from the hub), but it communicates over your tailnet.  There is no requirement to expose ports on the public internet.

## Job management model

Rclone operations like `copy`, `move` and `sync` are asynchronous when invoked via the remote‑control API.  The hub assigns each request a **job UID** and maintains a **per‑node queue** to avoid overloading individual agents.  Key aspects of the design include:

* **Per‑node queues** – Each rclone agent can be limited to a configurable number of concurrent jobs (default 1).  The queue is FIFO but head‑of‑line awareness prevents small jobs from being starved by a long transfer.
* **Idempotency keys** – For write operations the client must supply an `Idempotency‑Key` header.  The hub stores the mapping between this key and the rclone job ID.  If the client retries the same request with the same key, the hub returns the existing job UID instead of starting a new transfer.
* **Checkpointing and resumption** – After starting an rclone job the hub periodically calls `core/transferred` and stores bytes transferred, file counts and flags in SQLite.  On restart the hub queries each agent with `job/list`, re‑attaches to running jobs and re‑queues any partially completed tasks using flags like `--ignore‑existing` or `--size‑only`.  This ensures that long copy/sync operations resume rather than restart from scratch.
* **Dry‑run preview** – The hub implements a “plan” endpoint which runs rclone in dry‑run mode and caches the planned operations.  A real transfer can only proceed if the client references a valid dry‑run token.  This ensures you always see what will happen before data is altered.
* **Event streaming** – A `/v1/stream` WebSocket endpoint pushes node stats and job progress to the frontend, enabling a responsive dashboard without constant polling.

## Data persistence

The hub uses a simple **SQLite** database to persist node metadata and job state.  Jobs are stored with fields such as UID, node name, source/destination, flags (JSON), rclone job ID, status, bytes/files processed and timestamps.  Checkpoints can be stored in a separate table for more granular state.  Storing data on disk means that restarts, crashes or upgrades do not lose job information.

## Extensibility and future work

* **Scheduler** – A scheduler could allow cron‑like templates to be stored in the hub and executed at specified times.  Missed runs should trigger an immediate execution when the hub comes back online.
* **Web authentication** – You could integrate OAuth or OIDC at the frontend and hub for multi‑user environments.  For personal use Tailscale ACLs are generally sufficient.
* **TLS** – For an extra layer of security inside the tailnet you can enable TLS on each rclone daemon using the `--rc‑cert` and `--rc‑key` flags【691721010393831†L75-L110】.
* **tsnet** – The hub could embed Tailscale’s `tsnet` library to eliminate manual IP/port management by dialing nodes via tailnet DNS names.
