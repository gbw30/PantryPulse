# External service documentation

> **Current authority:** [Project specification V5](../pantrypulse/SPEC-V5.md). Use these guides for scoped procedures. V5 controls product contracts and current branch status. Backend/model hosting remains paused; the user authorized only the frontend-only Vercel prototype preview. The selected future browser integration is a thin same-origin Next.js proxy.

Start with the [Windows installation and remote connection quickstart](WINDOWS-QUICKSTART.md) for dependency installation, hosting the local API and connecting through Cloudflare from another computer.

For a later integrated demo/presentation, follow the [personal-computer demo guide](LOCAL-DEMO.md): the laptop replaces Fly.io. The hosted backend alternative remains **GitHub → Neon → Fly.io → Vercel**, with optional Hugging Face model downloads. These are future procedures, not prerequisites for the [live simulated Vercel preview](VERCEL.md).

Use the separate [external services installation guide](../../EXTERNAL-SERVICES.md) for the complete setup workflow. Local tools and dependencies are covered in [INSTALLATION.md](../../INSTALLATION.md).

Supplementary references:

- [Personal-computer demo](LOCAL-DEMO.md)
- [Cloudflare tunnel installation and operation](CLOUDFLARE.md)
- [Step-by-step local Chronos model guide](../../CHRONOS-LOCAL.md)
- [GitHub](GITHUB.md)
- [Neon](NEON.md)
- [Fly.io guide location](FLY.md)
- [Vercel](VERCEL.md)
- [Internal worker queue foundation](WORKER-QUEUE.md)
- [Optional Hugging Face / Chronos-2](HUGGING-FACE.md)

The laptop demo remains the selected full-product presentation path. The current Vercel preview is a public, synthetic UI prototype and does not establish backend, database or release readiness.
