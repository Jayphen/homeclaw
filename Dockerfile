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

COPY pyproject.toml .
COPY homeclaw/ homeclaw/
RUN pip install --no-cache-dir ".[semantic]"

COPY --from=ui-build /build/dist/ ui/dist/
ENV HOMECLAW_UI_DIST=/app/ui/dist

VOLUME /data/workspaces
EXPOSE 8080

ENTRYPOINT ["homeclaw", "serve", "--workspaces", "/data/workspaces", "--port", "8080"]
