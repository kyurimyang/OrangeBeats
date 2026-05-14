export function Vinyl({
  size = 180,
  label = 'preview',
  sublabel = '',
  spinning = true,
}: {
  size?: number;
  label?: string;
  sublabel?: string;
  spinning?: boolean;
}) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <div
        className={`absolute inset-0 rounded-full ${spinning ? 'ob-spin' : ''}`}
        style={{
          background: 'radial-gradient(circle, #1a1a1a 0%, #050505 70%)',
          boxShadow: '0 30px 60px -20px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.06)',
        }}
      >
        {[0.85, 0.7, 0.55, 0.42, 0.3].map((s, i) => (
          <div
            key={i}
            className="absolute inset-0 rounded-full"
            style={{ transform: `scale(${s})`, border: '1px solid rgba(255,255,255,0.04)' }}
          />
        ))}
        <div
          className="absolute inset-0 m-auto rounded-full flex flex-col items-center justify-center text-center"
          style={{
            width: '38%',
            height: '38%',
            background: 'linear-gradient(135deg, #FD6D11 0%, #C24A00 100%)',
            color: 'white',
            left: '31%',
            top: '31%',
          }}
        >
          <span className="text-[10px] uppercase tracking-[0.2em] opacity-80">orangebeats</span>
          <span className="text-[11px] font-semibold mt-0.5 leading-tight px-2">{label}</span>
          {sublabel && <span className="text-[9px] opacity-70 mt-0.5">{sublabel}</span>}
          <span className="w-2 h-2 rounded-full bg-black/80 mt-1.5" />
        </div>
      </div>
    </div>
  );
}
