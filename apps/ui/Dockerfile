# Logforge UI
#
#   production (default): next build, served by the standalone Node server
#   development:          next dev with hot reload (infra/docker/compose.dev.yml)
#
# NEXT_PUBLIC_* values are inlined into the browser bundle at build time, so
# the API URL is a build argument, not a runtime setting.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM deps AS development
COPY . .
# .next and node_modules are container-owned volumes in the dev override.
RUN mkdir -p .next && chown -R node:node /app
USER node
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM deps AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:7080
ARG NEXT_PUBLIC_WS_URL=ws://localhost:7080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# output: 'standalone' (next.config.js) emits a minimal server plus only the
# node_modules it needs; static assets are copied alongside it.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
# The standalone server only needs node. npm, npx, corepack and yarn ship with
# the base image (and npm bundles an old tar, CVE-2026-59873): remove them.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
      /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /opt/yarn-* \
      /usr/local/bin/yarn /usr/local/bin/yarnpkg
USER node
EXPOSE 3000
CMD ["node", "server.js"]
