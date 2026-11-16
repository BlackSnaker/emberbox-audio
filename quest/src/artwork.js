// ImageBitmap ignores WebGL's UNPACK_FLIP_Y. Use the same decode path for
// bundled and service artwork so orientation can be checked without an account.
export function decodeArtwork(blob) {
  return createImageBitmap(blob, { imageOrientation: "flipY" });
}

export function artworkPalette(rgba) {
  const buckets = new Map();
  let fallback = [0, 0, 0],
    total = 0;
  for (let i = 0; i < rgba.length; i += 4) {
    if (rgba[i + 3] < 128) continue;
    const rgb = [rgba[i] / 255, rgba[i + 1] / 255, rgba[i + 2] / 255];
    rgb.forEach((v, k) => (fallback[k] += v));
    total++;
    const high = Math.max(...rgb),
      low = Math.min(...rgb),
      sat = (high - low) / Math.max(0.001, high);
    if (high < 0.08 || low > 0.86) continue;
    const key = rgb.map((v) => Math.floor(v * 7)).join(",");
    const b = buckets.get(key) || { sum: [0, 0, 0], weight: 0, n: 0 };
    b.n++;
    b.weight += 0.25 + sat;
    rgb.forEach((v, k) => (b.sum[k] += v));
    buckets.set(key, b);
  }
  const selected = [];
  for (const b of [...buckets.values()].sort((a, b) => b.weight - a.weight)) {
    const rgb = b.sum.map((v) => v / b.n);
    if (
      selected.every((v) => Math.hypot(...rgb.map((x, k) => x - v[k])) > 0.22)
    )
      selected.push(rgb);
    if (selected.length === 3) break;
  }
  if (!selected.length)
    selected.push(fallback.map((v) => v / Math.max(1, total)));
  while (selected.length < 3) selected.push([...selected[0]]);
  return selected;
}
