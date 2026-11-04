# 0) check that the build context really contains backend/ and frontend/
#    (a wrong "Root Directory" in Railway makes them vanish and the build fails with "not found";
#     this step turns that into a clear message and prints what the context contains)
FROM busybox AS check
COPY . /ctx
RUN for d in backend frontend; do \
      if [ ! -d "/ctx/$d" ]; then \
        echo ""; \
        echo "ERROR: the folder '$d/' is not in the build context."; \
        echo "In Railway open: Service > Settings > Source > Root Directory. It must be empty (or /)."; \
        echo "The build context contains:"; \
        ls -la /ctx; \
        exit 1; \
      fi; \
    done; \
    echo "build context OK:"; ls /ctx; \
    touch /context-ok

# 1) build the React app
FROM node:22-alpine AS web
COPY --from=check /context-ok /tmp/context-ok
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) FastAPI serves the API and the built frontend
FROM python:3.12-slim
COPY --from=check /context-ok /tmp/context-ok
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /frontend/dist
ENV FRONTEND_DIST=/frontend/dist
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
