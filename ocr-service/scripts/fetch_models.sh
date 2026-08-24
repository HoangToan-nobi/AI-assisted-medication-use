#!/usr/bin/env sh
# Download the pretrained VietOCR checkpoint into models/.
#
# This fetches a published checkpoint; it does not train or fine-tune anything.
# Run it once after cloning, and at Docker build time, so the service never
# reaches the network at runtime -- vietocr's own downloader caches into /tmp,
# which a container loses on every restart.
set -eu

DEST="${1:-models}"
MODEL="${OCR_VIETOCR_MODEL:-vgg_transformer}"
URL="https://vocr.vn/data/vietocr/${MODEL}.pth"

mkdir -p "$DEST"
if [ -s "$DEST/${MODEL}.pth" ]; then
    echo "$DEST/${MODEL}.pth already present; skipping."
    exit 0
fi

echo "Fetching $URL ..."
# Download to a partial file so an interrupted run cannot leave a truncated
# checkpoint that torch.load would then fail on.
curl -sSL --fail -o "$DEST/${MODEL}.pth.part" "$URL"
mv "$DEST/${MODEL}.pth.part" "$DEST/${MODEL}.pth"
echo "Saved $DEST/${MODEL}.pth"
