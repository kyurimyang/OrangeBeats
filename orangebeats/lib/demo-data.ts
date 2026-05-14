export const DEMO_VIDEO = {
  title: '🍊 늦여름 드라이브 한 스푼 ☁️ City Pop Late-Summer Mix',
  channel: 'paran.fm',
  duration: '1:24:36',
  thumb: 0,
  url: 'https://youtube.com/watch?v=ob-cp-mix-25',
};

export type ConfidenceLevel = 'high' | 'similar' | 'live' | 'alt';

export interface Track {
  id: number;
  no: string;
  extracted: string;
  title: string;
  artist: string;
  album: string;
  duration: string;
  conf: ConfidenceLevel;
  coverSeed: number;
  year: number;
  kept?: boolean;
}

export interface AltCandidate {
  title: string;
  artist: string;
  album: string;
  duration: string;
  coverSeed: number;
  match: number;
}

export interface FeaturedPlaylist {
  title: string;
  count: number;
  hue: string;
  coverSeed: number;
}

export const DEMO_TRACKS: Track[] = [
  { id: 1, no: '01', extracted: 'Neon Marmalade — Yuna Hoshi',     title: 'Neon Marmalade',      artist: 'Yuna Hoshi',            album: 'Marmalade Sky',       duration: '4:53', conf: 'high',    coverSeed: 0, year: 2023 },
  { id: 2, no: '02', extracted: 'Stay a Little / Mira Kwon',       title: 'Stay a Little',       artist: 'Mira Kwon',             album: 'Pocket Garden',       duration: '4:12', conf: 'high',    coverSeed: 1, year: 2022 },
  { id: 3, no: '03', extracted: '4:00AM — Sora Cassette',          title: '4:00 AM',             artist: 'Sora Cassette',         album: 'Mignonette',          duration: '5:21', conf: 'similar', coverSeed: 2, year: 2024 },
  { id: 4, no: '04', extracted: 'Dress Down — paran (live ver.)',  title: 'Dress Down',          artist: 'paran',                 album: 'Live at Olympic Hall', duration: '3:48', conf: 'live',    coverSeed: 3, year: 2025 },
  { id: 5, no: '05', extracted: 'Summer Whisper — Anrie',          title: 'Last Summer Whisper', artist: 'Anrie',                 album: 'Timely Hours',        duration: '4:38', conf: 'alt',     coverSeed: 4, year: 2023 },
  { id: 6, no: '06', extracted: 'Yakimochi — Sora Cassette',       title: '야끼모찌',             artist: 'Sora Cassette',         album: 'Sunshower',           duration: '4:02', conf: 'similar', coverSeed: 5, year: 2022 },
  { id: 7, no: '07', extracted: 'Dress Code (city pop edit)',      title: 'Dress Code',          artist: 'Junko Oh',              album: 'Magical',             duration: '4:11', conf: 'high',    coverSeed: 6, year: 2024 },
  { id: 8, no: '08', extracted: 'Midnight Pretenders 83',          title: 'Midnight Pretenders', artist: 'Tomoko Aran (cover)',   album: 'Empty Space',         duration: '4:54', conf: 'high',    coverSeed: 7, year: 2024 },
];

export const ALT_CANDIDATES: Record<number, AltCandidate[]> = {
  1: [
    { title: 'Neon Marmalade (Extended Mix)',      artist: 'Yuna Hoshi',   album: 'Marmalade Sky 35th',    duration: '7:54', coverSeed: 9,  match: 74 },
    { title: 'Neon Marmalade (Friday Plans cover)', artist: 'Friday Plans', album: 'Cover Sessions EP',     duration: '4:33', coverSeed: 10, match: 62 },
  ],
  3: [
    { title: '4:00 AM (2024 Remaster)', artist: 'Sora Cassette', album: 'Mignonette Remaster', duration: '5:20', coverSeed: 2,  match: 91 },
    { title: '4 A.M.',                  artist: 'Anrie',          album: 'Heaven Beach',        duration: '4:48', coverSeed: 4,  match: 58 },
  ],
  4: [
    { title: 'Dress Down (Studio Ver.)', artist: 'paran', album: 'Lipstick',          duration: '3:31', coverSeed: 3,  match: 95 },
    { title: 'Dress Down (Remix)',       artist: 'paran', album: 'Single Collection', duration: '3:42', coverSeed: 11, match: 71 },
  ],
};

export const FEATURED_PLAYLISTS: FeaturedPlaylist[] = [
  { title: '늦여름 드라이브',      count: 24, hue: '#FD6D11', coverSeed: 0 },
  { title: 'City Pop Essentials',  count: 38, hue: '#5EEAD4', coverSeed: 1 },
  { title: 'K-Indie Quiet Hours',  count: 19, hue: '#A78BFA', coverSeed: 8 },
  { title: 'Lo-Fi 새벽 4시',       count: 42, hue: '#F1C40F', coverSeed: 6 },
  { title: '90s J-Ballad Archive', count: 31, hue: '#F87171', coverSeed: 5 },
];
