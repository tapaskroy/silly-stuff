#!/bin/sh
# Publish the pages (four sheets, plus the scorecard once built) to tapaskroy.me/elections/midterms2026/ (unlisted: nothing on the site links here).
# Pages are copied into the site repo so the blog skill's full `aws s3 sync --delete` keeps them,
# then only this folder is synced and invalidated. Config (bucket, distribution) is the blog skill's publish.json.
set -e
cd "$(dirname "$0")"
CFG=~/.claude/skills/blog-tapaskroy/publish.json
REPO=$(python3 -c "import json,os;print(os.path.expanduser(json.load(open('$CFG'))['repoDir']))")
BUCKET=$(python3 -c "import json;print(json.load(open('$CFG'))['s3']['bucket'])")
DIST=$(python3 -c "import json;print(json.load(open('$CFG'))['cloudfront']['distributionId'])")
DEST="$REPO/elections/midterms2026"
mkdir -p "$DEST"
cp index.html senate.html house.html governors.html "$DEST/"
[ -f scorecard.html ] && cp scorecard.html "$DEST/"
[ -f wings.html ] && cp wings.html "$DEST/"  # not in the sheets' nav: reachable only by its URL
[ -f review.html ] && cp review.html "$DEST/"  # likewise unlinked until reviewed
aws s3 sync "$DEST/" "s3://$BUCKET/elections/midterms2026/" --delete --cache-control "max-age=300"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/elections/midterms2026/*" --query Invalidation.Id --output text
echo "https://tapaskroy.me/elections/midterms2026/"
