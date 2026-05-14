export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <defs>
          <linearGradient id="obg" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#FD6D11" />
            <stop offset="100%" stopColor="#5EEAD4" />
          </linearGradient>
        </defs>
        <circle cx="16" cy="16" r="15" fill="url(#obg)" />
        <circle cx="16" cy="16" r="4" fill="#0a0a0a" />
        <circle cx="16" cy="16" r="1.4" fill="#FD6D11" />
      </svg>
      <span className="font-semibold tracking-tight text-[18px]">
        <span className="text-white">orange</span>
        <span className="text-orange">beats</span>
      </span>
    </div>
  );
}
