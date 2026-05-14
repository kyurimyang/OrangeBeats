import type { AnalyzeResponse } from './api';

const P = 'ob_';

function save<T>(key: string, val: T) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(P + key, JSON.stringify(val));
}

function load<T>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try { return JSON.parse(localStorage.getItem(P + key) ?? 'null') as T; }
  catch { return null; }
}

function remove(key: string) {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(P + key);
}

export const analyzeStore = {
  save: (d: AnalyzeResponse) => save('analyze', d),
  load: () => load<AnalyzeResponse>('analyze'),
  clear: () => remove('analyze'),
};

export interface PlaylistMeta {
  spotifyUrl: string;
  name: string;
  trackCount: number;
}

export const playlistStore = {
  save: (d: PlaylistMeta) => save('playlist', d),
  load: () => load<PlaylistMeta>('playlist'),
  clear: () => remove('playlist'),
};
