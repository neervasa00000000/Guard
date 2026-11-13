// SPDX-License-Identifier: MIT
// Blob workers keep the downloadable viewer self-contained and network-free.
function guardHashWorker() {
  self.onmessage = async ({ data }) => {
    try {
      const hashes = [];
      for (const bytes of data) {
        const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
        hashes.push(Array.from(digest, b => b.toString(16).padStart(2, '0')).join(''));
      }
      self.postMessage({ hashes });
    } catch (error) { self.postMessage({ error: error.message }); }
  };
}
export function createTileHasher(count) {
  const workers = [];
  let url;
  if (count > 1024 && typeof Worker === 'function') {
    try {
      url = URL.createObjectURL(new Blob(['(' + guardHashWorker.toString() + ')()'], { type: 'text/javascript' }));
      for (let i = 0; i < Math.min(8, globalThis.navigator?.hardwareConcurrency || 2); i++) workers.push(new Worker(url));
    } catch { for (const worker of workers) worker.terminate(); workers.length = 0; }
  }
  return {
    workerCount: workers.length,
    async hash(buffers) {
      if (!workers.length) return Promise.all(buffers.map(async bytes => {
        const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
        return Array.from(digest, b => b.toString(16).padStart(2, '0')).join('');
      }));
      const groups = workers.map(() => []);
      buffers.forEach((buffer, i) => groups[i % workers.length].push(buffer));
      const results = await Promise.all(workers.map((worker, i) => new Promise((resolve, reject) => {
        worker.onmessage = ({ data }) => data.error ? reject(new Error(data.error)) : resolve(data.hashes);
        worker.onerror = event => reject(new Error(event.message || 'Tile hash worker failed.'));
        worker.postMessage(groups[i], groups[i].map(buffer => buffer.buffer));
      })));
      return buffers.map((_, i) => results[i % workers.length][Math.floor(i / workers.length)]);
    },
    close() { for (const worker of workers) worker.terminate(); if (url) URL.revokeObjectURL(url); },
  };
}
