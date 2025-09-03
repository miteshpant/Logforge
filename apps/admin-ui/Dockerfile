# Multi-stage Dockerfile for Logforge Admin UI
# Development: docker build --target development
# Production: docker build --target production

FROM node:18-alpine AS base
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Development stage - for testing in Docker with hot reload
FROM node:18-alpine AS development
WORKDIR /app

# Copy package files and install all dependencies (including dev)
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Expose port 3002 for admin UI
EXPOSE 3002

# Start development server
CMD ["npm", "run", "dev"]

# Build stage
FROM base AS builder
WORKDIR /app

# Install all dependencies for build
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine AS production
WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3002

ENV PORT 3002
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]