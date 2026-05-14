import type { ConfidenceLevel } from '@/lib/demo-data';

const CONF_MAP: Record<ConfidenceLevel, { label: string; dot: string; bg: string; border: string }> = {
  high:    { label: '높은 일치율',      dot: '#5EEAD4', bg: 'rgba(94,234,212,0.10)',  border: 'rgba(94,234,212,0.35)' },
  similar: { label: '비슷한 곡 발견',   dot: '#FFB07A', bg: 'rgba(255,176,122,0.10)', border: 'rgba(255,176,122,0.35)' },
  live:    { label: '라이브 버전 가능성', dot: '#F1C40F', bg: 'rgba(241,196,15,0.10)',  border: 'rgba(241,196,15,0.30)' },
  alt:     { label: '다른 버전 추천',   dot: '#A78BFA', bg: 'rgba(167,139,250,0.10)', border: 'rgba(167,139,250,0.30)' },
};

export function ConfidencePill({ level }: { level: ConfidenceLevel }) {
  const m = CONF_MAP[level] ?? CONF_MAP.high;
  return (
    <span
      className="inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full text-[11px] font-medium"
      style={{ background: m.bg, border: `1px solid ${m.border}`, color: m.dot }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ background: m.dot, boxShadow: `0 0 8px ${m.dot}` }}
      />
      {m.label}
    </span>
  );
}
