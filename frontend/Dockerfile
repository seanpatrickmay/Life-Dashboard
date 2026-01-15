FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./ 
RUN npm install
COPY frontend/ /app
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
COPY docker/Caddyfile /etc/caddy/Caddyfile
