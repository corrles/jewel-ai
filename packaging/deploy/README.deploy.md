# Deploying Jewel (emeraldlabs.ai) — Ubuntu 22.04+ guide

This guide walks through deploying the Jewel FastAPI app behind nginx with TLS using Let's Encrypt. It targets Ubuntu/Debian-like systems. Adjust paths and usernames to match your environment.

Prereqs (on server):

- You own the domain `emeraldlabs.ai` and can add DNS records.
- A server reachable from the internet (VPS) with a public IP.
- Access to a user with sudo privileges.

1) DNS

- Create an A record for `emeraldlabs.ai` (and optional `www`) pointing to your server IP. Wait for DNS to propagate.

1) Prepare the server

SSH into your server and run:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git ffmpeg
```

1) Create a deploy user & clone repo

```bash
# Optional: create a dedicated user
sudo adduser --disabled-password --gecos "" jewel
sudo usermod -aG sudo jewel

# As the deploy user (or root for testing):
sudo su - jewel
git clone <your-repo-url> ~/Jewel
cd ~/Jewel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1) Configure environment

- Create an `.env` or systemd environment file for secrets (OpenAI API key, sqlite path, etc.). Example minimal env:

```ini
OPENAI_API_KEY=sk-...
JEWEL_DB_PATH=/home/jewel/Jewel/data/jewel.db
VOSK_MODEL_PATH=
AZURE_TTS_VOICE=en-US-EmmaMultilingualNeural
```

1) Create systemd service

- Copy `packaging/deploy/jewel.service` to `/etc/systemd/system/jewel.service` and edit `WorkingDirectory` and `Environment` PATH to match the path where you cloned the repo and your virtualenv.

```bash
sudo cp packaging/deploy/jewel.service /etc/systemd/system/jewel.service
sudo systemctl daemon-reload
sudo systemctl enable --now jewel.service
sudo systemctl status jewel.service
```

1) nginx

- Copy the provided nginx config to `/etc/nginx/sites-available/emeraldlabs.ai` and symlink it:

```bash
sudo cp packaging/deploy/emeraldlabs_nginx.conf /etc/nginx/sites-available/emeraldlabs.ai
sudo ln -s /etc/nginx/sites-available/emeraldlabs.ai /etc/nginx/sites-enabled/emeraldlabs.ai
sudo nginx -t
sudo systemctl reload nginx
```

1) Obtain TLS certificate with certbot

```bash
sudo certbot --nginx -d emeraldlabs.ai -d www.emeraldlabs.ai
```

Certbot will edit the nginx config and reload. Verify HTTPS works at <https://emeraldlabs.ai>

1) Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

1) Health checks & smoke tests

- Ensure `/health` returns `{"ok": true}` and that the UI serves at `/ui/chat_enhanced.html`.
- Run quick smoke tests (see `packaging/deploy/smoke_tests/` for a sample script if included).

1) Notes

- Do not commit secrets (API keys, cert private keys) to source control.
- If you need WebSocket scaling or more concurrency, consider running uvicorn behind gunicorn or using a process manager and increase worker counts accordingly.
- For heavy video processing, move yt-dlp/ffmpeg workload into an async worker or queue (e.g., Celery, RQ) and return immediate responses to users while background jobs run.

Need help applying this to a specific VPS provider or automating this with CI (GitHub Actions)? I can generate a deploy script and a sample GitHub Actions workflow to build, test, and deploy automatically to a given server (using SSH key or provider-specific action).
