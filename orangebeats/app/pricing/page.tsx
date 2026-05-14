'use client';

import { useRouter } from 'next/navigation';
import { Eyebrow } from '@/components/eyebrow';
import { IconCheck } from '@/components/icons';

const PLANS = [
  {
    name: 'Free',
    price: '₩0',
    sub: '/ 평생',
    feats: ['월 5개 플레이리스트', '곡당 12개 후보', '텍스트 기반 매칭', '커뮤니티 지원'],
    color: '#FFFFFF',
    featured: false,
  },
  {
    name: 'Pro',
    price: '₩4,900',
    sub: '/ 월',
    feats: ['무제한 플레이리스트', '곡당 24개 후보', 'OCR 분석 무제한', 'ACR 100분 / 월', '이메일 지원'],
    color: '#FD6D11',
    featured: true,
  },
  {
    name: 'Studio',
    price: '₩14,900',
    sub: '/ 월',
    feats: ['Pro의 모든 기능', 'ACR 600분 / 월', 'API 접근', 'priority 매칭', '전담 지원'],
    color: '#5EEAD4',
    featured: false,
  },
];

export default function PricingPage() {
  const router = useRouter();
  return (
    <div className="min-h-screen pt-[68px] pb-24">
      <div className="mx-auto max-w-[1080px] px-8 pt-16">
        <div className="text-center">
          <Eyebrow>pricing</Eyebrow>
          <h1 className="mt-5 font-display text-[64px] tracking-[-0.03em] leading-[0.98] font-medium">
            <span className="ob-grad-text">필요한 만큼만,</span>
            <br />
            심플한 요금제.
          </h1>
        </div>

        <div className="mt-14 grid grid-cols-3 gap-5">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={`relative rounded-3xl p-7 ${p.featured ? 'ob-glass' : 'ob-glass-soft'}`}
            >
              {p.featured && (
                <div
                  className="absolute -top-3 left-7 px-3 py-1 rounded-full text-[11px] font-mono uppercase tracking-[0.15em] text-black"
                  style={{ background: 'linear-gradient(90deg, #FD6D11, #FFB07A)' }}
                >
                  most popular
                </div>
              )}
              <div className="text-[14px] font-mono uppercase tracking-[0.18em]" style={{ color: p.color }}>
                {p.name}
              </div>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-[44px] font-display font-medium tracking-tight">{p.price}</span>
                <span className="text-[14px] text-white/50">{p.sub}</span>
              </div>
              <ul className="mt-6 space-y-2.5">
                {p.feats.map((f) => (
                  <li key={f} className="flex items-center gap-2.5 text-[13px] text-white/75">
                    <IconCheck size={14} color={p.color} /> {f}
                  </li>
                ))}
              </ul>
              <button
                onClick={() => router.push('/url')}
                className={`mt-7 w-full h-11 rounded-full text-[13px] font-semibold ${
                  p.featured ? 'ob-btn-primary' : 'ob-btn-ghost text-white/85'
                }`}
              >
                {p.featured ? '시작하기' : '선택하기'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
