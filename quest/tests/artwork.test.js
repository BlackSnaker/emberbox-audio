import test from "node:test";
import assert from "node:assert/strict";
import { artworkPalette } from "../src/artwork.js";
test("cover colours retain separated red and teal rather than averaging to grey", () => {
  const pixels = [];
  for (let i = 0; i < 30; i++) pixels.push(220, 40, 25, 255);
  for (let i = 0; i < 20; i++) pixels.push(15, 170, 180, 255);
  for (let i = 0; i < 100; i++) pixels.push(0, 0, 0, 255);
  const palette = artworkPalette(pixels);
  assert.ok(palette[0][0] > 0.8 && palette[0][1] < 0.2);
  assert.ok(palette[1][2] > 0.6 && palette[1][0] < 0.1);
});
test("transparent/monochrome covers still give finite bounded room colours", () => {
  for (const pixels of [
    [],
    [255, 0, 0, 0],
    [0, 0, 0, 255],
    [255, 255, 255, 255],
  ]) {
    const palette = artworkPalette(pixels);
    assert.equal(palette.length, 3);
    assert.ok(
      palette.flat().every((v) => Number.isFinite(v) && v >= 0 && v <= 1),
    );
  }
});
