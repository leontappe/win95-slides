#!/bin/sh
# Container entrypoint (nginx:alpine): pull public/ from GitHub, then serve it.
# Restart the container to deploy the latest commit. SITE_REF picks a branch/tag/commit.
set -e
REPO=${SITE_REPO:-leontappe/win95-slides}
REF=${SITE_REF:-main}
H=/usr/share/nginx/html
T=$(mktemp -d)
wget -qO "$T/site.tgz" "https://codeload.github.com/$REPO/tar.gz/$REF"
tar xzf "$T/site.tgz" -C "$T"
SRC=$(find "$T" -mindepth 1 -maxdepth 1 -type d)
rm -rf "$H"/* && cp -r "$SRC/public/." "$H/"
cp "$SRC/deploy/nginx.conf" /etc/nginx/conf.d/default.conf
rm -rf "$T"
echo "win95-slides: serving $REPO@$REF"
exec nginx -g 'daemon off;'
