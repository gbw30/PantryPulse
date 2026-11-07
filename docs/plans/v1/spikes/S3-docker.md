# Spike S3: cross-platform clean-clone run (W0-06)

Status: measured on 2026-11-06 at commit `f476520` (branch `w0/foundation`) on one machine, from a Windows 11 PowerShell clone and from a WSL Ubuntu clone. This is pre-evidence for V1-A01 and A24, not a PASS: both runs share one Docker Desktop engine, and base images and package downloads were already cached.

## Machine

- Docker Desktop 4.96.3 (244472), engine 29.9.2, Linux containers on the WSL 2 backend (kernel 6.18.54.1-microsoft-standard-WSL2).
- Docker resources: 16 CPUs, 15.3 GiB memory (`docker info` MemTotal 16,433,180,672 bytes). This is the WSL default; Docker Desktop shows no separate memory setting for the WSL 2 backend.
- Windows Git: `core.autocrlf=true`, set system-wide by the Git for Windows installer (`C:/Program Files/Git/etc/gitconfig`).

## Run 1: Windows 11 PowerShell (Gabriel)

Commands, from a normal PowerShell session (not Administrator; `C:\code\pp-s3` is owned by the user account):

```powershell
git config --global --add safe.directory '//wsl.localhost/Ubuntu/home/gabri/code/PantryPulse/.git'
git clone --branch w0/foundation \\wsl.localhost\Ubuntu\home\gabri\code\PantryPulse C:\code\pp-s3
cd C:\code\pp-s3
docker compose -p pp-s3 build --no-cache
docker compose -p pp-s3 up
```

- **Line endings:** no CRLF problem. `git ls-files --eol` shows `i/lf w/lf attr/text eol=lf` for `compose.yaml` and `apps/api/Dockerfile`, so `.gitattributes` overrides `autocrlf=true` for every file that runs in a container. No `\r`, `bad interpreter` or `exec format` lines appeared in the logs.
- **Build without cache:** api 35.6 s and web 31.0 s (`docker buildx history ls`). Gabriel measured the whole build at under 3 minutes.
- **Start:** about 10 s from `up` (containers created 21:53:44 EST) to the seed's `Open http://127.0.0.1:3000 — username: local — password: see .pantrypulse/local-login.txt` line.
  - migrate and seed exit 0; api and web report healthy.
  - On a new database, Postgres ran its first-time setup (`pp-s3_db` created 21:32:11).
- **Login file:** `Get-Content C:\code\pp-s3\.pantrypulse\local-login.txt` printed the username and password, so Windows can read the file even though WSL shows it as `root` with mode 600.
- **Login:** logging in at http://127.0.0.1:3000 as `local` worked. Screenshot by Gabriel, not committed: the Overview page, with "No planning-ready forecast yet" and no sites. That is expected in W0 (see below).
- **Clean-up:** `docker compose -p pp-s3 down -v` removed all containers and volumes.

## Run 2: WSL Ubuntu (orchestrator)

```bash
git clone --branch w0/foundation /home/gabri/code/PantryPulse ~/tmp-s3-clone
cd ~/tmp-s3-clone
export COMPOSE_PROJECT_NAME=pp-s3wsl PP_WEB_PORT=3999
docker compose build --no-cache        # 37 s
docker compose up -d --wait            # 20 s to all services healthy
```

The project was named `pp-s3wsl` because Run 1 had just used `pp-s3`.

- The seed generated a local login and a proxy token and printed `Open http://127.0.0.1:3999 …`. `.pantrypulse/local-login.txt` is owned by the host user with mode 600.
- Through the web proxy:
  - `GET /` → 307 (redirect to login).
  - `POST /api/v1/presenter/login` with the generated password → 200; with a wrong password → 401.
- `docker compose stop` took 0.9 s. api and web exit 143 (SIGTERM) and worker and postgres exit 0, so a normal stop is clean. The `web` exit 137 in Run 1 came from a second Ctrl+C, which forces a kill.
- `docker compose down -v` removed all containers and volumes. `~/tmp-s3-clone` is left in place; the hook blocked `rm -rf`.

## Findings

1. **A second copy silently joins the first install (packaging note).** `compose.yaml:5` sets `name: pantrypulse`. A plain `docker compose up --build` from a second folder therefore takes over the existing stack: it replaced the api, web and worker containers and reused the existing `pantrypulse_db`.
   - Gabriel's first attempt did exactly this.
   - The seed then found that `local-login.txt` didn't match the stored hash and generated a new password. This made the other folder's login file stale until that copy restarted and generated another one.
   - This is harmless for the one-install stranger case, and it keeps data across reinstalls into a new folder. It needs one line in the install guide: "one install per machine; use `docker compose -p <name>` for a second copy".
   - W5 packaging decides whether to keep the fixed name. Changing it would break the volume name for existing installs.
2. **Cloning from a WSL path needs `safe.directory`.** Windows Git refuses `\\wsl.localhost\…` sources as "dubious ownership". This affects only our test setup. A stranger cloning from GitHub never sees it.
3. **The Windows prompt prints placeholder ellipses literally.** Gabriel ran a command with the literal `…` from an instruction and added a junk `safe.directory '…'` entry. Install-guide commands must be complete and copy-paste ready, with no `…` placeholders.
4. **`samples loaded: 0` is expected.** `apps/api/app/services/samples/__init__.py:16` `ensure_samples` is a stub until the sample networks lane lands. Likewise, the UI is still the pre-v1 presenter shell; v1 navigation is W1-W02.

## Not measured

- A first install with nothing cached: base images (Python, Node, Postgres) and uv/npm download caches were warm, so 31–37 s per image is a lower bound.
- A separate Windows machine, Docker Desktop with Hyper-V instead of WSL 2, and native Linux Docker without Docker Desktop.
- Memory use under an import or solve. W0 has no v1 workload yet.
