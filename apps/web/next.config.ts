import path from "node:path";
import type { NextConfig } from "next";

// The Docker image (apps/web/Dockerfile) builds a standalone server; dev, e2e and hosted builds keep the default output.
const standalone = process.env.NEXT_OUTPUT === "standalone";
const config: NextConfig = {
  reactStrictMode: true,
  ...(standalone && { output: "standalone" as const, outputFileTracingRoot: path.resolve(process.cwd(), "../..") }),
};
export default config;
