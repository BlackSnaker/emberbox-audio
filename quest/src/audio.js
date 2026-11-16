export class AudioEngine {
  constructor() {
    this.context = null;
    this.media = null;
    this.source = null;
    this.abort = null;
    this.mode = "local";
    this.volume = 0.65;
    this.demoNodes = [];
    this.levels = new Float32Array(9);
    this.bins = new Uint8Array(512);
  }
  async ready() {
    if (!this.context) {
      this.context = new AudioContext({ sampleRate: 48000 });
      this.gain = this.context.createGain();
      this.gain.gain.value = this.volume;
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 1024;
      this.gain.connect(this.analyser);
      this.analyser.connect(this.context.destination);
    }
    await this.context.resume();
  }
  async open(file) {
    await this.disconnect();
    await this.ready();
    if (this.url) URL.revokeObjectURL(this.url);
    this.url = URL.createObjectURL(file);
    this.media = new Audio(this.url);
    this.source = this.context.createMediaElementSource(this.media);
    this.source.connect(this.gain);
    this.media.volume = 1;
    await this.media.play();
    return {
      title: file.name,
      artist: "Локальный файл",
      album: "На этом устройстве",
      image: "",
      playing: true,
      duration: 0,
      position: 0,
      source: "local",
    };
  }
  async demo() {
    await this.ready();
    this.stopDemo();
    const base = 110;
    for (const [i, ratio] of [1, 1.5, 2, 2.5].entries()) {
      const o = this.context.createOscillator(),
        g = this.context.createGain();
      o.type = "sine";
      o.frequency.value = base * ratio;
      g.gain.value = 0.025 / (i + 1);
      o.connect(g);
      g.connect(this.gain);
      o.start();
      this.demoNodes.push(o);
    }
    this.demoStarted = performance.now();
  }
  stopDemo() {
    for (const o of this.demoNodes) o.stop();
    this.demoNodes = [];
  }
  async toggle() {
    await this.ready();
    if (this.media) {
      if (this.media.paused) await this.media.play();
      else this.media.pause();
    } else if (this.demoNodes.length) this.stopDemo();
    else await this.demo();
  }
  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.gain)
      this.gain.gain.setTargetAtTime(
        this.mode === "pc" ? 1 : this.volume,
        this.context.currentTime,
        0.04,
      );
  }
  sample() {
    if (!this.analyser) return this.levels;
    this.analyser.getByteFrequencyData(this.bins);
    const edges = [1, 3, 5, 9, 16, 29, 53, 96, 174, 260];
    for (let n = 0; n < 9; n++) {
      let sum = 0;
      for (let i = edges[n]; i < edges[n + 1]; i++) sum += this.bins[i];
      this.levels[n] = Math.min(1, sum / ((edges[n + 1] - edges[n]) * 170));
    }
    return this.levels;
  }
  async stream(client) {
    await this.disconnect();
    await this.ready();
    await this.context.audioWorklet.addModule(
      new URL("./pcm-worklet.js", import.meta.url),
    );
    this.pcm = new AudioWorkletNode(this.context, "ember-pcm", {
      outputChannelCount: [2],
      processorOptions: { inputRate: 48000 },
    });
    this.pcm.connect(this.gain);
    this.gain.gain.setTargetAtTime(1, this.context.currentTime, 0.03);
    this.mode = "pc";
    this.abort = new AbortController();
    const streamNode = this.pcm;
    const response = await client.request("/api/audio", {
      signal: this.abort.signal,
      raw: true,
    });
    const reader = response.body.getReader();
    this.readTask = (async () => {
      let tail = new Uint8Array();
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const joined = new Uint8Array(tail.length + value.length);
          joined.set(tail);
          joined.set(value, tail.length);
          const count = joined.length - (joined.length % 8);
          tail = joined.slice(count);
          const bytes = joined.slice(0, count);
          streamNode.port.postMessage(bytes.buffer, [bytes.buffer]);
        }
      } catch (e) {
        if (e.name !== "AbortError") this.error = "Передача звука остановилась";
      } finally {
        reader.releaseLock();
        if (this.pcm === streamNode) {
          streamNode.disconnect();
          this.pcm = null;
          this.mode = "disconnected";
          this.error = "Передача звука остановилась. Подключи звук снова.";
          this.onchange?.();
        }
      }
    })();
  }
  async disconnect() {
    this.abort?.abort();
    this.abort = null;
    if (this.pcm) {
      this.pcm.disconnect();
      this.pcm = null;
    }
    this.stopDemo();
    if (this.media) {
      this.media.onended = null;
      this.media.pause();
      this.media.removeAttribute("src");
      this.media.load();
      this.media = null;
    }
    this.source?.disconnect();
    this.source = null;
    if (this.url) {
      URL.revokeObjectURL(this.url);
      this.url = null;
    }
    this.levels.fill(0);
    this.mode = "local";
  }
}
