#!/usr/bin/env sh
set -eu

mkdir -p build/server
javac -d build/server src/server/*.java
exec java -cp build/server server.BulletinServer "$@"
