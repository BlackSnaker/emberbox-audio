import test from "node:test";
import assert from "node:assert/strict";
import { volumeFromDrag, pageStart, fitLines } from "../src/interaction.js";
test("captured drag retains zero volume and clamps travel", () => {
  assert.equal(volumeFromDrag(0, 0), 0);
  assert.equal(volumeFromDrag(0.5, -2), 0);
  assert.equal(volumeFromDrag(0.5, 2), 1);
  assert.ok(volumeFromDrag(0.5, 0.1) > 0.5);
});
test("pagination clamps after a changing queue, without mutating tracks", () => {
  assert.equal(pageStart(3, 3), 0);
  assert.equal(pageStart(1, 9), 4);
  assert.equal(pageStart(0, 0), 0);
  assert.equal(pageStart(-1, 10), 0);
});
test("two-line metadata respects reserved space and signals truncation", () => {
  const context = { measureText: (s) => ({ width: s.length * 10 }) };
  assert.deepEqual(fitLines(context, "A short title", 200), ["A short title"]);
  const lines = fitLines(
    context,
    "One two three four five six seven eight nine",
    90,
  );
  assert.equal(lines.length, 2);
  assert.ok(lines[1].endsWith("…"));
  assert.ok(lines.every((v) => v.length * 10 <= 90));
});
