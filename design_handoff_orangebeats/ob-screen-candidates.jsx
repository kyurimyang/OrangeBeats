// Candidate matching screen — review extracted tracks
// Globals: CandidatesScreen

function CandidatesScreen({ onNavigate }) {
  const [tracks, setTracks] = React.useState(DEMO_TRACKS.map(t => ({...t, kept:true})));
  const [expanded, setExpanded] = React.useState(null); // track id with open alternates
  const [showACR, setShowACR] = React.useState(false);

  const kept = tracks.filter(t=>t.kept).length;
  const highConf = tracks.filter(t=>t.kept && t.conf==='high').length;
  const totalDuration = tracks.filter(t=>t.kept).reduce((s,t)=>{
    const [m,sec] = t.duration.split(':').map(Number);
    return s + m*60 + sec;
  },0);
  const dur = `${Math.floor(totalDuration/60)}분 ${totalDuration%60}초`;

  return (
    <div className="ob-fade min-h-screen pt-[68px] pb-24">
      <div className="mx-auto max-w-[1280px] px-8">
        {/* breadcrumb */}
        <div className="flex items-center gap-2 mt-8 text-[12px] text-white/40 font-mono uppercase tracking-[0.15em]">
          <button onClick={()=>onNavigate('landing')} className="hover:text-white">orangebeats</button>
          <span>/</span>
          <button onClick={()=>onNavigate('url')} className="hover:text-white">URL</button>
          <span>/</span>
          <span className="text-white">candidate matching</span>
        </div>

        {/* header */}
        <div className="mt-6 grid grid-cols-12 gap-8 items-end">
          <div className="col-span-7">
            <Eyebrow color="#5EEAD4">step 02 / 03 · 8 tracks found</Eyebrow>
            <h1 className="mt-4 font-display text-[52px] tracking-[-0.03em] leading-[1.02] font-medium">
              <span className="ob-grad-text">Youtube에서</span><br/>
              음악을 가져왔어요.
            </h1>
            <p className="mt-4 text-white/55 text-[14px] max-w-md leading-relaxed">
              아래 트랙들이 영상에서 자동으로 추출된 결과예요. 신뢰도가 낮은 곡은 다른 후보로 바꾸거나 제거할 수 있어요.
            </p>
          </div>
          <div className="col-span-5">
            <div className="grid grid-cols-3 gap-3">
              <StatCard label="포함" value={`${kept}곡`} accent="#FD6D11"/>
              <StatCard label="높은 신뢰" value={`${highConf}곡`} accent="#5EEAD4"/>
              <StatCard label="총 길이" value={dur} muted/>
            </div>
          </div>
        </div>

        {/* video card */}
        <div className="mt-10 ob-glass rounded-2xl p-5 flex items-center gap-5">
          <div className="aspect-video w-[160px] rounded-xl overflow-hidden ob-cover relative shrink-0" style={{ '--c1':'#FD6D11', '--c2':'#A78BFA' }}>
            <div className="absolute inset-0 flex items-center justify-center">
              <IconYT size={28} color="white"/>
            </div>
            <div className="absolute bottom-1.5 right-1.5 font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/70">{DEMO_VIDEO.duration}</div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-white/40 font-mono uppercase tracking-[0.15em]">원본 영상</div>
            <div className="mt-1 text-[18px] font-medium tracking-tight line-clamp-1">{DEMO_VIDEO.title}</div>
            <div className="mt-1 text-[13px] text-white/55">{DEMO_VIDEO.channel}</div>
          </div>
          <div className="flex items-center gap-2">
            <button className="ob-btn-ghost h-10 px-4 rounded-full text-[13px] text-white/75 inline-flex items-center gap-1.5">
              <IconExternal size={12}/> Youtube에서 열기
            </button>
          </div>
        </div>

        {/* track list */}
        <div className="mt-6 ob-glass-soft rounded-2xl overflow-hidden">
          <div className="px-5 py-3 flex items-center text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 border-b border-white/5">
            <span className="w-10">#</span>
            <span className="flex-1">extracted ⟶ matched</span>
            <span className="w-32">match</span>
            <span className="w-20 text-right">length</span>
            <span className="w-24"/>
          </div>
          {tracks.map((t, i)=>(
            <CandidateRow
              key={t.id}
              track={t}
              expanded={expanded===t.id}
              onToggleExpand={()=>setExpanded(expanded===t.id ? null : t.id)}
              onToggleKeep={()=>setTracks(prev=>prev.map(x=>x.id===t.id ? {...x, kept:!x.kept} : x))}
              onPickAlt={(alt)=>{
                setTracks(prev=>prev.map(x=>x.id===t.id ? {...x, title:alt.title, artist:alt.artist, album:alt.album, duration:alt.duration, coverSeed:alt.coverSeed, conf:'high'} : x));
                setExpanded(null);
              }}
            />
          ))}
        </div>

        {/* footer actions */}
        <div className="mt-10 flex items-center justify-between gap-4">
          <button
            onClick={()=>setShowACR(true)}
            className="ob-btn-ghost h-12 px-5 rounded-full text-[14px] text-white/85 inline-flex items-center gap-2"
          >
            <IconScan size={16}/> 원하는 노래가 없어요
            <span className="text-white/40 text-[12px] ml-1">OCR · ACR로 다시 시도</span>
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={()=>onNavigate('url')}
              className="text-white/60 hover:text-white text-[14px] h-12 px-5 inline-flex items-center"
            >
              다시 입력
            </button>
            <button
              onClick={()=>onNavigate('playlist')}
              className="ob-btn-primary h-12 px-7 rounded-full text-[14px] font-semibold inline-flex items-center gap-2"
            >
              이대로 Playlist 만들기 <IconArrow size={16} color="white"/>
            </button>
          </div>
        </div>
      </div>

      {showACR && <ACRModal onClose={()=>setShowACR(false)} onConfirm={()=>{ setShowACR(false); onNavigate('loading'); }}/>}
    </div>
  );
}

function StatCard({ label, value, accent, muted }) {
  return (
    <div className={`rounded-2xl p-4 border ${muted ? 'border-white/[0.06] bg-white/[0.02]' : 'ob-glass'}`}>
      <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40">{label}</div>
      <div className="mt-1.5 text-[24px] font-medium tracking-tight" style={{ color: accent || 'white' }}>{value}</div>
    </div>
  );
}

function CandidateRow({ track, expanded, onToggleExpand, onToggleKeep, onPickAlt }) {
  const alts = ALT_CANDIDATES[track.id] || [];
  return (
    <div className={`border-b border-white/5 transition ${track.kept?'':'opacity-40'}`}>
      <div className="px-5 py-3 flex items-center hover:bg-white/[0.02] group">
        <span className="w-10 text-[12px] font-mono text-white/40">{track.no}</span>
        <div className="flex-1 flex items-center gap-3 min-w-0">
          <TrackCover seed={track.coverSeed} size={48}/>
          <div className="min-w-0">
            <div className="text-[14px] text-white truncate">{track.title}</div>
            <div className="text-[12px] text-white/45 truncate">
              <span className="text-white/30 italic mr-1.5">from</span>
              {track.extracted}
            </div>
          </div>
        </div>
        <div className="w-32 pr-4">
          <ConfidencePill level={track.conf}/>
          <div className="mt-1.5 ob-meter">
            <span style={{ width: track.conf==='high'?'92%':track.conf==='similar'?'74%':track.conf==='live'?'66%':'48%' }}/>
          </div>
        </div>
        <span className="w-20 text-right text-[12px] font-mono text-white/50">{track.duration}</span>
        <div className="w-24 flex items-center justify-end gap-1">
          {alts.length > 0 && (
            <button
              onClick={onToggleExpand}
              className={`w-9 h-9 rounded-full flex items-center justify-center transition ${expanded?'bg-orange/15 text-orange':'hover:bg-white/10 text-white/60'}`}
              title="다른 버전 보기"
            >
              <IconChevron size={14} dir={expanded?'up':'down'}/>
            </button>
          )}
          <button
            onClick={onToggleKeep}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition ${track.kept?'hover:bg-white/10 text-white/60':'bg-white/10 text-white'}`}
            title={track.kept?'제외':'다시 포함'}
          >
            {track.kept ? <IconClose size={14}/> : <IconRefresh size={14}/>}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-5 pb-5 pt-1 bg-white/[0.02]">
          <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mb-3 pl-[52px]">
            다른 후보 · {alts.length}
          </div>
          <div className="grid grid-cols-2 gap-3 pl-[52px]">
            {alts.map((alt, ai)=>(
              <button
                key={ai}
                onClick={()=>onPickAlt(alt)}
                className="ob-glass-soft rounded-xl p-3 flex items-center gap-3 text-left hover:bg-white/[0.05] transition"
              >
                <TrackCover seed={alt.coverSeed} size={44}/>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] truncate">{alt.title}</div>
                  <div className="text-[11px] text-white/45 truncate">{alt.artist} · {alt.album}</div>
                </div>
                <div className="text-right">
                  <div className="text-[11px] font-mono text-mint">{alt.match}%</div>
                  <div className="text-[11px] font-mono text-white/40">{alt.duration}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ACRModal({ onClose, onConfirm }) {
  const [method, setMethod] = React.useState('ocr');
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center px-8 ob-fade">
      <div className="ob-glass rounded-3xl max-w-[680px] w-full p-8 relative">
        <button onClick={onClose} className="absolute top-5 right-5 w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white">
          <IconClose size={16}/>
        </button>

        <Eyebrow>fallback methods</Eyebrow>
        <h2 className="mt-4 font-display text-[32px] tracking-tight font-medium">
          영상에 더 어울리는 분석 방법을 골라주세요.
        </h2>
        <p className="mt-2 text-[13px] text-white/55 leading-relaxed">
          텍스트 기반 추출로 못 찾은 곡들을 한 번 더 시도해드려요. 영상 종류에 따라 더 정확한 방식이 달라요.
        </p>

        <div className="mt-7 grid grid-cols-2 gap-3">
          <MethodCard
            active={method==='ocr'}
            onClick={()=>setMethod('ocr')}
            label="OCR"
            sub="optical character recognition"
            desc="영상 속 자막·앨범 이미지에서 글자를 읽어 곡 정보를 찾아요."
            best="자막이 있는 라이브·라디오 영상에 좋아요"
            icon={<IconScan size={20} color="#FD6D11"/>}
          />
          <MethodCard
            active={method==='acr'}
            onClick={()=>setMethod('acr')}
            label="ACR"
            sub="audio content recognition"
            desc="실제 음원의 지문을 분석해 곡을 식별해요. 더 느리지만 정확해요."
            best="자막이 없는 모음집·믹스에 좋아요"
            icon={<IconMic size={20} color="#5EEAD4"/>}
          />
        </div>

        <div className="mt-8 flex items-center justify-between">
          <div className="text-[11px] font-mono text-white/40">
            예상 시간 · {method==='ocr'?'~18s':'~45s'}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="ob-btn-ghost h-11 px-5 rounded-full text-[13px] text-white/75">
              취소
            </button>
            <button onClick={onConfirm} className="ob-btn-primary h-11 px-6 rounded-full text-[13px] font-semibold inline-flex items-center gap-2">
              실행하기 <IconArrow size={14}/>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MethodCard({ active, onClick, label, sub, desc, best, icon }) {
  return (
    <button onClick={onClick}
      className={`text-left rounded-2xl p-5 border transition ${active ? 'border-orange/40 bg-orange/[0.04]' : 'border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04]'}`}>
      <div className="flex items-center justify-between">
        <div className="w-11 h-11 rounded-xl ob-chip flex items-center justify-center">{icon}</div>
        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center
                         ${active ? 'border-orange bg-orange' : 'border-white/30'}`}>
          {active && <IconCheck size={12} color="black"/>}
        </div>
      </div>
      <div className="mt-5">
        <div className="text-[20px] font-semibold tracking-tight">{label}</div>
        <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/40 mt-1">{sub}</div>
      </div>
      <div className="mt-4 text-[13px] text-white/65 leading-relaxed">{desc}</div>
      <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-mint font-mono">
        <span className="w-1 h-1 rounded-full bg-mint"/> {best}
      </div>
    </button>
  );
}

Object.assign(window, { CandidatesScreen });
