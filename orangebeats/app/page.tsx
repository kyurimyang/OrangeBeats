'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eyebrow } from '@/components/eyebrow';
import { Footer } from '@/components/footer';
import { Vinyl } from '@/components/vinyl';
import { TrackCover } from '@/components/track-cover';
import { ConfidencePill } from '@/components/confidence-pill';
import { EqualiserBars } from '@/components/equaliser-bars';
import {
  IconYT, IconArrow, IconSpotify, IconSparkle, IconPlay,
} from '@/components/icons';
import { DEMO_VIDEO, DEMO_TRACKS, FEATURED_PLAYLISTS } from '@/lib/demo-data';

export default function LandingPage() {
  const [url, setUrl] = useState('');
  const router = useRouter();

  const handleSubmit = () => {
    const target = url || 'https://youtube.com/watch?v=ob-cp-mix-25';
    router.push(`/url?url=${encodeURIComponent(target)}`);
  };

  return (
    <div className="pt-[68px]">
      <HeroSection url={url} setUrl={setUrl} onSubmit={handleSubmit} />
      <HowToSection />
      <FeaturedSection />
      <BigCTASection />
      <Footer />
    </div>
  );
}

function HeroSection({ url, setUrl, onSubmit }: { url: string; setUrl: (v: string) => void; onSubmit: () => void }) {
  return (
    <section className="relative overflow-hidden">
      {/* glow backdrop */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute -top-32 left-1/2 -translate-x-1/2 w-[900px] h-[700px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(253,109,17,0.35), transparent 70%)' }}
        />
        <div
          className="absolute top-40 right-10 w-[420px] h-[420px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(94,234,212,0.20), transparent 70%)' }}
        />
        <div className="absolute inset-0 ob-dotgrid opacity-60" />
      </div>

      <div className="mx-auto max-w-[1280px] px-8 pt-24 pb-10">
        <div className="flex justify-center mb-7">
          <Eyebrow>NEW · 2026 archive update</Eyebrow>
        </div>

        <h1 className="text-center font-display font-medium tracking-[-0.04em] leading-[0.95] text-[88px] md:text-[104px]">
          <span className="ob-grad-text">Youtube Playlist를 ㅡ</span>
          <br />
          <span>링크 한번에 내 </span>
          <span className="ob-grad-accent">streaming</span>
          <span>으로.</span>
        </h1>

        <p className="mt-8 text-center text-white/60 text-[17px] leading-relaxed max-w-2xl mx-auto">
          Youtube Playlist를 이용하면서 힘들었던 적은 없었나요?{' '}
          <span className="text-white/85">orangebeats</span>가 한 번에 옮겨드려요.
          <br />
          좋아하는 스트리밍에서 그대로 듣고, 수정하고, 즐기세요.
        </p>

        {/* URL input */}
        <div className="mt-12 max-w-[760px] mx-auto">
          <div className="ob-input-shell">
            <div className="ob-input-inner h-[72px] flex items-center pl-6 pr-2 gap-3">
              <IconYT size={22} color="#FD6D11" />
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
                placeholder="https://www.youtube.com/watch?v=…"
                className="flex-1 bg-transparent outline-none text-[17px] placeholder:text-white/30 text-white"
              />
              <button
                onClick={onSubmit}
                className="ob-btn-primary h-[56px] px-7 rounded-full text-[15px] font-semibold inline-flex items-center gap-2"
              >
                Analyze
                <IconArrow size={16} color="white" />
              </button>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center gap-4 text-[12px] text-white/40">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-mint" /> 무료 · 회원가입 필요 없음
            </span>
            <span className="w-1 h-1 rounded-full bg-white/20" />
            <span>분당 24,800곡 매칭</span>
            <span className="w-1 h-1 rounded-full bg-white/20" />
            <span>OCR / ACR fallback 포함</span>
          </div>
        </div>

        {/* App preview */}
        <div className="mt-16 max-w-[1080px] mx-auto">
          <div className="ob-glass rounded-[28px] p-2.5 relative">
            <div className="rounded-[22px] bg-ink-900 border border-white/5 overflow-hidden">
              {/* browser chrome */}
              <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                <div className="flex items-center gap-2">
                  {['bg-white/15', 'bg-white/15', 'bg-white/15'].map((c, i) => (
                    <span key={i} className={`w-2.5 h-2.5 rounded-full ${c}`} />
                  ))}
                </div>
                <div className="font-mono text-[11px] text-white/40 tracking-wider">
                  orangebeats / candidate-matching
                </div>
                <div className="w-12" />
              </div>

              <div className="grid grid-cols-12 gap-0">
                {/* left: video info */}
                <div className="col-span-5 p-6 border-r border-white/5">
                  <div
                    className="aspect-video rounded-xl overflow-hidden relative"
                    style={{
                      background: 'linear-gradient(135deg, #FD6D11 0%, #2BB8A3 100%)',
                    }}
                  >
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-14 h-14 rounded-full bg-white/95 flex items-center justify-center">
                        <IconPlay size={20} color="#FD6D11" />
                      </div>
                    </div>
                    <div className="absolute bottom-2 right-2 font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/70">
                      {DEMO_VIDEO.duration}
                    </div>
                  </div>
                  <div className="mt-4 text-[13px] text-white/85 line-clamp-2 leading-snug">
                    {DEMO_VIDEO.title}
                  </div>
                  <div className="mt-1 text-[12px] text-white/40">
                    {DEMO_VIDEO.channel} · 24개 트랙 추출됨
                  </div>
                </div>

                {/* right: track list */}
                <div className="col-span-7 p-4">
                  <div className="flex items-center justify-between px-3 py-2">
                    <div className="text-[12px] text-white/50 font-mono tracking-wide">
                      TRACKLIST · 8 of 24
                    </div>
                    <ConfidencePill level="high" />
                  </div>
                  <div className="space-y-1.5 mt-1.5">
                    {DEMO_TRACKS.slice(0, 5).map((t) => (
                      <div key={t.id} className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/[0.04]">
                        <TrackCover seed={t.coverSeed} size={40} />
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] text-white truncate">{t.title}</div>
                          <div className="text-[11px] text-white/50 truncate">
                            {t.artist} · {t.album}
                          </div>
                        </div>
                        <ConfidencePill level={t.conf} />
                        <div className="text-[11px] text-white/40 font-mono w-8 text-right">
                          {t.duration}
                        </div>
                      </div>
                    ))}
                    <div className="px-3 py-2 text-[11px] text-white/40 text-center font-mono">
                      + 19 more tracks
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <Link
              href="/candidates"
              className="absolute inset-x-0 -bottom-3 mx-auto w-fit translate-y-full inline-flex items-center gap-1.5 text-[12px] text-white/50 hover:text-white"
            >
              <IconArrow size={14} /> 실제 결과 화면 미리보기
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowToSection() {
  const steps = [
    { n: '01', t: 'URL 붙여넣기',     d: 'Youtube Playlist 또는 영상 링크를 입력창에 붙여 넣고 Analyze를 눌러주세요.', icon: <IconYT size={22} color="#FD6D11" />,      color: '#FD6D11' },
    { n: '02', t: 'AI가 곡 정리',     d: '영상 속 트랙리스트를 추출하고, 후보 곡을 찾아 매칭해드려요.',               icon: <IconSparkle size={22} color="#FFB07A" />, color: '#FFB07A' },
    { n: '03', t: '스트리밍으로 저장', d: '후보를 확인·수정하고 한 번의 클릭으로 플레이리스트를 저장하세요.',           icon: <IconSpotify size={22} color="#5EEAD4" />, color: '#5EEAD4' },
  ];

  return (
    <section className="mx-auto max-w-[1280px] px-8 mt-24">
      <div className="flex items-end justify-between mb-10">
        <div>
          <Eyebrow color="#5EEAD4">How to use</Eyebrow>
          <h2 className="mt-4 font-display text-[56px] tracking-[-0.03em] leading-[1.02] font-medium">
            세 번의 클릭으로,
            <br />
            <span className="ob-grad-accent">완벽한 플레이리스트.</span>
          </h2>
        </div>
        <a className="text-white/60 hover:text-white text-[14px] inline-flex items-center gap-1.5" href="#">
          전체 가이드 보기 <IconArrow size={14} />
        </a>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {steps.map((s) => (
          <div key={s.n} className="ob-glass rounded-3xl p-7 relative overflow-hidden">
            <div className="flex items-start justify-between">
              <div className="w-11 h-11 rounded-2xl ob-chip flex items-center justify-center">
                {s.icon}
              </div>
              <span className="font-mono text-[11px] tracking-[0.2em] text-white/40">STEP {s.n}</span>
            </div>
            <h3 className="mt-7 text-[24px] font-medium tracking-tight">{s.t}</h3>
            <p className="mt-2.5 text-[14px] text-white/55 leading-relaxed">{s.d}</p>
            <div
              className="absolute -right-12 -bottom-12 w-40 h-40 rounded-full opacity-30"
              style={{ background: `radial-gradient(closest-side, ${s.color}, transparent 70%)` }}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

function FeaturedSection() {
  return (
    <section className="mx-auto max-w-[1280px] px-8 mt-28">
      <div className="flex items-end justify-between mb-10">
        <div>
          <Eyebrow color="#A78BFA">paran archive</Eyebrow>
          <h2 className="mt-4 font-display text-[56px] tracking-[-0.03em] leading-[1.02] font-medium">
            요즘 사람들이
            <br />
            옮기고 있는 플레이리스트.
          </h2>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4">
        {FEATURED_PLAYLISTS.map((p, i) => (
          <button key={p.title} className="text-left group">
            <div
              className="aspect-square rounded-2xl overflow-hidden relative"
              style={{
                background: `radial-gradient(120% 80% at 30% 20%, ${p.hue}33, transparent 60%), linear-gradient(160deg, ${p.hue}, #0a0a0a 90%)`,
              }}
            >
              <div className="absolute inset-0 p-5 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] tracking-[0.2em] text-white/70">
                    PL · {String(i + 1).padStart(2, '0')}
                  </span>
                  <EqualiserBars count={4} color="white" size={12} />
                </div>
                <div>
                  <div className="text-[20px] font-medium tracking-tight leading-tight">{p.title}</div>
                  <div className="mt-1 text-[12px] text-white/60">{p.count}곡 · 8.4k 저장</div>
                </div>
              </div>
              <div
                className="absolute -bottom-8 -right-8 w-32 h-32 rounded-full opacity-25"
                style={{ background: 'radial-gradient(closest-side, white, transparent 70%)' }}
              />
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

function BigCTASection() {
  const router = useRouter();
  return (
    <section className="mx-auto max-w-[1280px] px-8 mt-28">
      <div className="ob-glass rounded-[32px] p-12 relative overflow-hidden">
        <div className="grid grid-cols-12 gap-8 items-center relative z-10">
          <div className="col-span-7">
            <Eyebrow>ready when you are</Eyebrow>
            <h2 className="mt-5 font-display text-[64px] tracking-[-0.03em] leading-[0.98] font-medium">
              <span className="ob-grad-text">지금 옮기는 데</span>
              <br />
              <span>약 </span>
              <span className="text-orange">37초</span>
              <span>면 끝나요.</span>
            </h2>
            <p className="mt-5 text-white/55 text-[15px] max-w-md leading-relaxed">
              평균 1시간짜리 플레이리스트가 37초 안에 옮겨져요. 매칭이 어려운 곡은 OCR/ACR로 한
              번 더 시도해드려요.
            </p>
            <div className="mt-8 flex items-center gap-3">
              <button
                onClick={() => router.push('/url')}
                className="ob-btn-primary h-12 px-6 rounded-full text-[14px] font-semibold inline-flex items-center gap-2"
              >
                지금 옮기기 <IconArrow size={14} />
              </button>
              <Link
                href="/faq"
                className="ob-btn-ghost h-12 px-5 rounded-full text-[14px] text-white/80 inline-flex items-center gap-2"
              >
                FAQ 보기
              </Link>
            </div>
          </div>
          <div className="col-span-5 flex justify-end">
            <Vinyl size={280} label="late-summer mix" sublabel="orangebeats · 2026" />
          </div>
        </div>
        <div
          className="absolute -left-32 -bottom-32 w-[420px] h-[420px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(253,109,17,0.4), transparent 70%)' }}
        />
      </div>
    </section>
  );
}
