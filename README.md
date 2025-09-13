# Rclone GUI – Personal Cloud Dashboard

## Overview

This project provides a **self‑hosted dashboard** for managing multiple [rclone](https://rclone.org) instances over a private **Tailscale** network.  The design centralizes control in a backend “hub” and exposes a modern single‑page application (SPA) for daily use.  All communication stays inside your tailnet, so there is **no public ingress** and no need to expose rclone on the Internet.  The architecture merges the ideas from the original plan and the more detailed job‑queue design into a cohesive system.

### Core components

1. **Rclone agents** – Each server you want to manage runs the rclone remote‑control daemon.  Rclone’s `--rc` flag starts an HTTP server that exposes a JSON‑RPC API; you can also use the convenient `rclone rcd` wrapper.  To listen on a non‑local interface, specify `--rc‑addr` and optionally set credentials with `--rc‑user` and `--rc‑pass`【691721010393831†L61-L79】【691721010393831†L104-L111】.  To serve file listings over HTTP, add `--rc‑serve`【691721010393831†L124-L131】.  If you trust your tailnet ACLs you can disable authentication with `--rc‑no‑auth`【691721010393831†L210-L217】.
2. **Backend hub** – A stateful service, written in Python with [FastAPI](https://fastapi.tiangolo.com/), proxies “friendly” REST endpoints to the low‑level rclone API.  The hub maintains a per‑node job queue to avoid harmful concurrency, persists checkpoints in SQLite so that jobs can resume after restarts, and normalizes events from all nodes.  It exposes endpoints to browse remotes, start copy/sync/move jobs, stream progress via WebSockets and retrieve job status.  Use the provided Docker configuration to run the hub in a container on your tailnet.
3. **Frontend (SPA)** – A web UI served by any modern static hosting (for example, the hub or a lightweight Nginx).  It talks exclusively to the hub API.  The frontend can be built with [SvelteKit](https://svelte.dev) or any framework supported by [Vite](https://vite.dev).  SvelteKit projects are scaffolded with `npx sv create myapp && cd myapp && npm install && npm run dev`【884361458094095†L124-L131】.  Alternatively, you can create a Vite‑based app with `npm create vite@latest` and choose the `svelte` or `react` template【986861734222727†L238-L297】.

### Why use this architecture?

* **Tailnet only** – By binding each rclone daemon to its Tailscale IP and high random port you avoid exposing storage operations on the Internet.  Access control is enforced by your Tailscale ACLs, and an optional API key for the hub can further restrict access.
* **Unified API** – Rclone’s remote‑control API is powerful but low‑level.  The hub normalizes commands and abstracts details like asynchronous job IDs, simplifying frontend development.
* **Stateful job queue** – Long running transfers can take hours or days.  The hub records checkpoints (bytes and files transferred, flags used and rclone job ID) and resumes or re‑attaches after a restart.  To avoid destructive errors, the hub enforces dry‑run previews and path allow‑lists, and requires idempotency keys on write operations.

### Project structure

This repository is organised as follows:

```
rclone-gui/
├── README.md              # high‑level overview (this file)
├── docker-compose.yml     # compose file for the hub (and optional rcd example)
├── backend/               # FastAPI hub implementation
│   ├── app.py             # hub application code
│   ├── requirements.txt   # Python dependencies
│   └── config.example.json# sample list of nodes (Tailscale IPs & ports)
├── frontend/              # placeholder & documentation for the SPA
│   └── README.md          # how to scaffold a Svelte or React app with Vite
└── docs/                  # detailed design and installation notes
    ├── architecture.md    # architecture and key design decisions
    ├── backend.md         # hub setup and configuration
    ├── rclone-rcd.md      # installing and configuring rclone agents
    └── frontend.md        # SPA development guidance
```

To get started quickly, read `docs/rclone-rcd.md` to set up each target server, then follow `docs/backend.md` to deploy the hub and `docs/frontend.md` to scaffold your web interface.
# Rclone-gui
