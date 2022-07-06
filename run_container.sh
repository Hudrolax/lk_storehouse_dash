#!/bin/bash

docker run -d --name lk_storehouse_dash --net container:www_nginx --restart unless-stopped -v /app:. lk_storehouse_dash