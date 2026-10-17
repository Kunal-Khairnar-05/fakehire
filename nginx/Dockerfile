# MULTI-STAGE BUILD
# Stage 1 needs Node.js (hundreds of MB) to turn the React code into plain HTML/CSS/JS.
# Stage 2 starts from a clean, small nginx image and copies ONLY those built files.
# Node, node_modules and the source code never reach the final image.
# Build context is the project root (see docker-compose.yml), so paths start at the root.

# ---- Stage 1: build the frontend ----
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci                      # exact versions from package-lock.json
COPY frontend/ ./
RUN npm run build               # type-check + bundle into /app/dist

# ---- Stage 2: serve it ----
FROM nginx:1.27-alpine
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/api_proxy.conf /etc/nginx/api_proxy.conf
COPY --from=build /app/dist /usr/share/nginx/html
