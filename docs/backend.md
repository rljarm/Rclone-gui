# Backend Hub Setup

This document explains how to set up and configure the backend hub.

## Installation

1.  Clone the repository.
2.  Install Python dependencies: `pip install -r backend/requirements.txt`
3.  Copy `backend/config.example.json` to `backend/config.json` and edit it to include your rclone nodes.

## Running the Hub

You can run the hub directly or using Docker Compose.

### Directly

```bash
python backend/app.py
```

### With Docker Compose

```bash
docker-compose up -d backend
```
