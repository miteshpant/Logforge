# Logforge Admin UI

Administrative interface for Logforge platform management.

## Development

```bash
cd apps/admin-ui
npm install
npm run dev
```

Access at: http://localhost:3002

## Docker Development

```bash
# Build development image
docker build --target development -t logforge-admin-ui:dev .

# Run with volume mount for live reload
docker run -p 3002:3002 -v $(pwd):/app logforge-admin-ui:dev
```

## Production

```bash
# Build production image
docker build --target production -t logforge-admin-ui:prod .

# Run production
docker run -p 3002:3002 logforge-admin-ui:prod
```

## Testing

```bash
npm run test        # Run Playwright tests
npm run test:ui     # Run tests with UI
```

## Environment Variables

- `NEXT_PUBLIC_API_URL`: Backend API URL (default: http://localhost:7080)
- `NEXT_PUBLIC_ADMIN_MODE`: Admin mode flag (default: true)