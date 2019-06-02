#!/bin/sh

docker run -it --rm --name certbot \
   -v /var/log/letsencrypt:/var/log/letsencrypt \
   -v /etc/letsencrypt:/etc/letsencrypt \
   -v /etc/nginx/pages/certbot:/data/letsencrypt \
   certbot/certbot certonly  \
   --force-renewal \
   --agree-tos \
   --webroot \
   --expand \
   --webroot-path=/data/letsencrypt \
   #--email <example@google.com> \
   -d zstoreit.info

docker exec nginx nginx -s reload
