'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Eyebrow } from '@/components/eyebrow';
import { IconYT, IconClose, IconArrow, IconCheck } from '@/components/icons';
import { DEMO_VIDEO } from '@/lib/demo-data';

export default function URLPage() {
  return (
    <Suspense>
      <URLPageInner />
    </Suspense>
  );
}

function URLPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [url, setUrl] = useState(searchParams.get('url') ?? '');
  const [titleMode, setTitleMode] = useState<'youtube' | 'custom'>('youtube');
  const [customTitle, setCustomTitle] = useState('');
  const [error, setError] = useState('');

  const isValid = /youtu(\.be|be\.com)/.test(url);

  const handleAnalyze = () => {
    if (!url) { setError('URL을 입력해주세요'); return; }
    if (!isValid) { setError('올바른 Youtube 링크인지 확인해주세요'); return; }
    setError('');
    const params = new URLSearchParams({ url, titleMode: titleMode === 'custom' ? 'custom' : 'auto' });
    if (titleMode === 'custom' && customTitle) params.set('title', customTitle);
    router.push(`/analyzing?${params.toString()}`);
  };

  return (
    <div className="min-h-screen pt-[68px] flex flex-col">
      {/* glow */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[900px] h-[700px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(253,109,17,0.25), transparent 70%)' }}
        />
        <div
          className="absolute bottom-1/4 right-10 w-[420px] h-[420px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, rgba(94,234,212,0.15), transparent 70%)' }}
        />
      </div>

      <div className="flex-1 flex items-center">
        <div className="mx-auto w-full max-w-[1080px] px-8 -mt-10">
          <div className="text-center">
            <Eyebrow>step 01 / 03</Eyebrow>
            <h1 className="mt-6 font-display text-[56px] md:text-[64px] tracking-[-0.03em] leading-[1.02] font-medium">
              <span className="ob-grad-text">Playlist를 생성할</span>
              <br />
              Youtube URL을 입력해주세요.
            </h1>
            <p className="mt-5 text-white/55 text-[15px]">
              영상 또는 재생목록 링크 모두 사용 가능해요. 비공개 영상은 인식되지 않을 수 있어요.
            </p>
          </div>

          {/* URL input */}
          <div className="mt-12 max-w-[800px] mx-auto">
            <div className={`ob-input-shell ${error ? 'is-error' : ''}`}>
              <div className="ob-input-inner h-[78px] flex items-center pl-7 pr-2 gap-3">
                <IconYT size={24} color="#FD6D11" />
                <input
                  value={url}
                  onChange={(e) => { setUrl(e.target.value); setError(''); }}
                  onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                  placeholder="Youtube URL 입력"
                  className="flex-1 bg-transparent outline-none text-[18px] placeholder:text-white/30 text-white"
                  autoFocus
                />
                {url && (
                  <button
                    onClick={() => setUrl('')}
                    className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center text-white/40 hover:text-white"
                  >
                    <IconClose size={14} />
                  </button>
                )}
                <button
                  onClick={handleAnalyze}
                  className="ob-btn-primary h-[62px] px-8 rounded-full text-[15px] font-semibold inline-flex items-center gap-2"
                >
                  Analyze
                  <IconArrow size={16} color="white" />
                </button>
              </div>
            </div>

            <div className="mt-3 min-h-[24px] text-center">
              {error ? (
                <span className="text-[13px] text-red-400 inline-flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-red-400" /> {error}
                </span>
              ) : url && isValid ? (
                <span className="text-[13px] text-mint inline-flex items-center gap-1.5">
                  <IconCheck size={14} color="#5EEAD4" /> 인식 가능한 링크예요
                </span>
              ) : (
                <span className="text-[13px] text-white/40">
                  예시 · youtube.com/playlist?list=… 또는 youtu.be/…
                </span>
              )}
            </div>
          </div>

          {/* Title strategy */}
          <div className="mt-14 max-w-[800px] mx-auto">
            <div className="text-center text-white/50 text-[13px] font-mono uppercase tracking-[0.2em]">
              플레이리스트 제목
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <TitleOption
                active={titleMode === 'youtube'}
                onClick={() => setTitleMode('youtube')}
                label="유튜브 제목 그대로 사용"
                hint="영상 제목을 그대로 가져와요"
                example={DEMO_VIDEO.title}
              />
              <TitleOption
                active={titleMode === 'custom'}
                onClick={() => setTitleMode('custom')}
                label="직접 제목 입력"
                hint="원하는 이름으로 저장해요"
                custom
                customValue={customTitle}
                onCustomChange={setCustomTitle}
              />
            </div>
          </div>

          {/* breadcrumb */}
          <div className="mt-16 flex items-center justify-center gap-2 text-[12px] text-white/40 font-mono uppercase tracking-[0.15em]">
            <span className="text-white">01 URL</span>
            <span className="text-white/20">───</span>
            <span>02 Analysis</span>
            <span className="text-white/20">───</span>
            <span>03 Playlist</span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface TitleOptionProps {
  active: boolean;
  onClick: () => void;
  label: string;
  hint: string;
  example?: string;
  custom?: boolean;
  customValue?: string;
  onCustomChange?: (v: string) => void;
}

function TitleOption({ active, onClick, label, hint, example, custom, customValue, onCustomChange }: TitleOptionProps) {
  return (
    <button
      onClick={onClick}
      className={`relative text-left p-5 rounded-2xl transition-all ${
        active ? 'ob-glass' : 'ob-glass-soft hover:bg-white/[0.05]'
      }`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${
            active ? 'border-orange' : 'border-white/30'
          }`}
        >
          {active && <span className="w-2 h-2 rounded-full bg-orange" />}
        </div>
        <div className="text-[15px] font-medium">{label}</div>
      </div>
      <div className="mt-2 ml-8 text-[12px] text-white/45">{hint}</div>
      <div className="mt-4 ml-8">
        {custom ? (
          <input
            value={customValue}
            onChange={(e) => onCustomChange?.(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            placeholder="예 · 새벽 4시 드라이브 모음"
            className="w-[90%] bg-white/[0.04] border border-white/10 rounded-lg h-10 px-3 text-[13px] outline-none focus:border-orange/50 placeholder:text-white/25"
          />
        ) : (
          <div className="text-[12px] text-white/35 line-clamp-1 italic">"{example}"</div>
        )}
      </div>
    </button>
  );
}
