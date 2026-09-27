# Sito di vendita IUSENTRA: file statici serviti da Caddy sulla porta assegnata da Railway.
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY index.html favicon.svg /srv/
COPY assets /srv/assets
ENV PORT=8080
EXPOSE 8080
