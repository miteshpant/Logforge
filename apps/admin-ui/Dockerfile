# Logforge Admin UI
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
EXPOSE 3002
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
    PORT=3002 \
    HOSTNAME=0.0.0.0
# output: 'standalone' (next.config.js) emits a minimal server plus only the
# node_modules it needs; static assets are copied alongside it.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3002
CMD ["node", "server.js"]
