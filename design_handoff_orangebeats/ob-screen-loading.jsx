// Loading / analysis screen with progress stages
// Globals: LoadingScreen

const STAGES = [
  { key:'fetch',  label:'영상 정보 불러오는 중',  detail:'Youtube에서 메타데이터를 받아오고 있어요',     ms:1400 },
  { key:'trans',  label:'자막·설명 분석 중',     detail:'트랙리스트가 보일 만한 텍스트를 추리고 있어요', ms:1800 },
  { key:'match',  label:'곡 매칭 중',           detail:'후보 곡을 찾고 신뢰도를 평가하고 있어요',      ms:2200 },
  { key:'tidy',   label:'결과 정리 중',         detail:'중복을 정리하고 순서를 맞추고 있어요',         ms:1200 },
];

function LoadingScreen({ onNavigate, url, title }) {
  const [stageIdx, setStageIdx] = React.useState(0);
  const [pct, setPct] = React.useState(0);
  const totalMs = STAGES.reduce((s,x)=>s+x.ms, 0);

  React.useEffect(()=>{
    let cancel = false;
    let acc = 0;
    let lastTime = performance.now();
    function tick(now) {
      if (cancel) return;
      const dt = now - lastTime;
      lastTime = now;
      acc += dt;
      const p = Math.min(1, acc / totalMs);
      setPct(p);

      let cumulative = 0;
      for (let i=0; i<STAGES.length; i++) {
        cumulative += STAGES[i].ms;
        if (acc < cumulative) { setStageIdx(i); break; }
      }

      if (acc >= totalMs) {
        setTimeout(()=>onNavigate('candidates'), 350);
        return;
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    return ()=>{ cancel = true; };
  }, []);

  return (
    <div className="ob-fade min-h-screen pt-[68px] flex items-center">
      {/* glow */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[800px] rounded-full"
             style={{ background:'radial-gradient(closest-side, rgba(253,109,17,0.30), transparent 70%)' }}/>
      </div>

      <div className="mx-auto w-full max-w-[1080px] px-8">
        <div className="text-center">
          <Eyebrow color="#FD6D11">Analyzing… please hold</Eyebrow>
          <h1 className="mt-7 font-display text-[44px] md:text-[52px] tracking-[-0.03em] leading-[1.05] font-medium">
            <span className="ob-grad-accent">Youtube에서 음원</span><br/>
            <span className="text-white/85">가져오는 중<DotsAnim/></span>
          </h1>
          <p className="mt-4 text-white/55 text-[14px]">
            {STAGES[stageIdx].detail}
          </p>
        </div>

        {/* big vinyl */}
        <div className="mt-12 flex items-center justify-center">
          <div className="relative">
            <Vinyl size={260} label="late-summer mix" sublabel="orangebeats · scanning"/>
            <div className="absolute inset-0 -m-6 rounded-full pointer-events-none animate-pulse"
                 style={{ boxShadow:'0 0 80px 20px rgba(253,109,17,0.3)' }}/>
          </div>
        </div>

        {/* progress */}
        <div className="mt-14 max-w-[720px] mx-auto">
          <div className="flex items-center justify-between mb-3 text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">
            <span>{Math.round(pct*100)}%</span>
            <span>~{Math.max(0, Math.ceil((totalMs - pct*totalMs)/1000))}s 남음</span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden relative">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-300"
              style={{
                width:`${pct*100}%`,
                background:'linear-gradient(90deg, #FD6D11 0%, #FFB07A 70%, #5EEAD4 100%)',
                boxShadow:'0 0 16px rgba(253,109,17,0.5)',
              }}
            />
            <div className="absolute inset-0 ob-shimmer rounded-full opacity-40"/>
          </div>
        </div>

        {/* stage list */}
        <div className="mt-10 max-w-[720px] mx-auto grid grid-cols-4 gap-3">
          {STAGES.map((s, i)=>{
            const done = i < stageIdx;
            const active = i === stageIdx;
            return (
              <div key={s.key}
                className={`rounded-xl p-3 transition border ${active ? 'border-orange/40 bg-orange/[0.06]' :
                                                       done ? 'border-mint/30 bg-mint/[0.04]' :
                                                              'border-white/[0.06] bg-white/[0.02]'}`}>
                <div className="flex items-center gap-2">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono
                                   ${done ? 'bg-mint text-black' : active ? 'bg-orange text-black' : 'bg-white/10 text-white/40'}`}>
                    {done ? <IconCheck size={12} color="black"/> : i+1}
                  </div>
                  <span className={`text-[11px] font-mono uppercase tracking-[0.14em] ${active?'text-orange':done?'text-mint':'text-white/40'}`}>
                    {s.key}
                  </span>
                </div>
                <div className={`mt-2 text-[12px] leading-tight ${active||done?'text-white/85':'text-white/40'}`}>
                  {s.label}
                </div>
              </div>
            );
          })}
        </div>

        {/* tip */}
        <div className="mt-10 max-w-[720px] mx-auto ob-glass-soft rounded-2xl px-5 py-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl ob-chip flex items-center justify-center shrink-0">
            <IconSparkle size={18} color="#FFB07A"/>
          </div>
          <div className="flex-1">
            <div className="text-[12px] font-mono uppercase tracking-[0.15em] text-white/40">DID YOU KNOW</div>
            <div className="mt-1 text-[13px] text-white/80">
              한 곡당 평균 12개의 후보 중에서 가장 일치율 높은 곡을 골라요. 라이브 버전·리믹스도 자동으로 구분돼요.
            </div>
          </div>
          <button onClick={()=>onNavigate('url')} className="text-[12px] text-white/50 hover:text-white">
            취소
          </button>
        </div>
      </div>
    </div>
  );
}

function DotsAnim() {
  const [n, setN] = React.useState(0);
  React.useEffect(()=>{
    const t = setInterval(()=>setN(x=>(x+1)%4), 400);
    return ()=>clearInterval(t);
  }, []);
  return <span className="inline-block w-8 text-left text-orange">{'.'.repeat(n)}</span>;
}

Object.assign(window, { LoadingScreen });
