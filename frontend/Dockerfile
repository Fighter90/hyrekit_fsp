# ============================================
# HyreKit Frontend — Multi-stage Dockerfile
# ============================================

# Build stage
FROM mirror.gcr.io/library/node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Коммит для подписи версии в углу интерфейса (в образе нет .git)
ARG APP_COMMIT=dev
ENV APP_COMMIT=$APP_COMMIT
RUN npm run build

# Production stage — nginx (mirror.gcr.io for Russia)
FROM mirror.gcr.io/library/nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
