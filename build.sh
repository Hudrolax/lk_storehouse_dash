#!/bin/bash

docker stop lk_storehouse_dash
docker rm lk_storehouse_dash
docker rmi lk_storehouse_dash
docker build . -t lk_storehouse_dash