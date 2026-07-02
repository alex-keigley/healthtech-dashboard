# Healthtech Dashboard — web container (Next.js).
# Build context is the REPO ROOT:
#   docker build -f deploy/web.Dockerfile .

FROM node:22-bookworm-slim AS build
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
# Migrations live at the repo root; the entrypoint applies them on start.
COPY db/ /app/db/
RUN npm run build

FROM node:22-bookworm-slim
ENV NODE_ENV=production
WORKDIR /app/web
COPY --from=build /app/web/package.json ./package.json
COPY --from=build /app/web/node_modules ./node_modules
COPY --from=build /app/web/.next ./.next
COPY --from=build /app/web/scripts ./scripts
COPY --from=build /app/web/next.config.ts ./next.config.ts
COPY --from=build /app/db /app/db
COPY deploy/web-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 3000
ENTRYPOINT ["/entrypoint.sh"]
