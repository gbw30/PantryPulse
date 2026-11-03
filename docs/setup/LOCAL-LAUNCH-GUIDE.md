# PantryPulse: launch locally and fix common problems

Updated October 25, 2026 for this laptop's prepared baseline demo. All commands are PowerShell. Current main is `647f6a8`: Overview, Data Explorer, Recommendations, Scenario Lab and Methodology are implemented; `/optimization` redirects to `/scenarios`. The app consists of a website, API, background worker and PostgreSQL database. Docker runs the last three; a separate terminal runs the website.

## Choose the right path

- **Use A to reopen the video demo.** It already contains the three labeled video datasets, saved forecasts and verified comparisons. Restarting it preserves them.
- **Use B only to create another independent demo.** This creates a new database with starter data; it does not automatically contain the three video scenes.
- If a port is occupied, read **C**. Do not rerun setup just to resolve a busy port.

Keep Docker open, plug the laptop into power and keep the website terminal open during use. Do not delete Docker volumes or overwrite private settings as routine cleanup.

## Ingredients

| Material | What you need |
| --- | --- |
| Source checkout | `C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse` |
| Existing video demo folder | `C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse\artifacts\presenter_demo_20261025_135726` |
| Docker Desktop | Linux containers; engine running |
| Website tools | Node 24.16+, npm 11.13+, installed locked packages |
| Preparation tools | uv and Python 3.12, already installed on this laptop |
| Two PowerShell windows | One for backend checks; one for the running website |
| Presenter access | Username `presenter`; the password you chose at setup |
| Internet | Needed for uncached packages/images; no cloud account is required for this local database |
| Memory | Leave room for Windows, Docker and the browser; the configured worker ceiling is 8 GiB, not a reservation |

Chronos, Neon, Fly, Vercel and a tunnel are not required for this baseline laptop demo. The website is available only on the local machine.

## A. Reopen the existing video demo

### 1. Start Docker

Open Docker Desktop from the Start menu. Wait until its engine is running. In PowerShell window 1:

```powershell
docker info --format '{{.OSType}}'
```

Expected: `linux`. If Docker returns an error, use D1 before continuing.

### 2. Set your folder paths

Copy this complete block into window 1:

```powershell
$repoRoot = 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse'
$demoFolder = 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse\artifacts\presenter_demo_20261025_135726'
Set-Location -LiteralPath $repoRoot
if (-not (Test-Path -LiteralPath "$demoFolder\compose.yaml")) { throw 'Demo folder is incorrect: compose.yaml was not found.' }
$demoInfo = Get-Content -LiteralPath "$demoFolder\project.json" -Raw | ConvertFrom-Json
$demoInfo | Select-Object project,web_url,api_url
```

The folder path ends in `135726`, **not** in `NEXT-STEPS.md`. PowerShell variables exist only in the terminal where you set them.

Last verified configuration: website `http://127.0.0.1:3020`; API `http://127.0.0.1:8021`. The older demo uses API 8020. **Use project.json as the authority**, especially after port repair.

### 3. Start or resume the backend

```powershell
docker compose -f "$demoFolder\compose.yaml" up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Backend did not start. Read the error before continuing.' }
docker compose -f "$demoFolder\compose.yaml" ps
Invoke-RestMethod "$($demoInfo.api_url)/api/v1/health"
```

Expected: database and API healthy; worker running; health request succeeds. This does not rebuild images, reset data or create another demo. A successful health check alone does not prove compute readiness; run a forecast when testing the complete flow.

### 4. Start the website in window 2

Open another PowerShell window and copy:

```powershell
$demoFolder = 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse\artifacts\presenter_demo_20261025_135726'
& "$demoFolder\start-web.ps1"
```

Wait for Next.js to report ready. Keep this terminal open. If the website is already running from this checkout for this demo, open its URL instead of launching a second server. If it is a different demo or process, use C.

### 5. Open the app

In window 1, display your addresses:

```powershell
"Optimization: $($demoInfo.web_url)/optimization"
"Overview: $($demoInfo.web_url)/overview"
```

Open the optimization address in your browser. Sign in as `presenter` using your chosen password. Use `127.0.0.1` consistently; `localhost` is a different browser origin.

After signing in, open **Scenario Lab** (`/scenarios`) and **Recommendations** to inspect saved scenarios/results. VIDEO 01 Normal Week, VIDEO 02 Demand Surge and VIDEO 03 Vulnerability Trade-off records were imported into this demo on October 25. CSV import is not required to preserve those records.

The older local video shortcut section was added to the retired monolithic workspace. Current main redirects `/optimization` to Scenario Lab and does not automatically consume that workspace's `demo-video.json` manifest. **Do not expect Open scene 01–03 buttons on the current screens.** Saved database records and local presentation labels are different things. Verify how the current catalog renders them before recording.

The earlier copied API image is not automatically upgraded by pulling source. Its existing database/worker can be resumed without adopting every current-main feature. For the tracked newer `pp-local-*` launcher and eight-product/experimental-model source support, see [local demo](LOCAL-DEMO.md). Never switch runtimes or reset the video database merely to make labels appear.

### 6. Stop safely

Wait for calculations to finish. Press Ctrl+C in the website window. In window 1:

```powershell
docker compose -f "$demoFolder\compose.yaml" stop
```

This stops only this demo project and preserves its database. A worker may take time to drain. To return later, repeat A. Do not add `-v`, run a volume prune, or delete the demo folder.

## B. Create a new independent demo

Use this only when you intentionally need fresh starter data or do not have an existing demo. It does not copy the video scenes, saved comparisons, password or database from another demo.

1. Start Docker and verify `linux` as above.
2. Change to the main checkout. Preserve existing changes; the video-label changes in `workspace.tsx` and `public/demo-video.json` were prepared for this demo, so do not discard them.
3. If packages are missing, stop the website server for this checkout and run `npm ci --no-audit --no-fund`. Do not reinstall packages on every launch.
4. Run:

```powershell
Set-Location 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse'
uv run --frozen --directory apps/api python 'C:\Users\gabri\.vscode\projects\Hackathons\GATORHACK26\PantryPulse\artifacts\demo-recipe\setup_demo.py' --repo "$PWD"
```

5. Enter a password of at least 12 characters twice. Typing is invisible; this is normal.
6. Wait for **Backend ready**. The helper creates a separate database, applies migrations, loads fictional history/stock/assumptions, and starts its API/worker. It chooses free ports automatically and rechecks after image building.
7. Copy the printed **folder path** into `$demoFolder`. Do not include a filename:

```powershell
$demoFolder = 'PASTE_THE_PRINTED_FOLDER_PATH_HERE'
if (-not (Test-Path -LiteralPath $demoFolder -PathType Container)) { throw 'Use a folder path, not NEXT-STEPS.md.' }
Get-Content -LiteralPath "$demoFolder\NEXT-STEPS.md"
```

8. Follow that generated file; it contains your actual URLs and launcher. A successful preparation was observed for the existing demo; a fresh run still needs its own readiness check.

The new-demo helper and port-repair helper are prepared local materials under the original checkout's ignored `artifacts/demo-recipe` directory. They are not installed system commands or automatically included when cloning the repository elsewhere.

## C. Resolve occupied ports without deleting data

### C1. Identify the owner

Load your project information in window 1 as in A2, then:

```powershell
$wantedPorts = @(([uri]$demoInfo.web_url).Port, ([uri]$demoInfo.api_url).Port)
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in $wantedPorts } |
  Select-Object LocalAddress,LocalPort,OwningProcess
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

An API port occupied by this demo's own healthy API is expected: open the existing app. A second website launch on its existing port is unnecessary. Windows may list `com.docker.backend.exe` as owner of container ports; identify the container with `docker ps`. Do not kill Docker's backend process.

If it is your own old website server, use Ctrl+C in that server's terminal. If you must stop a known obsolete demo container, first wait for its work to finish and target only that container. Docker's current stop option is `--timeout`; `--time` still worked here but printed a deprecation warning.

```powershell
# Only when pp-local is the old demo you intentionally want to stop:
docker stop --timeout 725 pp-local-worker
docker stop --timeout 30 pp-local-api
```

Those names refer to the older pp-local stack, not the prepared ppdemo video project. Do not stop every container or remove databases to free a port.

### C2. Keep the existing demo and move it to free ports

Use this when another intentional service owns a required port. The repair helper preserves the database, schema, password, tokens and saved data.

1. Wait for all calculations in this demo to finish. Press Ctrl+C in **this checkout's website terminal**. Leave other apps running.
2. In window 1, set `$demoFolder` to your actual existing demo folder as in A2.
3. Preview available ports without changing files:

```powershell
Set-Location 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse'
uv run --frozen --directory apps/api python 'C:\Users\gabri\.vscode\projects\Hackathons\GATORHACK26\PantryPulse\artifacts\demo-recipe\reconfigure_demo_ports.py' --folder "$demoFolder" --check-only
```

4. Prepare matching settings:

```powershell
uv run --frozen --directory apps/api python 'C:\Users\gabri\.vscode\projects\Hackathons\GATORHACK26\PantryPulse\artifacts\demo-recipe\reconfigure_demo_ports.py' --folder "$demoFolder"
```

The helper chooses free ports, backs up local configuration in the same private demo folder, and updates the API mapping, allowed browser origin, website proxy settings, project metadata and generated URLs. It does not operate Docker.

5. Apply only this demo's API configuration after work has finished:

```powershell
docker compose -f "$demoFolder\compose.yaml" up -d --wait --no-deps --force-recreate api
if ($LASTEXITCODE -ne 0) { throw 'API did not start. Inspect the error and preserve the demo folder.' }
$demoInfo = Get-Content -LiteralPath "$demoFolder\project.json" -Raw | ConvertFrom-Json
Invoke-RestMethod "$($demoInfo.api_url)/api/v1/health"
```

6. Start `start-web.ps1` again in window 2. Open the **new** URLs from `project.json`/`NEXT-STEPS.md` and sign in again if needed.

Never change only the Next.js port: the API allowed origin and website proxy must agree. Ports can be taken between any check and later startup; if that happens, preserve the demo and repeat this repair after confirming the new owner.

## D. Problems we encountered and their fixes

### D1. Docker pipe/daemon connection error

Symptoms include `dockerDesktopLinuxEngine`, `cannot connect`, or a missing pipe. Open Docker Desktop, wait for readiness, and rerun `docker info --format '{{.OSType}}'`. If Docker reports WSL/virtualization prerequisites, resolve its specific message before setup. A healthy source checkout cannot substitute for a running Linux engine. Do not kill other workloads, change global WSL settings, or prune databases as routine repair.

If the error is access denied, try Docker from your normal user PowerShell session with Docker Desktop signed in under the same Windows user. Keep the exact error for diagnosis rather than assuming it requires Administrator mode.

### D2. `C:\compose.yaml` cannot be found

`$demoFolder` is empty in this terminal. Copy A2's complete path block, then:

```powershell
Test-Path -LiteralPath "$demoFolder\compose.yaml"
```

Expected: `True`. Variables do not carry between terminal windows. Do not run compose commands with an unset folder variable.

### D3. `NEXT-STEPS.md\NEXT-STEPS.md` cannot be found

The variable contains the file path instead of the folder. Remove the final `\NEXT-STEPS.md` from `$demoFolder`, then use:

```powershell
Get-Content -LiteralPath "$demoFolder\NEXT-STEPS.md"
```

### D4. Port occupied / `EADDRINUSE` / bind failed

New preparation skips busy ports automatically. For an already prepared demo, use C: reopen its existing server, stop only your known old website, or repair all related port settings together. Never kill `com.docker.backend.exe`, stop all containers, or let Next silently select a different origin.

If Next reports that `.next/dev/lock` is held, another Next dev server is using the same checkout. Open its existing URL or stop that exact server with Ctrl+C. A different port alone does not allow two dev servers to share the same build directory. Do not delete the lock while its server is running.

### D5. Next.js hydration warning with `data-gr-*` attributes

The screenshot showed `data-new-gr-c-s-check-loaded` and `data-gr-ext-installed`, strongly indicating Grammarly modified the page before React hydrated it. Disable Grammarly on the demo site, then refresh with Ctrl+Shift+R, or use a private browser window where that extension is disabled. Sign in again in that window. Browser extensions modifying HTML are a [documented hydration-error cause](https://nextjs.org/docs/messages/react-hydration-error). If it persists without extensions, investigate the remaining diff; do not assume all hydration warnings have the same cause.

No database reset or setup rerun is needed for this warning.

### D6. Login fails / origin or CSRF error

Use the exact generated `http://127.0.0.1:PORT` address, not another hostname/port. Start the website through the launcher from the **same demo folder** as the backend. Username is `presenter`; use your chosen password. The two prepared demos can share a recorded website port but have different API URLs/passwords, so don't mix their folders. After switching demos or ports, sign in again. Never publish `.env` or `web-private.json` to debug this.

### D7. API health works, but a new calculation returns 503

The worker can be unavailable even when API health passes. Check:

```powershell
docker compose -f "$demoFolder\compose.yaml" ps
docker compose -f "$demoFolder\compose.yaml" logs --tail 80 worker
docker compose -f "$demoFolder\compose.yaml" logs --tail 80 api
```

Check that API and worker belong to the selected project and schema. If the worker is stopped, start it with `docker compose -f "$demoFolder\compose.yaml" up -d worker`, then retry after it becomes ready. If it is running but reports migration/capability/resource errors, preserve the exact error for diagnosis. Do not clear queue rows or fabricate readiness. Saved reads can still work during compute outage.

### D8. Forecast/scenario is stale or historical

Saved results do not move to today's date automatically. Use fresh forecasts and an explicitly revised scenario for new planning. If the seeded history no longer covers the required date window, intentionally prepare fresh isolated data; do not relabel old results as current. The three prepared video scenes are dated October 25, 2026 and remain viewable as historical saved results later.

### D9. Video scenes missing or overview says Static fixture

First sign in and refresh the optimization workspace. Use the exact demo folder ending `135726`; the other demo does not have the same imported video records. The old local label manifest and untracked `workspace.tsx` are not part of current main's active Scenario Lab route. The dataset/scenario/comparison records remain in the database. Use the current saved catalog and verify labels rather than restoring retired source automatically.

For the overview, make sure a planning-ready forecast exists, use the same signed-in browser session, and confirm the source label says **Live · simulated network**. A static fixture is fallback display, not a live-data success.

### D10. Missing npm package or website won't compile

Stop this checkout's website first, change to the correct main checkout, and run `npm ci --no-audit --no-fund`. Then retry the saved launcher. Do not run `npm audit fix` or upgrade packages during presentation setup. Old `node_modules` initially lacked a dependency required by the updated UI; reinstalling from the committed lockfile resolved that issue.

### D11. PowerShell blocks `start-web.ps1`

Open the launcher in an editor, review its commands and paste them into PowerShell. It loads private proxy settings and starts Next at the selected port. Do not weaken global execution/security policy just to launch the demo.

### D12. Native Windows tests fail on `resource` or containment

The solver qualification and process-control tests need Linux. Use the documented Linux/PostgreSQL CI or isolated container test environment. Native Windows collection failures/skips are not passing full QA. A local contract check also encountered CRLF-versus-LF differences; those were confirmed identical after newline normalization. These are separate from launching the app.

## Final presentation check

- Docker database/API healthy; worker running for the selected project.
- Website open at the generated URL; presenter signed in.
- Prepared video datasets/results available in the selected current catalog; saved results show independent verification. Do not assume retired shortcut controls exist.
- Overview's source is live simulated data, with dated/provider labels.
- No hydration overlay or unfinished computation obscures the recording.
- A saved comparison is ready so the pitch does not wait for a long calculation.
- New comparisons can take several minutes; do not repeatedly submit while waiting.
- Data, vulnerability scores and recommendations are described as simulated; no stock is dispatched.
- Keep the private demo folder and backups off Git and out of screenshots.

## Verification and limits

At the latest inspection, the video project's API/database were healthy and worker running. Its real data preparation produced three forecasts and six independently verified OPTIMAL method results. Frontend types/lint passed for the label update. The repair helper is validated with disposable fixture configuration and temporary socket checks; applying it to the actual demo is an operator step, not an action performed while authoring this guide. No containers, passwords or databases were reset for this documentation task.
