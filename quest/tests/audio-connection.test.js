import test from "node:test";
import assert from "node:assert/strict";
import { AudioEngine } from "../src/audio.js";
function fixture() {
  let release;
  const gate = new Promise((r) => (release = r));
  let requests = 0;
  const nodes = [];
  class Node {
    constructor() {
      this.connected = false;
      this.port = { postMessage() {} };
      nodes.push(this);
    }
    connect() {
      this.connected = true;
    }
    disconnect() {
      this.connected = false;
    }
  }
  const engine = new AudioEngine();
  engine.context = {
    currentTime: 0,
    state: "running",
    audioWorklet: { addModule: () => gate },
  };
  engine.gain = { gain: { setTargetAtTime() {} } };
  engine.ready = async () => {};
  const client = {
    request: async (_url, { signal }) => {
      requests++;
      return {
        body: {
          getReader: () => ({
            read: () =>
              new Promise((_resolve, reject) =>
                signal.addEventListener(
                  "abort",
                  () => reject(new DOMException("Aborted", "AbortError")),
                  { once: true },
                ),
              ),
            releaseLock() {},
          }),
        },
      };
    },
  };
  return {
    engine,
    client,
    Node,
    nodes,
    release,
    get requests() {
      return requests;
    },
  };
}
test("rapid playback inputs share one PCM connection and shutdown leaves no ghost audio", async () => {
  const f = fixture(),
    old = globalThis.AudioWorkletNode;
  globalThis.AudioWorkletNode = f.Node;
  try {
    const a = f.engine.stream(f.client),
      b = f.engine.stream(f.client);
    f.release();
    await Promise.all([a, b]);
    assert.equal(f.requests, 1);
    assert.equal(f.nodes.filter((n) => n.connected).length, 1);
    await f.engine.disconnect();
    await f.engine.readTask;
    assert.equal(f.nodes.filter((n) => n.connected).length, 0);
    assert.equal(f.engine.mode, "local");
    assert.ok(!f.engine.error);
  } finally {
    globalThis.AudioWorkletNode = old;
  }
});
test("cancel while the worklet loads does not start a late audio request", async () => {
  const f = fixture(),
    old = globalThis.AudioWorkletNode;
  globalThis.AudioWorkletNode = f.Node;
  try {
    const pending = f.engine.stream(f.client);
    await Promise.resolve();
    await Promise.resolve();
    await f.engine.disconnect();
    f.release();
    await pending;
    assert.equal(f.requests, 0);
    assert.equal(f.nodes.length, 0);
  } finally {
    globalThis.AudioWorkletNode = old;
  }
});
test("rejected stream does not leave a connected silent node claiming playback", async () => {
  const f = fixture(),
    old = globalThis.AudioWorkletNode;
  globalThis.AudioWorkletNode = f.Node;
  try {
    f.client.request = async () => {
      throw Error("unavailable");
    };
    f.release();
    await assert.rejects(f.engine.stream(f.client));
    assert.equal(f.nodes.filter((n) => n.connected).length, 0);
    assert.equal(f.engine.mode, "disconnected");
  } finally {
    globalThis.AudioWorkletNode = old;
  }
});

test("play without music fails silently instead of starting a test oscillator", async () => {
  const engine = new AudioEngine();
  let touched = false;
  engine.ready = async () => {
    touched = true;
  };
  await assert.rejects(engine.toggle(), /Выбери трек/);
  assert.equal(touched, false);
  assert.equal(engine.context, null);
});
