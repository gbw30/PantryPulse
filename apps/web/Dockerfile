# Built from the repository root (compose.yaml: context ".") because the root lockfile owns
# the npm workspace and the app imports packages/contracts.
FROM node:24.16.0-slim AS build
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
RUN npm ci --no-audit --no-fund
COPY packages/contracts packages/contracts
COPY apps/web apps/web
RUN NEXT_OUTPUT=standalone npm run build --workspace @pantrypulse/web

FROM node:24.16.0-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
