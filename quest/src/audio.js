export class AudioEngine {
  constructor() {
    this.context = null;
    this.generation = 0;
    this.connecting = null;
    this.pcmStats = null;
    this.media = null;
    this.source = null;
    this.abort = null;
    this.mode = "local";
    this.volume = 0.65;
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
  async toggle() {
    if (!this.media) throw Error("Выбери трек или войди в музыкальный сервис.");
    await this.ready();
    if (this.media.paused) await this.media.play();
    else this.media.pause();
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
  stream(client) {
    if (this.connecting) return this.connecting;
    if (this.mode === "pc" && this.pcm) return Promise.resolve();
    const pending = this.connectStream(client);
    this.connecting = pending;
    pending
      .finally(() => {
        if (this.connecting === pending) this.connecting = null;
      })
      .catch(() => {});
    return pending;
  }
  async connectStream(client) {
    await this.disconnect();
    const generation = this.generation;
    const current = () => generation === this.generation;
    let node = null,
      abort = null;
    try {
      this.error = "";
      this.mode = "connecting";
      await this.ready();
      await this.context.audioWorklet.addModule(
        new URL("./pcm-worklet.js", import.meta.url),
      );
      if (!current()) return;
      node = new AudioWorkletNode(this.context, "ember-pcm", {
        numberOfInputs: 0,
        outputChannelCount: [2],
        processorOptions: { inputRate: 48000 },
      });
      node.port.onmessage = (e) => {
        if (current()) this.pcmStats = e.data;
      };
      node.connect(this.gain);
      this.pcm = node;
      this.gain.gain.setTargetAtTime(1, this.context.currentTime, 0.03);
      abort = new AbortController();
      this.abort = abort;
      const response = await client.request("/api/audio", {
        signal: abort.signal,
        raw: true,
      });
      if (!current()) {
        node.disconnect();
        abort.abort();
        return;
      }
      const reader = response.body.getReader();
      this.mode = "pc";
      this.error = "";
      this.onchange?.();
      this.readTask = (async () => {
        let tail = new Uint8Array();
        try {
          while (current()) {
            const { value, done } = await reader.read();
            if (done) break;
            const joined = new Uint8Array(tail.length + value.length);
            joined.set(tail);
            joined.set(value, tail.length);
            const count = joined.length - (joined.length % 8);
            tail = joined.slice(count);
            if (count) {
              const bytes = joined.slice(0, count);
              node.port.postMessage(bytes.buffer, [bytes.buffer]);
            }
          }
        } catch (e) {
          if (current() && e.name !== "AbortError")
            this.error = "Передача звука остановилась";
        } finally {
          reader.releaseLock();
          node.disconnect();
          if (current()) {
            this.pcm = null;
            this.mode = "disconnected";
            this.error = "Передача звука остановилась. Подключи звук снова.";
            this.onchange?.();
          }
        }
      })();
    } catch (e) {
      node?.disconnect();
      abort?.abort();
      if (current()) {
        this.pcm = null;
        this.mode = "disconnected";
        this.error = "Не удалось подключить звук. Попробуй ещё раз.";
        this.onchange?.();
      }
      throw e;
    }
  }
  async disconnect() {
    this.generation++;
    this.pcmStats = null;
    this.abort?.abort();
    this.abort = null;
    if (this.pcm) {
      this.pcm.disconnect();
      this.pcm = null;
    }
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
