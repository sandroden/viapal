#!/usr/bin/env bash
# Genera tutte le icone PWA da images/viapal2.svg
# Sostituisce i PNG default Quasar in frontend/public/icons/
set -euo pipefail

usage() {
    cat <<H
gen_icons.sh - Genera icone PWA da SVG sorgente
  -h    Help
  -s    SVG sorgente (default: images/viapal2.svg)
  -o    Output dir (default: frontend/public/icons)
H
}

SRC="images/viapal2.svg"
OUT="frontend/public/icons"

while getopts "hs:o:" opt; do
    case $opt in
        h) usage; exit 0 ;;
        s) SRC="$OPTARG" ;;
        o) OUT="$OPTARG" ;;
    esac
done

cd /home/sandro/src/siti/sandro/viapal

render() {
    local size="$1" name="$2"
    inkscape "$SRC" --export-type=png --export-filename="$OUT/$name" -w "$size" -h "$size" 2>/dev/null
    echo "  $name ($size px)"
}

render_padded() {
    # Per icona maskable: 10% padding per safe-zone
    local size="$1" name="$2"
    local inner=$((size * 80 / 100))
    local pad=$(((size - inner) / 2))
    convert -background "#f7eed8" -size "${size}x${size}" canvas: \
            \( "$SRC" -background none -resize "${inner}x${inner}" \) \
            -gravity center -composite \
            "$OUT/$name"
    echo "  $name (maskable ${size}px)"
}

main() {
    echo "Generazione icone PWA in $OUT/"
    mkdir -p "$OUT"

    render 128 icon-128x128.png
    render 192 icon-192x192.png
    render 256 icon-256x256.png
    render 384 icon-384x384.png
    render 512 icon-512x512.png

    render 16  favicon-16x16.png
    render 32  favicon-32x32.png
    render 96  favicon-96x96.png
    render 128 favicon-128x128.png

    render 120 apple-icon-120x120.png
    render 152 apple-icon-152x152.png
    render 167 apple-icon-167x167.png
    render 180 apple-icon-180x180.png

    render 144 ms-icon-144x144.png

    # Maskable per home-screen (Android adaptive icon)
    render_padded 192 icon-maskable-192.png
    render_padded 512 icon-maskable-512.png

    cp "$SRC" "$OUT/safari-pinned-tab.svg"

    # favicon.ico nel root public
    convert "$OUT/favicon-32x32.png" "$OUT/favicon-16x16.png" frontend/public/favicon.ico
    echo "  favicon.ico (multi-size)"
}

main "$@"
