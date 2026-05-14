'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Eyebrow } from '@/components/eyebrow';
import { BrandMark } from '@/components/brand-mark';
import { TrackCover } from '@/components/track-cover';
import { IconCheck, IconSpotify, IconHeart, IconExternal, IconArrow, IconPlay, IconStar } from '@/components/icons';
import { DEMO_VIDEO, DEMO_TRACKS } from '@/lib/demo-data';
import { playlistStore, analyzeStore } from '@/lib/store';
import type { MatchResult } from '@/lib/api';

export default function PlaylistPage() {
  const router = useRouter();
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const [spotifyUrl, setSpotifyUrl] = useState<string | null>(null);
  const [playlistName, setPlaylistName] = useState(DEMO_VIDEO.title);
  const [tracks, setTracks] = useState<MatchResult[]>([]);
  const [usingDemo, setUsingDemo] = useState(true);

  useEffect(() => {
    const playlist = playlistStore.load();
    const analysis = analyzeStore.load();

    if (playlist) {
      setSpotifyUrl(playlist.spotifyUrl);
      setPlaylistName(playlist.name);
      setUsingDemo(false);
    }
    if (analysis?.results?.length) {
      setTracks(analysis.results.filter((r) => r.matched));
    }
  }, []);

  const matchedTracks = usingDemo ? DEMO_TRACKS : tracks;
  const trackCount = usingDemo ? DEMO_TRACKS.length : tracks.length;
  const avgConf = usingDemo
    ? 89
    : tracks.length
    ? Math.round((tracks.reduce((s, t) => s + t.confidence, 0) / tracks.length) * 100)
    : 0;

  return (
    <div className="min-h-screen pt-[68px] pb-24">
      {/* glow */}
      <div className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-[600px]">
        <div
          className="absolute top-32 left-1/2 -translate-x-1/2 w-[1100px] h-[700px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(94,234,212,0.20), transparent 70%)' }}
        />
      </div>

      <div className="mx-auto max-w-[1280px] px-8">
        {/* success header */}
        <div className="text-center mt-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-mint/30 bg-mint/[0.08]">
            <span className="w-6 h-6 rounded-full bg-mint flex items-center justify-center">
              <IconCheck size={14} color="black" />
            </span>
            <span className="text-[13px] text-mint font-medium">생성 완료</span>
          </div>
          <h1 className="mt-7 font-display text-[64px] tracking-[-0.03em] leading-[0.98] font-medium">
            <span className="ob-grad-text">Playlist를</span>
            <br />
            <span>성공적으로 만들었어요!</span>
          </h1>
          <p className="mt-4 text-white/55 text-[15px]">
            {trackCount}곡 모두 매칭됐어요. 지금 바로 스트리밍에서 열어보세요.
          </p>
        </div>

        {/* playlist hero card */}
        <div className="mt-12 ob-glass rounded-[28px] p-8 relative overflow-hidden">
          <div
            className="absolute -right-32 -top-32 w-[500px] h-[500px] rounded-full"
            style={{ background: 'radial-gradient(closest-side, rgba(253,109,17,0.25), transparent 70%)' }}
          />
          <div className="relative grid grid-cols-12 gap-8 items-end">
            {/* big cover */}
            <div className="col-span-3">
              <div
                className="aspect-square rounded-2xl overflow-hidden relative"
                style={{
                  background: 'linear-gradient(160deg, #FD6D11 0%, #C24A00 60%, #5EEAD4 110%)',
                  boxShadow: '0 30px 60px -20px rgba(253,109,17,0.6)',
                }}
              >
                <div className="absolute inset-0 ob-dotgrid opacity-30" />
                <div className="absolute inset-0 flex flex-col p-6 justify-between">
                  <div className="font-mono text-[11px] tracking-[0.25em] text-white/80">ORANGEBEATS</div>
                  <div>
                    <div className="text-[28px] font-display font-medium leading-[0.95] text-white line-clamp-3">
                      {playlistName}
                    </div>
                    <div className="mt-2 text-[12px] text-white/70 font-mono">PLAYLIST · 2026</div>
                  </div>
                </div>
              </div>
            </div>

            {/* meta */}
            <div className="col-span-9">
              <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
                Playlist · created
              </div>
              <h2 className="mt-2 font-display text-[44px] tracking-[-0.03em] leading-[1.05] font-medium line-clamp-2">
                {playlistName}
              </h2>
              <div className="mt-4 flex items-center gap-2 text-[13px] text-white/55">
                <BrandMark size={20} />
                <span className="text-white/30">·</span>
                <span>{trackCount}곡</span>
                <span className="text-white/30">·</span>
                <span className="text-mint">평균 일치율 {avgConf}%</span>
              </div>
              <div className="mt-7 flex items-center gap-3">
                {spotifyUrl ? (
                  <a
                    href={spotifyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ob-btn-primary h-12 px-6 rounded-full text-[14px] font-semibold inline-flex items-center gap-2"
                  >
                    <IconSpotify size={16} color="white" />
                    Spotify에서 바로 듣기
                    <IconExternal size={14} />
                  </a>
                ) : (
                  <button className="ob-btn-primary h-12 px-6 rounded-full text-[14px] font-semibold inline-flex items-center gap-2 opacity-50 cursor-not-allowed">
                    <IconSpotify size={16} color="white" />
                    Spotify에서 바로 듣기
                    <IconExternal size={14} />
                  </button>
                )}
                <button className="ob-btn-ghost h-12 px-5 rounded-full text-[14px] text-white/85 inline-flex items-center gap-2">
                  <IconHeart size={14} /> 좋아요
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* track list + rating */}
        <div className="mt-10 grid grid-cols-12 gap-6">
          {/* tracks */}
          <div className="col-span-8">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[12px] font-mono uppercase tracking-[0.2em] text-white/50">
                tracklist · {trackCount}
              </div>
            </div>
            <div className="ob-glass-soft rounded-2xl overflow-hidden">
              {usingDemo
                ? DEMO_TRACKS.map((t, i) => (
                    <div
                      key={t.id}
                      className="flex items-center px-5 py-3 border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] group"
                    >
                      <span className="w-8 text-[12px] font-mono text-white/40 group-hover:hidden">{i + 1}</span>
                      <button className="w-8 hidden group-hover:flex justify-center text-white">
                        <IconPlay size={14} color="white" />
                      </button>
                      <TrackCover seed={t.coverSeed} size={44} />
                      <div className="ml-3 flex-1 min-w-0">
                        <div className="text-[14px] truncate">{t.title}</div>
                        <div className="text-[12px] text-white/45 truncate">{t.artist}</div>
                      </div>
                      <div className="hidden md:block flex-1 min-w-0">
                        <div className="text-[12px] text-white/45 truncate">{t.album}</div>
                      </div>
                      <div className="w-20 text-right text-[12px] font-mono text-white/45">{t.duration}</div>
                      <div className="w-10 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="w-7 h-7 rounded-full hover:bg-white/10 flex items-center justify-center">
                          <IconHeart size={12} color="white" />
                        </button>
                      </div>
                    </div>
                  ))
                : tracks.map((t, i) => (
                    <div
                      key={t.spotify_uri ?? i}
                      className="flex items-center px-5 py-3 border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] group"
                    >
                      <span className="w-8 text-[12px] font-mono text-white/40 group-hover:hidden">{i + 1}</span>
                      <button className="w-8 hidden group-hover:flex justify-center text-white">
                        <IconPlay size={14} color="white" />
                      </button>
                      <TrackCover seed={i} size={44} imageUrl={t.album_image} />
                      <div className="ml-3 flex-1 min-w-0">
                        <div className="text-[14px] truncate">{t.spotify_title ?? t.input_title}</div>
                        <div className="text-[12px] text-white/45 truncate">{t.spotify_artist ?? t.input_artist}</div>
                      </div>
                      <div className="hidden md:block w-24 text-right">
                        <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${
                          t.confidence_label === 'high' ? 'text-mint bg-mint/10' : 'text-white/40 bg-white/[0.04]'
                        }`}>
                          {Math.round(t.confidence * 100)}%
                        </span>
                      </div>
                      <div className="w-10 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="w-7 h-7 rounded-full hover:bg-white/10 flex items-center justify-center">
                          <IconHeart size={12} color="white" />
                        </button>
                      </div>
                    </div>
                  ))}
            </div>
          </div>

          {/* rating + next actions */}
          <div className="col-span-4 space-y-4">
            <div className="ob-glass rounded-2xl p-6">
              {!submitted ? (
                <>
                  <Eyebrow color="#FFB07A">last step</Eyebrow>
                  <h3 className="mt-4 text-[22px] font-display font-medium tracking-tight leading-tight">
                    orangebeats는
                    <br />
                    어땠나요?
                  </h3>
                  <p className="mt-2 text-[12px] text-white/50 leading-relaxed">
                    여러분의 평가가 서비스 개선과 품질 향상에 큰 도움이 되어요.
                  </p>
                  <div className="mt-5 flex items-center gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        onClick={() => setRating(n)}
                        onMouseEnter={() => setHoverRating(n)}
                        onMouseLeave={() => setHoverRating(0)}
                        className="p-1"
                      >
                        <IconStar active={(hoverRating || rating) >= n} />
                      </button>
                    ))}
                    {rating > 0 && (
                      <span className="ml-2 text-[12px] text-white/60 font-mono">{rating}/5</span>
                    )}
                  </div>
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    rows={3}
                    placeholder="추가로 남기고 싶은 의견이 있다면…"
                    className="mt-4 w-full bg-white/[0.04] border border-white/10 rounded-xl px-3 py-2.5 text-[13px] outline-none focus:border-orange/50 placeholder:text-white/25 resize-none"
                  />
                  <button
                    onClick={() => rating > 0 && setSubmitted(true)}
                    disabled={rating === 0}
                    className={`mt-3 w-full h-11 rounded-full text-[13px] font-semibold transition ${
                      rating > 0 ? 'ob-btn-primary' : 'bg-white/[0.05] text-white/30 cursor-not-allowed'
                    }`}
                  >
                    평가 보내기
                  </button>
                </>
              ) : (
                <div className="text-center py-4">
                  <div className="w-16 h-16 mx-auto rounded-full bg-mint/10 border border-mint/30 flex items-center justify-center">
                    <IconCheck size={28} color="#5EEAD4" />
                  </div>
                  <div className="mt-4 text-[16px] font-medium">소중한 의견 감사해요 🙏</div>
                  <div className="mt-1 text-[12px] text-white/50">더 좋은 서비스로 보답할게요.</div>
                </div>
              )}
            </div>

            <button
              onClick={() => router.push('/url')}
              className="w-full ob-glass-soft hover:bg-white/[0.05] rounded-2xl p-5 text-left transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[14px] font-medium">다른 영상 더 옮기기</div>
                  <div className="text-[12px] text-white/50 mt-0.5">새 URL로 다시 시작</div>
                </div>
                <div className="w-9 h-9 rounded-full bg-white/[0.04] flex items-center justify-center">
                  <IconArrow size={14} />
                </div>
              </div>
            </button>

            <button
              onClick={() => router.push('/')}
              className="w-full ob-glass-soft hover:bg-white/[0.05] rounded-2xl p-5 text-left transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[14px] font-medium">홈으로 돌아가기</div>
                  <div className="text-[12px] text-white/50 mt-0.5">추천 플레이리스트 보기</div>
                </div>
                <div className="w-9 h-9 rounded-full bg-white/[0.04] flex items-center justify-center">
                  <IconArrow size={14} />
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
