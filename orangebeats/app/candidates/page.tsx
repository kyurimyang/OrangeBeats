'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Eyebrow } from '@/components/eyebrow';
import { TrackCover } from '@/components/track-cover';
import { ConfidencePill } from '@/components/confidence-pill';
import {
  IconScan, IconArrow, IconClose, IconRefresh, IconChevron,
  IconExternal, IconYT, IconCheck, IconMic,
} from '@/components/icons';
import { createPlaylist } from '@/lib/api';
import type { MatchResult, SpotifyCandidate, AnalyzeResponse } from '@/lib/api';
import { analyzeStore, playlistStore } from '@/lib/store';
import type { ConfidenceLevel } from '@/lib/demo-data';
import { DEMO_VIDEO, DEMO_TRACKS, ALT_CANDIDATES } from '@/lib/demo-data';

// Map backend confidence_label → design ConfidenceLevel
const CONF_MAP: Record<string, ConfidenceLevel> = {
  high: 'high', mid: 'similar', low: 'alt', failed: 'alt',
};

const CONF_WIDTH: Record<ConfidenceLevel, string> = {
  high: '92%', similar: '74%', live: '66%', alt: '48%',
};

// Internal track type (covers both real API data and demo fallback)
interface UITrack {
  id: number;
  no: string;
  extracted: string;
  title: string;
  artist: string;
  duration: string;
  conf: ConfidenceLevel;
  coverSeed: number;
  albumImage: string | null;
  spotifyUri: string | null;
  kept: boolean;
  alts: UIAlt[];
}

interface UIAlt {
  title: string;
  artist: string;
  albumImage: string | null;
  spotifyUri: string;
  match: number;
  coverSeed: number;
}

function resultToUITrack(r: MatchResult, idx: number): UITrack {
  return {
    id: idx + 1,
    no: String(idx + 1).padStart(2, '0'),
    extracted: `${r.input_artist} — ${r.input_title}`,
    title: r.spotify_title ?? r.input_title,
    artist: r.spotify_artist ?? r.input_artist,
    duration: '--:--',
    conf: CONF_MAP[r.confidence_label] ?? 'alt',
    coverSeed: idx % 9,
    albumImage: r.album_image,
    spotifyUri: r.spotify_uri,
    kept: r.matched,
    alts: r.top_candidates.slice(0, 2).map((c, ci) => ({
      title: c.spotify_title,
      artist: c.spotify_artist,
      albumImage: c.album_image,
      spotifyUri: c.spotify_uri,
      match: Math.round(c.confidence * 100),
      coverSeed: (idx + ci + 4) % 9,
    })),
  };
}

export default function CandidatesPage() {
  const router = useRouter();

  const [analyzeData, setAnalyzeData] = useState<AnalyzeResponse | null>(null);
  const [tracks, setTracks] = useState<UITrack[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showACR, setShowACR] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Load data from localStorage (set by analyzing page)
  useEffect(() => {
    const data = analyzeStore.load();
    if (data) {
      setAnalyzeData(data);
      setTracks((data.results ?? []).map(resultToUITrack));
    } else {
      // Fallback to demo data if no analysis result
      setTracks(DEMO_TRACKS.map((t, i) => ({
        id: t.id,
        no: t.no,
        extracted: t.extracted,
        title: t.title,
        artist: t.artist,
        duration: t.duration,
        conf: t.conf,
        coverSeed: t.coverSeed,
        albumImage: null,
        spotifyUri: null,
        kept: true,
        alts: (ALT_CANDIDATES[t.id] ?? []).map((a, ai) => ({
          title: a.title,
          artist: a.artist,
          albumImage: null,
          spotifyUri: '',
          match: a.match,
          coverSeed: a.coverSeed,
        })),
      })));
    }
  }, []);

  const kept = tracks.filter((t) => t.kept);
  const highConf = kept.filter((t) => t.conf === 'high').length;

  const toggleKeep = (id: number) =>
    setTracks((prev) => prev.map((x) => (x.id === id ? { ...x, kept: !x.kept } : x)));

  const pickAlt = (id: number, alt: UIAlt) =>
    setTracks((prev) =>
      prev.map((x) =>
        x.id === id
          ? { ...x, title: alt.title, artist: alt.artist, albumImage: alt.albumImage, spotifyUri: alt.spotifyUri, conf: 'high' }
          : x
      )
    );

  const handleCreatePlaylist = async () => {
    if (creating) return;
    const uris = kept.map((t) => t.spotifyUri).filter((u): u is string => Boolean(u));

    if (!analyzeData) {
      // Demo mode — just navigate to playlist page
      router.push('/playlist');
      return;
    }
    if (uris.length === 0) {
      setCreateError('Spotify에 매칭된 곡이 없어요. 곡을 다시 확인해주세요.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const res = await createPlaylist({
        youtube_url: analyzeData.youtube_url,
        youtube_title: analyzeData.youtube_title,
        title_mode: 'custom',
        playlist_name: analyzeData.playlist_name,
        track_uris: uris,
        thumbnail_url: analyzeData.thumbnail_url,
      });
      if (res.success) {
        playlistStore.save({
          spotifyUrl: res.playlist_url ?? '#',
          name: analyzeData.playlist_name,
          trackCount: res.added_count ?? uris.length,
        });
        router.push('/playlist');
      } else {
        setCreateError(res.detail ?? '플레이리스트 생성에 실패했어요.');
      }
    } catch (err: unknown) {
      const e = err as Error & { status?: number };
      if (e.status === 401) {
        setCreateError('Spotify 로그인이 필요해요. NavBar에서 로그인해주세요.');
      } else {
        setCreateError(e.message || '플레이리스트 생성에 실패했어요.');
      }
    } finally {
      setCreating(false);
    }
  };

  const videoTitle     = analyzeData?.youtube_title ?? DEMO_VIDEO.title;
  const videoUrl       = analyzeData?.youtube_url ?? DEMO_VIDEO.url;
  const thumbnailUrl   = analyzeData?.thumbnail_url ?? null;
  const trackCount     = tracks.length;

  return (
    <div className="min-h-screen pt-[68px] pb-24">
      <div className="mx-auto max-w-[1280px] px-8">
        {/* breadcrumb */}
        <div className="flex items-center gap-2 mt-8 text-[12px] text-white/40 font-mono uppercase tracking-[0.15em]">
          <button onClick={() => router.push('/')} className="hover:text-white">orangebeats</button>
          <span>/</span>
          <button onClick={() => router.push('/url')} className="hover:text-white">URL</button>
          <span>/</span>
          <span className="text-white">candidate matching</span>
        </div>

        {/* needs-fallback banner */}
        {analyzeData?.needs_fallback && (
          <div className="mt-6 ob-glass-soft rounded-2xl px-5 py-4 flex items-center gap-4 border-yellow-400/20">
            <span className="text-[13px] text-yellow-300">
              일부 곡 매칭이 불완전해요. OCR / ACR로 더 정확하게 시도해볼 수 있어요.
            </span>
            <button
              onClick={() => setShowACR(true)}
              className="ml-auto shrink-0 text-[12px] text-white/60 hover:text-white underline"
            >
              재시도
            </button>
          </div>
        )}

        {/* header */}
        <div className="mt-6 grid grid-cols-12 gap-8 items-end">
          <div className="col-span-7">
            <Eyebrow color="#5EEAD4">step 02 / 03 · {trackCount} tracks found</Eyebrow>
            <h1 className="mt-4 font-display text-[52px] tracking-[-0.03em] leading-[1.02] font-medium">
              <span className="ob-grad-text">Youtube에서</span>
              <br />
              음악을 가져왔어요.
            </h1>
            <p className="mt-4 text-white/55 text-[14px] max-w-md leading-relaxed">
              아래 트랙들이 영상에서 자동으로 추출된 결과예요. 신뢰도가 낮은 곡은 다른 후보로 바꾸거나 제거할 수 있어요.
            </p>
          </div>
          <div className="col-span-5">
            <div className="grid grid-cols-3 gap-3">
              <StatCard label="포함" value={`${kept.length}곡`} accent="#FD6D11" />
              <StatCard label="높은 신뢰" value={`${highConf}곡`} accent="#5EEAD4" />
              <StatCard label="총 트랙" value={`${trackCount}곡`} muted />
            </div>
          </div>
        </div>

        {/* video card */}
        <div className="mt-10 ob-glass rounded-2xl p-5 flex items-center gap-5">
          <div
            className="aspect-video w-[160px] rounded-xl overflow-hidden relative shrink-0"
            style={{ background: 'linear-gradient(135deg, #FD6D11 0%, #A78BFA 100%)' }}
          >
            {thumbnailUrl ? (
              <img src={thumbnailUrl} alt={videoTitle} className="absolute inset-0 w-full h-full object-cover" />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <IconYT size={28} color="white" />
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-white/40 font-mono uppercase tracking-[0.15em]">원본 영상</div>
            <div className="mt-1 text-[18px] font-medium tracking-tight line-clamp-1">{videoTitle}</div>
          </div>
          <a
            href={videoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ob-btn-ghost h-10 px-4 rounded-full text-[13px] text-white/75 inline-flex items-center gap-1.5"
          >
            <IconExternal size={12} /> Youtube에서 열기
          </a>
        </div>

        {/* track list */}
        <div className="mt-6 ob-glass-soft rounded-2xl overflow-hidden">
          <div className="px-5 py-3 flex items-center text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 border-b border-white/5">
            <span className="w-10">#</span>
            <span className="flex-1">extracted ⟶ matched</span>
            <span className="w-32">match</span>
            <span className="w-20 text-right">length</span>
            <span className="w-24" />
          </div>

          {tracks.map((t) => (
            <CandidateRow
              key={t.id}
              track={t}
              expanded={expanded === t.id}
              onToggleExpand={() => setExpanded(expanded === t.id ? null : t.id)}
              onToggleKeep={() => toggleKeep(t.id)}
              onPickAlt={(alt) => { pickAlt(t.id, alt); setExpanded(null); }}
            />
          ))}
        </div>

        {/* error message */}
        {createError && (
          <div className="mt-4 text-[13px] text-red-400 text-center">{createError}</div>
        )}

        {/* footer actions */}
        <div className="mt-10 flex items-center justify-between gap-4">
          <button
            onClick={() => setShowACR(true)}
            className="ob-btn-ghost h-12 px-5 rounded-full text-[14px] text-white/85 inline-flex items-center gap-2"
          >
            <IconScan size={16} /> 원하는 노래가 없어요
            <span className="text-white/40 text-[12px] ml-1">OCR · ACR로 다시 시도</span>
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/url')}
              className="text-white/60 hover:text-white text-[14px] h-12 px-5 inline-flex items-center"
            >
              다시 입력
            </button>
            <button
              onClick={handleCreatePlaylist}
              disabled={creating}
              className="ob-btn-primary h-12 px-7 rounded-full text-[14px] font-semibold inline-flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {creating ? '생성 중…' : '이대로 Playlist 만들기'}
              {!creating && <IconArrow size={16} color="white" />}
            </button>
          </div>
        </div>
      </div>

      {showACR && (
        <ACRModal
          onClose={() => setShowACR(false)}
          onConfirm={(method) => {
            setShowACR(false);
            const params = new URLSearchParams({ url: videoUrl, mode: method });
            router.push(`/analyzing?${params.toString()}`);
          }}
        />
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, accent, muted }: { label: string; value: string; accent?: string; muted?: boolean }) {
  return (
    <div className={`rounded-2xl p-4 border ${muted ? 'border-white/[0.06] bg-white/[0.02]' : 'ob-glass'}`}>
      <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">{label}</div>
      <div className="mt-1.5 text-[24px] font-medium tracking-tight" style={{ color: accent ?? 'white' }}>
        {value}
      </div>
    </div>
  );
}

function CandidateRow({
  track, expanded, onToggleExpand, onToggleKeep, onPickAlt,
}: {
  track: UITrack;
  expanded: boolean;
  onToggleExpand: () => void;
  onToggleKeep: () => void;
  onPickAlt: (alt: UIAlt) => void;
}) {
  return (
    <div className={`border-b border-white/5 transition-opacity ${track.kept ? '' : 'opacity-40'}`}>
      <div className="px-5 py-3 flex items-center hover:bg-white/[0.02] group">
        <span className="w-10 text-[12px] font-mono text-white/40">{track.no}</span>
        <div className="flex-1 flex items-center gap-3 min-w-0">
          <TrackCover seed={track.coverSeed} size={48} imageUrl={track.albumImage} />
          <div className="min-w-0">
            <div className="text-[14px] text-white truncate">{track.title}</div>
            <div className="text-[12px] text-white/65 truncate">{track.artist}</div>
            <div className="text-[11px] text-white/30 truncate">
              <span className="italic mr-1">from</span>
              {track.extracted}
            </div>
          </div>
        </div>
        <div className="w-32 pr-4">
          <ConfidencePill level={track.conf} />
          <div className="mt-1.5 ob-meter">
            <span style={{ width: CONF_WIDTH[track.conf] }} />
          </div>
        </div>
        <span className="w-20 text-right text-[12px] font-mono text-white/50">{track.duration}</span>
        <div className="w-24 flex items-center justify-end gap-1">
          {track.alts.length > 0 && (
            <button
              onClick={onToggleExpand}
              className={`w-9 h-9 rounded-full flex items-center justify-center transition ${
                expanded ? 'bg-orange/15 text-orange' : 'hover:bg-white/10 text-white/60'
              }`}
            >
              <IconChevron size={14} dir={expanded ? 'up' : 'down'} />
            </button>
          )}
          <button
            onClick={onToggleKeep}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition ${
              track.kept ? 'hover:bg-white/10 text-white/60' : 'bg-white/10 text-white'
            }`}
          >
            {track.kept ? <IconClose size={14} /> : <IconRefresh size={14} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-5 pb-5 pt-1 bg-white/[0.02]">
          <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mb-3 pl-[52px]">
            다른 후보 · {track.alts.length}
          </div>
          <div className="grid grid-cols-2 gap-3 pl-[52px]">
            {track.alts.map((alt, ai) => (
              <button
                key={ai}
                onClick={() => onPickAlt(alt)}
                className="ob-glass-soft rounded-xl p-3 flex items-center gap-3 text-left hover:bg-white/[0.05] transition"
              >
                <TrackCover seed={alt.coverSeed} size={44} imageUrl={alt.albumImage} />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] truncate">{alt.title}</div>
                  <div className="text-[11px] text-white/45 truncate">{alt.artist}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[11px] font-mono text-mint">{alt.match}%</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ACRModal({ onClose, onConfirm }: { onClose: () => void; onConfirm: (method: 'ocr' | 'acr') => void }) {
  const [method, setMethod] = useState<'ocr' | 'acr'>('ocr');
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center px-8">
      <div className="ob-glass rounded-3xl max-w-[680px] w-full p-8 relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white"
        >
          <IconClose size={16} />
        </button>

        <Eyebrow>fallback methods</Eyebrow>
        <h2 className="mt-4 font-display text-[32px] tracking-tight font-medium">
          영상에 더 어울리는 분석 방법을 골라주세요.
        </h2>
        <p className="mt-2 text-[13px] text-white/55 leading-relaxed">
          텍스트 기반 추출로 못 찾은 곡들을 한 번 더 시도해드려요.
        </p>

        <div className="mt-7 grid grid-cols-2 gap-3">
          {([
            { id: 'ocr' as const, label: 'OCR', sub: 'optical character recognition', desc: '영상 속 자막·앨범 이미지에서 글자를 읽어 곡 정보를 찾아요.', best: '자막이 있는 라이브·라디오 영상에 좋아요', icon: <IconScan size={20} color="#FD6D11" /> },
            { id: 'acr' as const, label: 'ACR', sub: 'audio content recognition',    desc: '실제 음원의 지문을 분석해 곡을 식별해요. 더 느리지만 정확해요.', best: '자막이 없는 모음집·믹스에 좋아요', icon: <IconMic size={20} color="#5EEAD4" /> },
          ]).map((m) => (
            <button
              key={m.id}
              onClick={() => setMethod(m.id)}
              className={`text-left rounded-2xl p-5 border transition ${
                method === m.id ? 'border-orange/40 bg-orange/[0.04]' : 'border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04]'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="w-11 h-11 rounded-xl ob-chip flex items-center justify-center">{m.icon}</div>
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${method === m.id ? 'border-orange bg-orange' : 'border-white/30'}`}>
                  {method === m.id && <IconCheck size={12} color="black" />}
                </div>
              </div>
              <div className="mt-5">
                <div className="text-[20px] font-semibold tracking-tight">{m.label}</div>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mt-1">{m.sub}</div>
              </div>
              <div className="mt-4 text-[13px] text-white/65 leading-relaxed">{m.desc}</div>
              <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-mint font-mono">
                <span className="w-1 h-1 rounded-full bg-mint" /> {m.best}
              </div>
            </button>
          ))}
        </div>

        <div className="mt-8 flex items-center justify-between">
          <div className="text-[11px] font-mono text-white/40">
            예상 시간 · {method === 'ocr' ? '~18s' : '~45s'}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="ob-btn-ghost h-11 px-5 rounded-full text-[13px] text-white/75">
              취소
            </button>
            <button onClick={() => onConfirm(method)} className="ob-btn-primary h-11 px-6 rounded-full text-[13px] font-semibold inline-flex items-center gap-2">
              실행하기 <IconArrow size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
