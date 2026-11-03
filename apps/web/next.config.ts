import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // Keep browser tests isolated from an already-running developer server/build.
  distDir: process.env.PANTRYPULSE_E2E === "1" ? ".next-e2e" : ".next",
};
export default config;

