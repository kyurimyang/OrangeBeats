import { useEffect, useRef, useState } from "react";

function estimateCreateDurationMs(trackCount) {
  const n = Math.max(1, Number(trackCount) || 1);
  const batchBonus = Math.max(0, Math.floor((n - 1) / 100)) * 800;
  return Math.min(15000, Math.max(6000, 8000 + batchBonus));
}

export function usePlaylistCreateProgress(active, trackCount) {
  const [percent, setPercent] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const percentRef = useRef(0);
  const tickIdRef = useRef(null);

  useEffect(() => {
    if (!active) {
      setPercent(0);
      percentRef.current = 0;
      setSecondsLeft(0);
      return undefined;
    }

    const totalMs = estimateCreateDurationMs(trackCount);
    const startedAt = Date.now();

    const tick = () => {
      const elapsed = Date.now() - startedAt;
      const ratio = Math.min(0.98, elapsed / totalMs);
      const next = Math.round(ratio * 100);
      percentRef.current = next;
      setPercent(next);
      setSecondsLeft(Math.max(0, Math.ceil((totalMs - elapsed) / 1000)));
    };

    tick();
    const id = window.setInterval(tick, 90);
    tickIdRef.current = id;
    return () => {
      window.clearInterval(id);
      tickIdRef.current = null;
    };
  }, [active, trackCount]);

  const finish = () => {
    // tick 인터벌 먼저 중단 — finish 애니메이션과 충돌 방지
    if (tickIdRef.current != null) {
      window.clearInterval(tickIdRef.current);
      tickIdRef.current = null;
    }
    setSecondsLeft(0);
    const remaining = 100 - percentRef.current;
    if (remaining <= 0) return;
    // 남은 퍼센트를 ~500ms 안에 균등하게 채움
    const step = Math.max(2, Math.ceil(remaining / 16));
    const id = window.setInterval(() => {
      const next = Math.min(100, percentRef.current + step);
      percentRef.current = next;
      setPercent(next);
      if (next >= 100) window.clearInterval(id);
    }, 30);
  };

  return { percent, secondsLeft, finish };
}

export default function PlaylistCreateLoading({ percent, secondsLeft, playlistTitle = "" }) {
  const ariaName = String(playlistTitle || "").trim();

  return (
    <main
      className="playlist-create-loading"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={
        ariaName ? `Spotify 플레이리스트 생성 중: ${ariaName}` : "Spotify 플레이리스트 생성 중"
      }
    >
      <div className="playlist-create-loading__stage">
        <div className="playlist-create-loading__vinyl-scene">
          <div className="playlist-create-loading__glow" aria-hidden="true" />
          <div className="playlist-create-loading__glow playlist-create-loading__glow--secondary" aria-hidden="true" />
          <div className="playlist-create-loading__disc-3d">
            <div className="playlist-create-loading__vinyl" aria-hidden="true">
              <div className="playlist-create-loading__grooves" />
              <div className="playlist-create-loading__runout" aria-hidden="true" />
              <div className="playlist-create-loading__reflection" aria-hidden="true" />
              <div
                className="playlist-create-loading__reflection playlist-create-loading__reflection--alt"
                aria-hidden="true"
              />
              <div className="playlist-create-loading__label">
                <div className="playlist-create-loading__spindle" aria-hidden="true" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <footer className="playlist-create-loading__footer">
        <div className="playlist-create-loading__meta">
          <span className="playlist-create-loading__percent">{percent}%</span>
          <span className="playlist-create-loading__eta">~ {secondsLeft}S 남음</span>
        </div>
        <div
          className="playlist-create-loading__bar-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <div
            className="playlist-create-loading__bar-fill"
            style={{ width: `${percent}%` }}
          />
        </div>
      </footer>
    </main>
  );
}
