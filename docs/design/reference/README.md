# Design reference images

User-supplied layout images that a screen is built against. The lead adds them during `design-intake`; builders and ux-critic only read them. Visual acceptance still comes from the real app (see `.claude/skills/visual-review`).

## Naming

- `<screen>@<width>.png`, where `<width>` is `1440`, `1280` or `390` (the review viewports 1440x900, 1280x720 and 390x844). Use lowercase kebab-case screen names, for example `method-comparison@1440.png`.
- `<screen>.md` beside the images, recording:
  - source (user upload, or a Figma frame link if the user provided one);
  - date added;
  - path to the user's design spec document;
  - widths not supplied;
  - the PP-NN packet that uses it.

## Rules

- An image sets layout, hierarchy and density. SPEC-V5 section 14, ART-DIRECTION.md and `.claude/rules/frontend.md` take precedence over anything it shows.
- Numbers, names and copy in a mockup are illustrative. Never hardcode them in the app.
- Don't use these images as pixel-diff baselines.
