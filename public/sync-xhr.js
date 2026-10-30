// Makes v86's disk-part requests synchronous, so a sector read completes before the
// emulated CPU continues. Windows 95's ESDI_506 driver aborts I/O that completes late
// (same fix as encarta_95_web's patched v86, done here without forking the emulator).
// Load before libv86.js; call window.syncXhrPrefixes.push("disks/hd/") to opt URLs in.
(function () {
  const Native = window.XMLHttpRequest;
  const prefixes = (window.syncXhrPrefixes = []);
  const isSyncUrl = (url) => prefixes.some((p) => String(url).includes(p));

  class SyncDiskXHR extends Native {
    open(method, url, async = true, ...rest) {
      this._sync = async !== false && isSyncUrl(url);
      if (!this._sync) return super.open(method, url, async, ...rest);
      super.open(method, url, false);
      // sync XHR can't use responseType=arraybuffer in a document; read bytes as x-user-defined text
      super.overrideMimeType("text/plain; charset=x-user-defined");
    }
    get responseType() { return this._sync ? "arraybuffer" : super.responseType; }
    set responseType(v) { if (!this._sync) super.responseType = v; }
    get response() { return this._sync ? this._buf : super.response; }
    send(body) {
      if (!this._sync) return super.send(body);
      const onload = this.onload;
      this.onload = null; // fire it ourselves once the buffer is decoded
      try {
        super.send(body);
      } catch (e) {
        this.onload = onload;
        if (this.onerror) this.onerror(e);
        else throw e;
        return;
      }
      if (this.status === 200 || this.status === 206) {
        const text = this.responseText;
        const bytes = new Uint8Array(text.length);
        for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i) & 0xff;
        this._buf = bytes.buffer;
      }
      this.onload = onload;
      if (onload) onload.call(this, new ProgressEvent("load"));
    }
  }
  window.XMLHttpRequest = SyncDiskXHR;
})();
