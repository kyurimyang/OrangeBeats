import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SPOTIFY_CONNECT_REDIRECT_PATH } from "../utils/spotifyAuth.js";

/** Figma 001_home hero — 가운데 오렌지 CTA → 002_URL(/create) */
export default function HomeHeroSpotify() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState("default");

  const phaseClass =
    phase === "hover"
      ? "figma-spotify-connect--hover"
      : phase === "pressed"
        ? "figma-spotify-connect--pressed"
        : "figma-spotify-connect--default";

  const handleAnalyze = () => {
    navigate(SPOTIFY_CONNECT_REDIRECT_PATH);
  };

  return (
    <div className="home-hero__cta" data-node-id="99:284-cta">
      <button
        type="button"
        className={`figma-piece figma-spotify-connect ${phaseClass}`}
        data-node-id="97:157"
        onMouseEnter={() => setPhase("hover")}
        onMouseLeave={() => setPhase("default")}
        onMouseDown={() => setPhase("pressed")}
        onMouseUp={() => setPhase("hover")}
        onBlur={() => setPhase("default")}
        onClick={handleAnalyze}
      >
        <span className="figma-piece__label figma-spotify-connect__label">Youtube 분석하기</span>
      </button>
    </div>
  );
}
