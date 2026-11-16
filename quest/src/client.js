import { decodeArtwork } from "./artwork.js";
export class EmberClient {
  constructor() {
    const hash = new URLSearchParams(location.hash.slice(1));
    this.bridgeMode =
      hash.get("bridge") || localStorage.getItem("ember-quest-bridge") || "pc";
    if (!["pc", "quest"].includes(this.bridgeMode)) this.bridgeMode = "pc";
    if (hash.get("bridge"))
      localStorage.setItem("ember-quest-bridge", this.bridgeMode);
    this.base =
      location.protocol === "https:"
        ? "http://localhost:" + (this.bridgeMode === "quest" ? 8768 : 8769)
        : "";
    this.token =
      hash.get("pair") ||
      localStorage.getItem("ember-quest-pair") ||
      sessionStorage.getItem("ember-quest-pair") ||
      "";
    if (this.token) {
      localStorage.setItem("ember-quest-pair", this.token);
      history.replaceState(null, "", location.pathname);
    }
    this.error = "";
    this.online = false;
    this.state = null;
    this.listeners = new Set();
    this.stopped = false;
  }
  async request(path, options = {}) {
    const { raw, ...rest } = options;
    const response = await fetch(this.base + path, {
      ...rest,
      headers: {
        Authorization: `Bearer ${this.token}`,
        ...(rest.body ? { "Content-Type": "application/json" } : {}),
        ...rest.headers,
      },
    });
    if (!response.ok) {
      let message = `Ошибка подключения: ${response.status}`;
      try {
        message = (await response.json()).error || message;
      } catch {}
      throw Error(message);
    }
    return raw ? response : response.json();
  }
  forget() {
    this.token = "";
    localStorage.removeItem("ember-quest-pair");
    sessionStorage.removeItem("ember-quest-pair");
    this.online = false;
  }
  action(op, details = {}) {
    return this.request("/api/action", {
      method: "POST",
      body: JSON.stringify({ op, ...details }),
    });
  }
  browse(category, term = "", collection = null, offset = 0) {
    return this.request("/api/browse", {
      method: "POST",
      body: JSON.stringify({ category, term, collection, offset }),
    });
  }
  async poll() {
    while (!this.stopped) {
      try {
        if (!this.token)
          throw Error(
            "Режим без ПК: открой парную ссылку из Ember для подключения сервисов.",
          );
        this.state = await this.request("/api/state", {
          signal: AbortSignal.timeout(5000),
        });
        this.online = true;
        this.error = "";
      } catch (e) {
        this.online = false;
        this.error =
          location.protocol === "https:" && e instanceof TypeError
            ? this.bridgeMode === "quest"
              ? "Открой Ember Quest заново: движок шлема пока недоступен."
              : "Проверь USB и разрешение локальной сети для Ember Quest."
            : e.message;
      }
      for (const fn of this.listeners) fn(this.state);
      await new Promise((r) => setTimeout(r, this.online ? 100 : 1500));
    }
  }
  async image(url) {
    if (!url) return null;
    const response = await this.request(
      "/api/image?url=" + encodeURIComponent(url),
      { raw: true },
    );
    // WebGL cannot apply UNPACK_FLIP_Y to ImageBitmap. Perform this at
    // decode time; Texture.flipY alone leaves service artwork upside down.
    return decodeArtwork(await response.blob());
  }
}
export const initialState = {
  title: "Твоя комната прослушивания",
  artist: "EMBER · QUEST",
  album: "Локальные файлы или подключение к Ember на ПК",
  source: "local",
  playing: false,
  position: 0,
  duration: 0,
  volume: 0.65,
  levels: Array(9).fill(0),
  queue: [],
  flow: false,
};
