# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies first (layer-cached unless package files change)
COPY package.json package-lock.json* ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY . .

# VITE_API_BASE_URL can be overridden at build time via:
#   docker build --build-arg VITE_API_BASE_URL=https://api.atomquest.io/api/v1 .
ARG VITE_APP_TITLE=AtomQuest
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ── Stage 2: Serve with Nginx ─────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove default Nginx HTML
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing: all unknown paths serve index.html so React Router handles them
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
