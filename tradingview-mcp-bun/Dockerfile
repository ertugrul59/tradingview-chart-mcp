# Start with Playwright (has all browser deps pre-installed)
FROM mcr.microsoft.com/playwright:v1.49.0-jammy

# Install Bun manually
ENV BUN_INSTALL=/usr/local
RUN curl -fsSL https://bun.sh/install | bash

WORKDIR /app

# Copy files
COPY package.json bun.lockb ./
COPY tsconfig.json ./
COPY src ./src

# Install project deps
RUN bun install

# Run it
CMD ["bun", "run", "src/index.ts"]
