import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import SpotifyShortcutLink from "../components/SpotifyShortcutLink.jsx";

const CREATED_PLAYLIST_KEY = "orangebeats.createdPlaylist";

function readCreatedBundle(locationState) {
  const fromState = locationState?.createdPlaylist;
  if (fromState && typeof fromState === "object") {
    return fromState;
  }
  try {
    const raw = sessionStorage.getItem(CREATED_PLAYLIST_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export default function PlaylistCreatedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [bundle] = useState(() => readCreatedBundle(location.state));

  const tracks = useMemo(
    () => (Array.isArray(bundle?.tracks) ? bundle.tracks : []),
    [bundle],
  );
  const playlistUrl = String(bundle?.playlistUrl || "").trim();

  useEffect(() => {
    if (!playlistUrl) {
      navigate("/result", { replace: true });
    }
  }, [playlistUrl, navigate]);

  if (!playlistUrl) {
    return null;
  }

  return (
    <div className="result-list-page playlist-created-page" data-node-id="328:249">
      <SiteHeader />
      <main className="result-list-page__main playlist-created-page__main">
        <p className="result-list-page__heading playlist-created-page__heading" data-node-id="164:1841">
          Spotify에 Playlist를 생성했어요!
        </p>

        <section className="result-list-panel playlist-created-page__panel" aria-label="생성된 플레이리스트">
          {tracks.map((track, index) => (
            <article
              key={track.id || `${index}`}
              className={`result-track-item result-track-item--readonly${
                track.confidenceLabel === "low" ? " result-track-item--low-confidence" : ""
              }`}
            >
              <span className="result-track-item__index">{index + 1}</span>
              {track.cover ? (
                <img
                  className="result-track-item__cover"
                  src={track.cover}
                  alt=""
                  loading="lazy"
                />
              ) : (
                <div className="result-track-item__cover result-track-item__cover--placeholder" />
              )}
              <div className="result-track-item__meta">
                <p className="result-track-item__title">{track.title}</p>
                <p className="result-track-item__artist">{track.artist}</p>
              </div>
            </article>
          ))}
        </section>

        <SpotifyShortcutLink
          url={playlistUrl}
          className="playlist-created-page__shortcut"
          onAfterOpen={() =>
            navigate("/result/rating", {
              state: {
                playlistUrl,
                playlistName: String(bundle?.playlistName || "").trim(),
              },
            })
          }
        />
      </main>
    </div>
  );
}
