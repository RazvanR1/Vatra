#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

bashio::log.info "Vatra porneste..."
cd /opt/home_brain || exit 1
exec python3 -m app.main
