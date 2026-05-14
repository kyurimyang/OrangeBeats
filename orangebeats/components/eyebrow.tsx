import { ReactNode } from 'react';

export function Eyebrow({ children, color = '#FD6D11' }: { children: ReactNode; color?: string }) {
  return (
    <div className="inline-flex items-center gap-2 ob-chip rounded-full px-3 py-1.5 text-[11px] font-mono tracking-[0.18em] uppercase text-white/70">
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
      {children}
    </div>
  );
}
