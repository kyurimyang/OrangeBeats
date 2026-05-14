// Root app — routes between screens, manages global tweaks
const { useState, useEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#FD6D11",
  "secondary": "#5EEAD4",
  "showACRPanel": false,
  "showTweaks": false
}/*EDITMODE-END*/;

function ScreenLabel({ id, children }) {
  return <div data-screen-label={id} className="contents">{children}</div>;
}

function App() {
  const [route, setRoute] = useState('landing');
  const [routeState, setRouteState] = useState({});
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [tweaksOpen, setTweaksOpen] = useState(false);

  // Tweaks protocol
  useEffect(()=>{
    const handler = (e)=>{
      const msg = e.data;
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === '__activate_edit_mode') setTweaksOpen(true);
      if (msg.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', handler);
    window.parent.postMessage({ type:'__edit_mode_available' }, '*');
    return ()=> window.removeEventListener('message', handler);
  }, []);

  const setTweak = (k, v) => {
    setTweaks(prev => {
      const next = typeof k === 'object' ? { ...prev, ...k } : { ...prev, [k]: v };
      window.parent.postMessage({ type:'__edit_mode_set_keys', edits: next }, '*');
      return next;
    });
  };

  // Sync accent CSS var with tweak value
  useEffect(()=>{
    document.documentElement.style.setProperty('--ob-orange', tweaks.accent);
    document.documentElement.style.setProperty('--ob-mint',   tweaks.secondary);
  }, [tweaks.accent, tweaks.secondary]);

  const navigate = (id, state) => {
    setRoute(id);
    setRouteState(state || {});
    if (typeof window.scrollTo === 'function') window.scrollTo({ top: 0, behavior:'instant' });
  };

  const screens = {
    landing:    () => <LandingScreen onNavigate={navigate} tweaks={tweaks}/>,
    url:        () => <URLScreen onNavigate={navigate} initialUrl={routeState.initialUrl || ''}/>,
    loading:    () => <LoadingScreen onNavigate={navigate} url={routeState.url} title={routeState.title}/>,
    candidates: () => <CandidatesScreen onNavigate={navigate}/>,
    playlist:   () => <PlaylistScreen onNavigate={navigate}/>,
    faq:        () => <FaqScreen onNavigate={navigate}/>,
    pricing:    () => <PricingScreen onNavigate={navigate}/>,
  };

  const Screen = screens[route] || screens.landing;

  const screenLabels = {
    landing: '01 Landing', url: '02 URL Input', loading: '03 Analyzing',
    candidates: '04 Candidates', playlist: '05 Playlist Created',
    faq: '06 FAQ', pricing: '07 Pricing',
  };

  return (
    <div className="min-h-screen">
      <NavBar route={route} onNavigate={navigate} accentColor={tweaks.accent}/>
      <div data-screen-label={screenLabels[route]} key={route}>
        <Screen/>
      </div>
      {tweaksOpen && <TweaksPanel tweaks={tweaks} setTweak={setTweak} route={route} navigate={navigate}/>}
      <DemoNavDots route={route} navigate={navigate}/>
    </div>
  );
}

function DemoNavDots({ route, navigate }) {
  const flow = ['landing','url','loading','candidates','playlist'];
  const idx = flow.indexOf(route);
  if (idx === -1) return null;
  return (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-5 z-40 ob-glass rounded-full px-2 py-2 flex items-center gap-1 backdrop-blur-md">
      <span className="px-3 text-[10px] font-mono uppercase tracking-[0.18em] text-white/40">demo flow</span>
      {flow.map((r, i)=>(
        <button
          key={r}
          onClick={()=>navigate(r)}
          className={`px-3 h-7 rounded-full text-[11px] font-medium transition ${
            i===idx ? 'bg-orange text-black' : 'text-white/60 hover:text-white hover:bg-white/[0.06]'
          }`}
        >
          {String(i+1).padStart(2,'0')} {r}
        </button>
      ))}
    </div>
  );
}

function TweaksPanel({ tweaks, setTweak, route, navigate }) {
  return (
    <div className="fixed right-5 top-[88px] z-50 w-[300px] ob-glass rounded-2xl p-5 shadow-2xl ob-fade">
      <div className="flex items-center justify-between mb-4">
        <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/60">Tweaks</div>
        <button onClick={()=>window.parent.postMessage({ type:'__edit_mode_dismissed' }, '*')}
                className="w-7 h-7 rounded-full hover:bg-white/10 flex items-center justify-center text-white/50 hover:text-white">
          <IconClose size={14}/>
        </button>
      </div>

      <div className="text-[11px] font-mono text-white/40 mb-2">SCREEN</div>
      <div className="grid grid-cols-2 gap-1.5 mb-5">
        {['landing','url','loading','candidates','playlist','faq','pricing'].map(r=>(
          <button key={r} onClick={()=>navigate(r)}
            className={`h-8 rounded-md text-[11px] ${route===r?'bg-orange text-black font-semibold':'bg-white/5 text-white/70 hover:bg-white/10'}`}>
            {r}
          </button>
        ))}
      </div>

      <div className="text-[11px] font-mono text-white/40 mb-2">PRIMARY ACCENT</div>
      <div className="flex items-center gap-2 mb-4">
        {['#FD6D11','#FF3D7F','#A78BFA','#5EEAD4','#F1C40F'].map(c=>(
          <button key={c} onClick={()=>setTweak('accent', c)}
            className={`w-8 h-8 rounded-full border-2 ${tweaks.accent===c?'border-white':'border-white/10'}`}
            style={{ background:c }}/>
        ))}
      </div>

      <div className="text-[11px] font-mono text-white/40 mb-2">SECONDARY ACCENT</div>
      <div className="flex items-center gap-2">
        {['#5EEAD4','#A6F2E5','#FFB07A','#A78BFA','#FFFFFF'].map(c=>(
          <button key={c} onClick={()=>setTweak('secondary', c)}
            className={`w-8 h-8 rounded-full border-2 ${tweaks.secondary===c?'border-white':'border-white/10'}`}
            style={{ background:c }}/>
        ))}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
