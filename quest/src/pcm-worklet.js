class EmberPCM extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.data = new Float32Array(48000 * 2);
    this.write = 0;
    this.read = 0;
    this.count = 0;
    this.started = false;
    this.fade = 0;
    this.phase = 0;
    this.meterFrames = 0;
    this.peak = 0;
    this.step = (options.processorOptions?.inputRate || 48000) / sampleRate;
    this.port.onmessage = (e) => {
      const values = new Float32Array(e.data);
      for (let i = 0; i + 1 < values.length; i += 2) {
        if (this.count >= 48000) {
          this.read = (this.read + 1) % 48000;
          this.count--;
        }
        this.data[this.write * 2] = Number.isFinite(values[i]) ? values[i] : 0;
        this.data[this.write * 2 + 1] = Number.isFinite(values[i + 1])
          ? values[i + 1]
          : 0;
        this.write = (this.write + 1) % 48000;
        this.count++;
      }
      if (this.count > 16000) {
        const drop = this.count - 8000;
        this.read = (this.read + drop) % 48000;
        this.count -= drop;
      }
    };
  }
  process(_inputs, outputs) {
    const [left, right] = outputs[0];
    if (!left) return true;
    if (!this.started && this.count >= 6000) this.started = true;
    for (let n = 0; n < left.length; n++) {
      const valid = this.started && this.count > 2;
      this.fade += (Number(valid) - this.fade) * 0.015;
      if (valid) {
        const next = (this.read + 1) % 48000;
        left[n] =
          (this.data[this.read * 2] * (1 - this.phase) +
            this.data[next * 2] * this.phase) *
          this.fade;
        if (right)
          right[n] =
            (this.data[this.read * 2 + 1] * (1 - this.phase) +
              this.data[next * 2 + 1] * this.phase) *
            this.fade;
        this.phase += this.step;
        const advance = Math.floor(this.phase);
        this.phase -= advance;
        this.read = (this.read + advance) % 48000;
        this.count -= advance;
        this.peak = Math.max(
          this.peak,
          Math.abs(left[n]),
          Math.abs(right?.[n] || 0),
        );
      } else {
        left[n] = 0;
        if (right) right[n] = 0;
        if (this.count < 2) this.started = false;
      }
    }
    this.meterFrames += left.length;
    if (this.meterFrames >= sampleRate / 2) {
      this.port.postMessage?.({ buffer: this.count, peak: this.peak });
      this.meterFrames = 0;
      this.peak = 0;
    }
    return true;
  }
}
registerProcessor("ember-pcm", EmberPCM);
