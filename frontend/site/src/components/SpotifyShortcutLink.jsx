import { useState } from "react";

/** Figma `Spotify 바로가기` — figma-spotify-shortcut 컴포넌트 */
export default function SpotifyShortcutLink({ url, className = "", onAfterOpen }) {
  const [hovered, setHovered] = useState(false);
  const phaseClass = hovered ? "figma-spotify-shortcut--hover" : "figma-spotify-shortcut--default";

  const openSpotify = () => {
    const target = (url || "").trim();
    if (!target) return;
    window.open(target, "_blank", "noopener,noreferrer");
    onAfterOpen?.();
  };

  return (
    <button
      type="button"
      className={`figma-piece figma-spotify-shortcut ${phaseClass} ${className}`.trim()}
      onClick={openSpotify}
      disabled={!url}
      aria-label="Spotify에서 플레이리스트 열기"
      data-node-id="164:1843"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
    >
      Spotify 바로가기
    </button>
  );
}
