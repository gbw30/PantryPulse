# w5-screens visual evidence

Connected captures of the lane's own isolated stack (`COMPOSE_PROJECT_NAME=pp-screens`, web on 127.0.0.1:3105, real API, PostgreSQL and worker), on the fictional **Sample Pantry Network (North Central Florida)** that a first start seeds. Taken by `apps/web/tests/e2e/v1-screens-evidence.spec.ts` (`PP_RUN_CONNECTED=1`, reduced motion, light theme) at 1440×900, 1280×720 and 390×844.

- `*-view.png`: the first view, what a reader sees without scrolling.
- `*-full.png`: the full page. Playwright paints the fixed sidebar and the sticky top bar where the capture started, so they appear mid-page; that's an artifact of the capture, not the layout.

| Files | Screen | Built from |
|---|---|---|
| `data-*` | `/data` with the Pantry sample chosen (W5-UI02.1) | `abba32a` |
| `comparison-*` | Scenario Lab comparison, Hub → pantries only, 3 days, rows collapsed (W5-UI02.2) | `abba32a` |

Known, outside this lane (reported to the orchestrator):
- At 390×844 the page is 481 px wide on every screen: the top bar's right cluster (`top-bar.tsx:83`, `ml-auto flex shrink-0`) overflows. w5-polish's file.
- The sidebar network selector covers the page title at 1440 and 1280 (W5-UI05).
- Tables write "boxs" until CR-w5-screens-4 lands in `overview/live-source.ts`.
