# Setting up rclone agents

Every server you want to manage must run rclone in **remote‑control mode**.  Rclone’s API is powerful but low‑level; the hub abstracts most details, but you still need to install rclone and start the daemon correctly.

## Installing rclone

Rclone is distributed as a single static binary.  The official installation script downloads the latest release and copies it into `/usr/bin`.  On Linux, you can run:

```bash
sudo -v; curl https://rclone.org/install.sh | sudo bash
```

This script checks whether rclone is already installed and will not re‑download unnecessarily【640260517030287†L79-L87】.  Alternatively, download and unpack the binary manually:

```bash
curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip rclone-current-linux-amd64.zip
cd rclone-*-linux-amd64
sudo cp rclone /usr/bin/
sudo chown root:root /usr/bin/rclone
sudo chmod 755 /usr/bin/rclone
```

After installation, run `rclone config` to set up remotes (e.g., Google Drive, S3, local paths)【640260517030287†L57-L67】.  You do *not* need to configure remotes on the hub; each agent maintains its own config file.

## Running the remote‑control daemon

Rclone exposes an HTTP API when started with the `--rc` flag【691721010393831†L61-L67】.  For a dedicated remote‑control process, use the `rclone rcd` command.  Important flags include:

* `--rc-addr` – IP and port to bind the server to.  The default is `localhost:5572`【691721010393831†L71-L78】.  Set this to your Tailscale IP and a high, unique port (e.g., `100.84.76.84:55743`) so the daemon is reachable on the tailnet.
* `--rc-user` / `--rc-pass` – Username and password for basic authentication【691721010393831†L104-L111】.  If omitted, rclone will refuse remote requests that manipulate remotes.  You can instead disable authentication entirely with `--rc-no-auth`【691721010393831†L210-L217】 if your tailnet ACLs already protect the port.
* `--rc-serve` – Enables an HTTP file browser so you can list and download files via `http://<ip>:<port>/`【691721010393831†L124-L131】.  This is optional but helpful for browsing.
* `--rc-server-read-timeout` / `--rc-server-write-timeout` – Tune server timeouts for large transfers.  The defaults are one hour【691721010393831†L116-L122】.
* `--rc-allow-origin` – Set CORS headers if the hub and rclone run on different addresses【691721010393831†L168-L176】.
* `--rc-web-gui` – Launches the official rclone Web GUI on the same port.  This project replaces that GUI with a custom SPA, so leave it off.

### Example service

The following systemd unit runs rclone rcd on a machine with Tailscale IP `100.84.76.84` using port `55743`.  Adjust the `User=`, IP and port, and create remotes with `rclone config` before enabling the service.

```ini
[Unit]
Description=rclone remote control daemon
After=network.target

[Service]
Type=simple
User=myuser
ExecStart=/usr/bin/rclone rcd \
    --rc-addr=100.84.76.84:55743 \
    --rc-no-auth \
    --rc-serve \
    --use-json-log
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start the service with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rclone-rcd.service
```

### Node profile and allow‑list

Each agent should only expose the minimal set of rclone operations that the hub needs.  Configure the hub to use the following namespaces: `job/*`, `core/stats`, `core/transferred`, `operations/*`, `sync/*`, `bisync/*`, `config/listremotes` and `backend/command` (if you need to run backend commands).  Do **not** expose `delete` or other destructive operations directly; the hub will call them on your behalf with safety rails.

### TLS and authentication

If you prefer end‑to‑end encryption inside your tailnet, you can supply PEM files via `--rc-cert` and `--rc-key` to enable HTTPS【691721010393831†L75-L110】.  When using TLS you must also configure the hub to trust the certificate or disable verification in the HTTP client.  For most private deployments, Tailscale encryption is sufficient and you can keep the daemon on HTTP.
