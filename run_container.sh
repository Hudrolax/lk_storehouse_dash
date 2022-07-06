#!/bin/bash

docker run \
-d \
--name lk_storehouse_dash \
--net container:www_nginx \
--restart unless-stopped \
-v /app:/home/www/lk_storehouse_dash \
lk_storehouse_dash