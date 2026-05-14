const COVER_PALETTES: [string, string][] = [
  ['#FD6D11', '#7A1B00'], ['#5EEAD4', '#0B5A53'], ['#F1C40F', '#693F0A'],
  ['#A78BFA', '#321B66'], ['#F87171', '#4C0E16'], ['#34D399', '#0B3E2A'],
  ['#FFB07A', '#5A2D14'], ['#60A5FA', '#0F2D60'], ['#E879F9', '#4E0E5D'],
  ['#FD6D11', '#A78BFA'], ['#5EEAD4', '#F1C40F'], ['#F87171', '#5EEAD4'],
];

interface TrackCoverProps {
  seed?: number;
  size?: number;
  label?: string;
  imageUrl?: string | null;
}

export function TrackCover({ seed = 0, size = 64, label, imageUrl }: TrackCoverProps) {
  if (imageUrl) {
    return (
      <div
        className="relative shrink-0 rounded-md overflow-hidden"
        style={{ width: size, height: size }}
        aria-label={label}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageUrl} alt={label ?? ''} className="w-full h-full object-cover" />
      </div>
    );
  }

  const [c1, c2] = COVER_PALETTES[seed % COVER_PALETTES.length];
  const angle = (seed * 37) % 360;
  const shapes = seed % 3;

  return (
    <div
      className="relative shrink-0 rounded-md overflow-hidden"
      style={{ width: size, height: size, background: `linear-gradient(${angle}deg, ${c1} 0%, ${c2} 100%)` }}
      aria-label={label}
    >
      <svg viewBox="0 0 64 64" className="absolute inset-0 w-full h-full" style={{ mixBlendMode: 'overlay', opacity: 0.6 }}>
        {shapes === 0 && <circle cx={20 + seed * 2} cy={20 + seed * 3} r={18} fill="white" />}
        {shapes === 1 && <path d={`M0 ${20 + seed} Q32 ${seed * 2} 64 ${30 + seed} L64 64 L0 64 Z`} fill="white" />}
        {shapes === 2 && <rect x={8} y={32 - (seed % 8)} width={48} height={8} fill="white" />}
      </svg>
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.35), transparent 50%)' }}
      />
    </div>
  );
}
