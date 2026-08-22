FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Create .next directory with proper permissions and change ownership of entire /app
RUN mkdir -p .next/cache && chown -R node:node /app

# Switch to non-root user
USER node

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "run", "dev"]