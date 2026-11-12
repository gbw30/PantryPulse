# PantryPulse

PantryPulse shows which locations in a food-pantry network or a store chain are about to run short, or to throw away stock that expires, and compares plans for moving stock between your own locations before anything happens. It runs on your computer with your own data. It suggests transfers; it never changes your stock.

Version pin: `0.1.0` (`ghcr.io/gbw30/pantrypulse-api:0.1.0`, `ghcr.io/gbw30/pantrypulse-web:0.1.0`)

## Quickstart

### 1. Prerequisites

- **Windows 11:** [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with the WSL 2 backend, and [git](https://git-scm.com/install/windows).
- **Linux** (tested on Ubuntu 24.04): [Docker Engine](https://docs.docker.com/engine/install/ubuntu/) with the Compose plugin, and git.
- macOS is untested and not supported in this version.
- Hardware: 4 CPU cores and 8 GiB of memory available to Docker, and about 15 GB of free disk. See [docs/pantrypulse/HARDWARE.md](docs/pantrypulse/HARDWARE.md) for the measurements.

You don't need Node, Python or a database: Docker runs everything.

### 2. Download and start

```bash
git clone https://github.com/gbw30/PantryPulse.git
cd PantryPulse
docker compose up --build
```

No images are published yet, so `--build` builds them on your computer. After the first published release, `docker compose up` without `--build` will download them instead.

The first run took 2 min 07 s to build and 27 s to start on the reference laptop ([measurements](docs/pantrypulse/HARDWARE.md)), plus the time to download Docker's base images (PostgreSQL, Python, Node and uv) on a machine that doesn't have them yet.

### 3. Sign in

During start-up, the output prints:

```text
Open http://127.0.0.1:3000 — username: local — password: see .pantrypulse/local-login.txt
```

Open that address once the `web` service has started (the output stops scrolling). Sign in as `local`, with the password from the file `.pantrypulse/local-login.txt` in the folder you cloned. The password is generated on the first start and never leaves your computer.

### 4. Try the sample

The first start loads two fictional networks, labeled "Sample data — fictional": a Pantry network (1 hub, 8 pantries) and a Retail network (1 distribution centre, 20 stores).

1. Choose a network in the sidebar.
2. On the Overview, run the forecast. The ranking lists the locations most at risk of running short or of stock expiring unsold.
3. In the Scenario Lab, compare the transfer methods on one frozen scenario.
4. In Decisions, review each suggested action and export the plan as CSV or print it. The plan is a simulation: no stock is reserved or moved.

### 5. Import your own data

Open **Import** (http://127.0.0.1:3000/import). Download the blank templates or the filled-in examples; the in-app guide explains every column.

- Required files: `locations.csv`, `products.csv`, `inventory.csv`, `demand_history.csv`.
- Optional files: `routes.csv`, `inbound.csv`, `donation_history.csv`.
- Limits: up to 100 locations, 500 products, 90 days of daily history (14 days to forecast, 35 to measure accuracy) and 200,000 inventory batches. A file over a limit is rejected with the limit named, never cut short.

A maximum-size import (100 locations × 500 products × 90 days) took 1 min 22 s of processing on the reference laptop. Locations that have an address but no coordinates are geocoded by the US Census Bureau. That lookup is the app's only outbound call, unless you save your own Google key for road distances in Settings.

### 6. Stop or start over

- `docker compose down` stops the app. Your data stays for the next `docker compose up`.
- `docker compose down -v` **deletes all local data**: imported networks, forecasts, comparisons and the login. There is no undo. The next start loads the samples again and generates a new password.

### Troubleshooting

- **Port 3000 is in use:** copy `.env.example` to `.env`, set `PP_WEB_PORT=3001` (or any free port), run `docker compose up --build` again and open that port.
- **Docker memory:** the forecast and planning worker is allowed up to 6 CPUs and 8 GiB. On Windows, Docker Desktop with WSL 2 takes its CPU and memory limits from WSL (`%UserProfile%\.wslconfig`, section `[wsl2]`, `memory=` and `processors=`); allow at least what [HARDWARE.md](docs/pantrypulse/HARDWARE.md) lists, then restart Docker Desktop.
- **WSL 2 backend:** in Docker Desktop, open Settings → General and turn on "Use the WSL 2 based engine". If Docker asks for a WSL update, run `wsl --update` in PowerShell.
- **Login fails after `down -v`:** the password changed; read `.pantrypulse/local-login.txt` again.

## Known limits

- Batch IDs over 64 characters, or containing `/`, are shown as hashed batch IDs.
- There is no way to abort an import, and nothing cleans up abandoned imports or their files.
- The stack runs one worker; the cleanup of staged import tables assumes that.
- Import progress shows its phase but no live row count.
- There is no publish retry backoff.
- Forecasts are projections: seasonal-naive, with a labeled moving-average fallback. Their quantile ranges are not calibrated intervals or stockout probabilities.
- macOS is untested. Chronos-2 forecasting is an opt-in profile for contributors and is off by default.

## Methods and research basis

Pantry networks compare five methods on the same frozen scenario: no transfers, equal share, most-urgent-first, classical goal programming and **EGP-PI-inspired** allocation. Retail networks compare no transfers, soonest-expiry-first, and an optimized plan that minimizes expired stock plus lost sales. Every published result passes an independent verifier.

EGP-PI-inspired is a bounded, research-inspired adaptation of Rampazo, R. C., Jones, D. F., Godoi, L. F., Iamamoto, M. O., & Cantane, D. R. (2026), *An extended goal programming framework incorporating poverty measures: application to food bank logistics*, International Transactions in Operational Research, first published online 11 September 2026 ([doi:10.1111/itor.70252](https://doi.org/10.1111/itor.70252)).

- **Adapted:** absolute-poverty and relative-poverty goals with thresholds, normalized vulnerability attributes of each location, a weighted plus Chebyshev deviation, and first-expiry-first lot rules.
- **Not reproduced:** the paper's endogenous vulnerability weights, its multi-period model, its full equations and its reported results.
- **Data:** vulnerability values describe locations (census tracts), never individuals. The samples' values are simulated "sample values". For your own network they come from the bundled Census ACS table, or you enter them.

A different recommendation shows different priorities in this simulated scenario. It is not evidence of better real-world outcomes.

## For contributors

- [INSTALLATION.md](INSTALLATION.md): contributor setups, including running the backend tests in Docker with `npm run test:docker`.
- [Testing guide](docs/testing/README.md): every test kit and what it proves.
- [V1-SPEC](docs/pantrypulse/V1-SPEC.md) and the [v1 plan](docs/plans/v1/README.md): scope and decisions. [SPEC-V5](docs/pantrypulse/SPEC-V5.md) governs what V1-SPEC leaves open.

PantryPulse started as a Gator Hack V project. MIT License.
