# Stage 1: Build Svelte UI
FROM node:22-slim AS ui-build
WORKDIR /build
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install deps first (cached unless pyproject.toml changes)
COPY pyproject.toml .
COPY homeclaw/__init__.py homeclaw/__init__.py
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir ".[semantic,whatsapp]"

# Copy application code (changes often, but deps already cached)
COPY homeclaw/ homeclaw/

COPY --from=ui-build /build/dist/ ui/dist/
ENV HOMECLAW_UI_DIST=/app/ui/dist

VOLUME /data/workspaces
EXPOSE 8080

ENTRYPOINT ["homeclaw", "serve", "--workspaces", "/data/workspaces", "--port", "8080"]
