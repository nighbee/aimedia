# Stage 1: Build React Frontend
FROM node:20.18-alpine3.20 AS build

WORKDIR /app

# Cache npm dependencies (no lockfile — let npm resolve platform bindings for Alpine)
COPY package.json ./
RUN npm install && npm cache clean --force

COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:1.26-alpine3.20

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
