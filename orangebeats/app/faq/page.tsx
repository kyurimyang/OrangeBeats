'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eyebrow } from '@/components/eyebrow';
import { IconSparkle } from '@/components/icons';

const FAQ_ITEMS = [
  { q: 'orangebeats는 어떤 서비스인가요?', a: 'Youtube 영상이나 재생목록 URL을 붙여넣으면, AI가 트랙리스트를 추출해 다른 스트리밍 서비스(Spotify 등)에 같은 플레이리스트를 자동으로 만들어드려요.' },
  { q: '유료 결제가 필요한가요?', a: '기본 기능은 모두 무료예요. 단 ACR(오디오 지문 분석)은 분당 비용이 들기 때문에 월 100분까지 무료로 제공되고, 그 이상은 구독제로 운영됩니다.' },
  { q: '비공개 영상도 변환할 수 있나요?', a: '아쉽지만 비공개 영상은 메타데이터를 가져올 수 없어 변환이 불가능해요. 공개 또는 일부 공개 영상만 사용 가능합니다.' },
  { q: '곡이 잘못 매칭됐어요. 어떻게 바꿀 수 있나요?', a: '후보 화면에서 각 트랙 옆 ⌄ 아이콘을 누르면 다른 버전(라이브·리믹스 등)으로 교체할 수 있어요. 정 안 되면 "원하는 노래가 없어요"를 눌러 OCR/ACR로 재시도해주세요.' },
  { q: '커버곡·라이브 버전도 인식되나요?', a: '네, 신뢰도 라벨에 "live"나 "alt"가 표시됩니다. 원곡으로 바꾸고 싶다면 다른 후보에서 스튜디오 버전을 골라주세요.' },
  { q: '데이터 사용 정책은 어떻게 되나요?', a: '영상 URL과 사용자 평점 외 어떤 개인정보도 저장하지 않아요. 자세한 내용은 개인정보처리방침을 확인해주세요.' },
];

export default function FaqPage() {
  const router = useRouter();
  const [open, setOpen] = useState(0);

  return (
    <div className="min-h-screen pt-[68px] pb-24">
      <div className="mx-auto max-w-[920px] px-8 pt-16">
        <Eyebrow color="#A78BFA">Help center</Eyebrow>
        <h1 className="mt-5 font-display text-[64px] tracking-[-0.03em] leading-[0.98] font-medium">
          <span className="ob-grad-text">자주 묻는</span> 질문들.
        </h1>
        <p className="mt-4 text-white/55 text-[15px]">
          처음 써보시거나 문제가 생긴 분들을 위해 자주 묻는 질문을 모아뒀어요.
        </p>

        <div className="mt-12 space-y-3">
          {FAQ_ITEMS.map((it, i) => (
            <div
              key={i}
              className={`ob-glass-soft rounded-2xl transition-all ${
                open === i ? 'border-orange/30 bg-orange/[0.03]' : ''
              }`}
            >
              <button
                onClick={() => setOpen(open === i ? -1 : i)}
                className="w-full px-6 py-5 flex items-center justify-between gap-4 text-left"
              >
                <div className="flex items-center gap-4">
                  <span className="text-[12px] font-mono text-white/40 w-6">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-[16px] font-medium">{it.q}</span>
                </div>
                <span
                  className="shrink-0 text-white/50 transition-transform duration-200"
                  style={{ transform: open === i ? 'rotate(45deg)' : 'none' }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 5v14M5 12h14" strokeLinecap="round" />
                  </svg>
                </span>
              </button>
              {open === i && (
                <div className="px-6 pb-5 -mt-1 pl-[58px] text-[14px] text-white/70 leading-relaxed">
                  {it.a}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-16 ob-glass rounded-3xl p-8 flex items-center gap-6">
          <div className="w-14 h-14 rounded-2xl ob-chip flex items-center justify-center shrink-0">
            <IconSparkle size={22} color="#FFB07A" />
          </div>
          <div className="flex-1">
            <div className="text-[18px] font-medium">아직 답을 못 찾으셨나요?</div>
            <div className="text-[13px] text-white/55 mt-1">
              계정·문의는 contact@orangebeats.paran 으로 보내주세요. 24시간 안에 답변드려요.
            </div>
          </div>
          <button
            onClick={() => router.push('/')}
            className="ob-btn-primary h-11 px-5 rounded-full text-[13px] font-semibold shrink-0"
          >
            홈으로
          </button>
        </div>
      </div>
    </div>
  );
}
