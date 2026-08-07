# ---- Stage 1: Build ----
FROM node:20-slim AS builder
WORKDIR /app

# Baked into the client bundle at build time (Next.js inlines NEXT_PUBLIC_* at build, not runtime)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# ---- Stage 2: Production ----
FROM node:20-slim
WORKDIR /app

RUN useradd -m appuser

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 3000
CMD ["npm", "start"]
