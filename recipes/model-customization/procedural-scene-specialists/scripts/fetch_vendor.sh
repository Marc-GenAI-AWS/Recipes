#!/bin/bash
# The harness renders offline, so three.js is vendored locally rather than pulled from a CDN at render time.
# Not committed (15 MB); fetch it once.
set -e
V=${THREE_VERSION:-0.169.0}
D="$(dirname "$0")/../vendor"
mkdir -p "$D/three-addons"
echo "fetching three.js $V -> $D"
curl -sfL "https://unpkg.com/three@$V/build/three.module.min.js" -o "$D/three.module.min.js"
for a in capabilities/WebGL.js objects/Sky.js; do
  mkdir -p "$D/three-addons/$(dirname $a)"
  curl -sfL "https://unpkg.com/three@$V/examples/jsm/$a" -o "$D/three-addons/$a" || true
done
echo "done. export HARNESS_THREE_LOCAL=$D/three.module.min.js"
