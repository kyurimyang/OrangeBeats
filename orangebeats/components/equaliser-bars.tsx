'use client';

export function EqualiserBars({ count = 4, color = '#FD6D11', size = 14 }: { count?: number; color?: string; size?: number }) {
  return (
    <div className="flex items-end gap-[2px]" style={{ height: size }}>
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className="ob-bar"
          style={{
            width: 2,
            height: '100%',
            background: color,
            borderRadius: 1,
            animationDelay: `${i * 0.15}s`,
            animationDuration: `${0.9 + (i % 3) * 0.25}s`,
            display: 'block',
          }}
        />
      ))}
    </div>
  );
}
