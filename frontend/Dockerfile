FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./ 
RUN npm install
COPY frontend/ /app
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
COPY docker/Caddyfile /etc/caddy/Caddyfile
