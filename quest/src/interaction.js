export function volumeFromDrag(start, delta) {
  return Math.max(0, Math.min(1, start + delta * 1.6));
}

export function pageStart(page, count, size = 4) {
  return Math.max(0, Math.min(page, Math.ceil(count / size) - 1)) * size;
}

export function fitLines(context, value, width, count = 2) {
  const words = String(value || "")
    .trim()
    .split(/\s+/);
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? line + " " + word : word;
    if (context.measureText(candidate).width > width && line) {
      lines.push(line);
      line = word;
    } else line = candidate;
  }
  if (line) lines.push(line);
  if (lines.length <= count) return lines;
  const result = lines.slice(0, count);
  let last = result[count - 1];
  while (last && context.measureText(last + "…").width > width)
    last = last.slice(0, -1);
  result[count - 1] = last + "…";
  return result;
}
