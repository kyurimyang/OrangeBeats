import { useEffect, useState } from "react";

function estimateCreateDurationMs(trackCount) {
  const n = Math.max(1, Number(trackCount) || 1);
  return Math.min(16000, Math.max(4500, 2800 + n * 550));
}

export function usePlaylistCreateProgress(active, trackCount) {
  const [percent, setPercent] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    if (!active) {
      setPercent(0);
      setSecondsLeft(0);
      return undefined;
    }

    const totalMs = estimateCreateDurationMs(trackCount);
    const startedAt = Date.now();

    const tick = () => {
      const elapsed = Date.now() - startedAt;
      const ratio = Math.min(0.92, elapsed / totalMs);
      setPercent(Math.round(ratio * 100));
      setSecondsLeft(Math.max(0, Math.ceil((totalMs - elapsed) / 1000)));
    };

    tick();
    const id = window.setInterval(tick, 90);
    return () => window.clearInterval(id);
  }, [active, trackCount]);

  const finish = () => {
    setPercent(100);
    setSecondsLeft(0);
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
              <div className="playlist-create-loading__rim" aria-hidden="true" />
              <div className="playlist-create-loading__grooves" />
              <div className="playlist-create-loading__shine" aria-hidden="true" />
              <div className="playlist-create-loading__label">
                <div className="playlist-create-loading__label-gloss" aria-hidden="true" />
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
