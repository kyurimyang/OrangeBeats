// Shared UI components for Orange Beats
// Globals: Logo, NavBar, BrandMark, Footer, IconYT, IconSpotify, IconArrow, IconCheck, IconSparkle, IconWave,
//          TrackCover, EqualiserBars, Vinyl, RatingStars, ConfidencePill

const { useState, useEffect, useRef, useMemo } = React;

// ───────────────────────── Icons (custom strokes only) ─────────────────────────
const IconYT = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/>
    <path d="M10.5 9.5 L15 12 L10.5 14.5 Z" fill={color} stroke="none"/>
  </svg>
);
const IconSpotify = ({size=18, color='currentColor'}) => (
  // Original waveform-disc mark (not the Spotify logo)
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round">
    <circle cx="12" cy="12" r="9.5"/>
    <path d="M6.5 9.5c3.5-1.2 7.5-1.2 11 .3"/>
    <path d="M7 12.5c3-1 6.5-1 9.5.3"/>
    <path d="M7.5 15.2c2.5-.8 5.4-.8 7.7.3"/>
  </svg>
);
const IconArrow = ({size=18, color='currentColor', dir='right'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
       style={{transform: dir==='left'?'scaleX(-1)':dir==='down'?'rotate(90deg)':'none'}}>
    <path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>
  </svg>
);
const IconCheck = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12.5l4 4L19 7"/>
  </svg>
);
const IconSparkle = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
    <path d="M12 2 L13.6 9.6 L21 11 L13.6 12.4 L12 20 L10.4 12.4 L3 11 L10.4 9.6 Z"/>
  </svg>
);
const IconPlay = ({size=18, color='currentColor', filled=true}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={filled?color:'none'} stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round">
    <path d="M7 5 L19 12 L7 19 Z"/>
  </svg>
);
const IconRefresh = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/>
    <path d="M21 3v5h-5"/>
    <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/>
    <path d="M3 21v-5h5"/>
  </svg>
);
const IconClose = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round">
    <path d="M6 6 L18 18 M18 6 L6 18"/>
  </svg>
);
const IconChevron = ({size=18, color='currentColor', dir='down'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
       style={{transform: dir==='up'?'rotate(180deg)':dir==='left'?'rotate(90deg)':dir==='right'?'rotate(-90deg)':'none', transition:'transform .2s'}}>
    <path d="M6 9l6 6 6-6"/>
  </svg>
);
const IconExternal = ({size=14, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 5h5v5"/><path d="M19 5L10 14"/><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>
  </svg>
);
const IconHeart = ({size=18, color='currentColor', filled=false}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={filled?color:'none'} stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 21s-7-4.5-9.3-9.3C1 8 3.5 4.5 7 4.5c2 0 3.6 1.1 5 3 1.4-1.9 3-3 5-3 3.5 0 6 3.5 4.3 7.2C19 16.5 12 21 12 21z"/>
  </svg>
);
const IconScan = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8V5a2 2 0 0 1 2-2h3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>
    <path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M21 16v3a2 2 0 0 1-2 2h-3"/>
    <path d="M7 12h10"/>
  </svg>
);
const IconMic = ({size=18, color='currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="3" width="6" height="12" rx="3"/>
    <path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/>
  </svg>
);

// ───────────────────────── Brand mark ─────────────────────────
function BrandMark({size=28}) {
  return (
    <div className="flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <defs>
          <linearGradient id="obg" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#FD6D11"/>
            <stop offset="100%" stopColor="#5EEAD4"/>
          </linearGradient>
        </defs>
        <circle cx="16" cy="16" r="15" fill="url(#obg)"/>
        <circle cx="16" cy="16" r="4" fill="#0a0a0a"/>
        <circle cx="16" cy="16" r="1.4" fill="#FD6D11"/>
      </svg>
      <span className="font-semibold tracking-tight text-[18px]">
        <span className="text-white">orange</span><span className="text-orange">beats</span>
      </span>
    </div>
  );
}

// ───────────────────────── Nav ─────────────────────────
function NavBar({ route, onNavigate, accentColor }) {
  const links = [
    { id: 'landing', label: 'Home' },
    { id: 'url', label: 'Convert' },
    { id: 'faq', label: 'FAQ' },
    { id: 'pricing', label: 'Pricing' },
  ];
  return (
    <header className="ob-nav fixed top-0 inset-x-0 z-50 h-[68px] flex items-center">
      <div className="mx-auto w-full max-w-[1280px] px-8 flex items-center justify-between">
        <button onClick={()=>onNavigate('landing')} className="flex items-center"><BrandMark/></button>
        <nav className="flex items-center gap-1">
          {links.map(l => (
            <button
              key={l.id}
              onClick={()=>onNavigate(l.id)}
              className={`px-3.5 py-2 rounded-full text-[14px] transition ${route===l.id ? 'text-white bg-white/[0.06]' : 'text-white/60 hover:text-white'}`}
            >{l.label}</button>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <button className="ob-btn-ghost h-9 px-3.5 rounded-full text-[13px] text-white/80 hover:text-white inline-flex items-center gap-1.5">
            로그인
          </button>
          <button
            onClick={()=>onNavigate('url')}
            className="h-9 pl-3 pr-4 rounded-full text-[13px] font-medium inline-flex items-center gap-2 text-black"
            style={{ background: 'linear-gradient(180deg, #fff, #d8d8d8)' }}
          >
            <IconSpotify size={14} color="#0a0a0a"/>
            Spotify 연동
          </button>
        </div>
      </div>
    </header>
  );
}

// ───────────────────────── Track cover (procedural) ─────────────────────────
const COVER_PALETTES = [
  ['#FD6D11', '#7A1B00'], ['#5EEAD4', '#0B5A53'], ['#F1C40F', '#693F0A'],
  ['#A78BFA', '#321B66'], ['#F87171', '#4C0E16'], ['#34D399', '#0B3E2A'],
  ['#FFB07A', '#5A2D14'], ['#60A5FA', '#0F2D60'], ['#E879F9', '#4E0E5D'],
];
function TrackCover({ seed=0, size=64, label }) {
  const [c1, c2] = COVER_PALETTES[seed % COVER_PALETTES.length];
  const angle = (seed*37) % 360;
  const shapes = (seed % 3);
  return (
    <div
      className="relative shrink-0 rounded-md overflow-hidden"
      style={{
        width: size, height: size,
        background: `linear-gradient(${angle}deg, ${c1} 0%, ${c2} 100%)`,
      }}
      aria-label={label}
    >
      {/* decorative geometry */}
      <svg viewBox="0 0 64 64" className="absolute inset-0 w-full h-full" style={{ mixBlendMode:'overlay', opacity:0.6 }}>
        {shapes===0 && <circle cx={20+seed*2} cy={20+seed*3} r={18} fill="white"/>}
        {shapes===1 && <path d={`M0 ${20+seed} Q32 ${seed*2} 64 ${30+seed} L64 64 L0 64 Z`} fill="white"/>}
        {shapes===2 && <rect x={8} y={32-seed%8} width={48} height={8} fill="white"/>}
      </svg>
      <div className="absolute inset-0" style={{
        background: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.35), transparent 50%)',
      }}/>
    </div>
  );
}

// ───────────────────────── Equaliser bars ─────────────────────────
function EqualiserBars({ count=4, color='#FD6D11', size=14 }) {
  return (
    <div className="flex items-end gap-[2px]" style={{ height: size }}>
      {Array.from({length: count}).map((_,i)=>(
        <span
          key={i}
          className="ob-bar"
          style={{
            width: 2, height: '100%',
            background: color,
            borderRadius: 1,
            animationDelay: `${i*0.15}s`,
            animationDuration: `${0.9 + (i%3)*0.25}s`,
          }}
        />
      ))}
    </div>
  );
}

// ───────────────────────── Confidence pill ─────────────────────────
function ConfidencePill({ level }) {
  // level: high | similar | live | alt
  const map = {
    high:    { label:'높은 일치율',     dot:'#5EEAD4', text:'text-mint',   bg:'rgba(94,234,212,0.10)', border:'rgba(94,234,212,0.35)' },
    similar: { label:'비슷한 곡 발견',   dot:'#FFB07A', text:'text-orange-soft', bg:'rgba(255,176,122,0.10)', border:'rgba(255,176,122,0.35)' },
    live:    { label:'라이브 버전 가능성', dot:'#F1C40F', text:'text-yellow-300', bg:'rgba(241,196,15,0.10)', border:'rgba(241,196,15,0.30)' },
    alt:     { label:'다른 버전 추천',   dot:'#A78BFA', text:'text-violet-300', bg:'rgba(167,139,250,0.10)', border:'rgba(167,139,250,0.30)' },
  };
  const m = map[level] || map.high;
  return (
    <span
      className="inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full text-[11px] font-medium"
      style={{ background: m.bg, border: `1px solid ${m.border}`, color: m.dot }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.dot, boxShadow: `0 0 8px ${m.dot}` }}/>
      {m.label}
    </span>
  );
}

// ───────────────────────── Vinyl record ─────────────────────────
function Vinyl({ size=180, label='preview', sublabel='', spinning=true }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <div
        className={`absolute inset-0 rounded-full ${spinning ? 'ob-spin' : ''}`}
        style={{
          background: 'radial-gradient(circle, #1a1a1a 0%, #050505 70%)',
          boxShadow: '0 30px 60px -20px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.06)',
        }}
      >
        {/* grooves */}
        {[0.85,0.7,0.55,0.42,0.3].map((s,i)=>(
          <div key={i} className="absolute inset-0 rounded-full" style={{
            transform: `scale(${s})`, border:'1px solid rgba(255,255,255,0.04)'
          }}/>
        ))}
        {/* label */}
        <div className="absolute inset-0 m-auto rounded-full flex flex-col items-center justify-center text-center" style={{
          width:'38%', height:'38%',
          background: 'linear-gradient(135deg, #FD6D11 0%, #C24A00 100%)',
          color:'white',
        }}>
          <span className="text-[10px] uppercase tracking-[0.2em] opacity-80">orangebeats</span>
          <span className="text-[11px] font-semibold mt-0.5 leading-tight px-2">{label}</span>
          {sublabel && <span className="text-[9px] opacity-70 mt-0.5">{sublabel}</span>}
          <span className="w-2 h-2 rounded-full bg-black/80 mt-1.5"/>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── Footer ─────────────────────────
function Footer() {
  return (
    <footer className="border-t border-white/5 mt-32">
      <div className="mx-auto max-w-[1280px] px-8 py-14 grid grid-cols-12 gap-8">
        <div className="col-span-5">
          <BrandMark/>
          <p className="mt-4 text-white/50 text-[14px] leading-relaxed max-w-sm">
            Youtube 플레이리스트를 한 번에 Spotify로. 음악을 옮기는 가장 부드러운 방법.
          </p>
          <p className="mt-6 text-white/30 text-[12px] font-mono">© 2026 ORANGEBEATS — paran studio</p>
        </div>
        <div className="col-span-7 grid grid-cols-3 gap-8 text-[13px]">
          {[
            ['Product', ['Convert','Pricing','Changelog','Roadmap']],
            ['Resources', ['FAQ','How to use','API','Status']],
            ['Company', ['About','Privacy','Terms','Contact']],
          ].map(([h, items]) => (
            <div key={h}>
              <div className="text-white/40 uppercase tracking-[0.18em] text-[11px] mb-4">{h}</div>
              <ul className="space-y-2.5">
                {items.map(i => <li key={i}><a className="text-white/70 hover:text-white" href="#">{i}</a></li>)}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}

// ───────────────────────── Section header ─────────────────────────
function Eyebrow({ children, color='#FD6D11' }) {
  return (
    <div className="inline-flex items-center gap-2 ob-chip rounded-full px-3 py-1.5 text-[11px] font-mono tracking-[0.18em] uppercase text-white/70">
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow:`0 0 8px ${color}` }}/>
      {children}
    </div>
  );
}

Object.assign(window, {
  IconYT, IconSpotify, IconArrow, IconCheck, IconSparkle, IconPlay, IconRefresh, IconClose, IconChevron, IconExternal, IconHeart, IconScan, IconMic,
  BrandMark, NavBar, TrackCover, EqualiserBars, ConfidencePill, Vinyl, Footer, Eyebrow,
});
