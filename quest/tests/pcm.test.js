import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
function processor(rate = 48000) {
  let Processor;
  const context = {
    Float32Array,
    Number,
    Math,
    sampleRate: rate,
    AudioWorkletProcessor: class {
      constructor() {
        this.port = {};
      }
    },
    registerProcessor: (_name, type) => (Processor = type),
  };
  vm.runInNewContext(
    fs.readFileSync(new URL("../src/pcm-worklet.js", import.meta.url), "utf8"),
    context,
  );
  return new Processor({ processorOptions: { inputRate: 48000 } });
}
function signal(frames) {
  const data = new Float32Array(frames * 2);
  for (let i = 0; i < frames; i++) {
    data[i * 2] = 0.2 * Math.sin((i * Math.PI * 2 * 440) / 48000);
    data[i * 2 + 1] = 0.12 * Math.sin((i * Math.PI * 2 * 660) / 48000);
  }
  return data;
}
test("stereo PCM stays separate, finite and bounded through playback", () => {
  const p = processor();
  p.port.onmessage({ data: signal(12000).buffer });
  let left = 0,
    right = 0;
  for (let n = 0; n < 60; n++) {
    const out = [new Float32Array(128), new Float32Array(128)];
    p.process([], [out]);
    for (let i = 0; i < 128; i++) {
      assert.ok(Number.isFinite(out[0][i]) && Number.isFinite(out[1][i]));
      assert.ok(Math.abs(out[0][i]) <= 0.201);
      left += out[0][i] ** 2;
      right += out[1][i] ** 2;
    }
  }
  assert.ok(left > 50);
  assert.ok(right > 15 && right < left * 0.6);
});
test("network overflow drops stale latency and underflow recovers without NaN", () => {
  const p = processor(44100);
  p.port.onmessage({ data: signal(100000).buffer });
  assert.ok(p.count <= 16000);
  for (let n = 0; n < 200; n++)
    p.process([], [[new Float32Array(128), new Float32Array(128)]]);
  assert.ok(p.count >= 0);
  p.port.onmessage({ data: signal(9000).buffer });
  const out = [new Float32Array(128), new Float32Array(128)];
  p.process([], [out]);
  assert.ok(out[0].every(Number.isFinite));
  assert.ok(out[0].some((v) => v !== 0));
});
