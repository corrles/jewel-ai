Local development domain and TLS setup for Jewel

This document covers a safe, repeatable way to map a local DNS name (e.g. `jewel.local`) to your machine, create a trusted local TLS certificate (recommended), and start the Jewel FastAPI server bound to that host.

1) Choose a domain name

Pick something short and unambiguous for local dev, e.g. `jewel.local` or `dev-jewel.local`.

2) Edit hosts file (Windows)

Open PowerShell as Administrator and run:

```powershell
# Backup hosts file
copy $env:windir\System32\drivers\etc\hosts $env:windir\System32\drivers\etc\hosts.bak

# Add mapping
Add-Content -Path $env:windir\System32\drivers\etc\hosts -Value "127.0.0.1`tjewel.local"
# Optional IPv6
Add-Content -Path $env:windir\System32\drivers\etc\hosts -Value "::1`tjewel.local"
```

Alternatively, open `%windir%\System32\drivers\etc\hosts` in Notepad (Run as Admin) and append the same lines.

3) Install mkcert and generate a locally-trusted certificate (recommended)

mkcert creates a local CA and installs it into your OS/browser trust stores. On Windows you can install mkcert via Chocolatey:

```powershell
choco install mkcert -y
mkcert -install
mkcert jewel.local 127.0.0.1 ::1
```

This creates files like `jewel.local+2.pem` and `jewel.local+2-key.pem` in the current folder.

4) Start the server with TLS (example)

From the project root run (PowerShell):

```powershell
# Without TLS (default)
.\start.ps1

# With TLS using mkcert outputs
.\start.ps1 -Domain "jewel.local" -Https -CertFile ".\jewel.local+2.pem" -KeyFile ".\jewel.local+2-key.pem"

# Optionally attempt to add hosts entry (best-effort; requires elevation)
.\start.ps1 -Domain "jewel.local" -AddHosts
```

5) Open the app in your browser

- HTTP: <http://jewel.local:8000/ui/chat_enhanced.html>
- HTTPS (preferred): <https://jewel.local:8000/ui/chat_enhanced.html>

6) Notes & troubleshooting

- If browsers still warn about the certificate, ensure mkcert's CA is installed in Windows Trusted Root Certification Authorities and that you used the exact hostnames when generating the cert (include 127.0.0.1 and ::1 if you want IP access).
- If the `start.ps1 -AddHosts` step fails due to permissions, open PowerShell as Administrator and add the hosts entry manually.
- Service workers and some browser features require HTTPS. Use mkcert to avoid warnings.

7) Security

- Do NOT commit generated cert/key files to source control. Add them to `.gitignore` if you create them in the repo. The `start.ps1` script will accept paths anywhere on your filesystem.

8) Want me to do this for you?

I can attempt the `-AddHosts` operation and/or generate mkcert certs locally, but those steps require elevated privileges on your machine. If you want me to proceed, confirm and I will try to add the hosts entry (best-effort) and, if mkcert is installed, generate certs and update `start.ps1` usage notes.
