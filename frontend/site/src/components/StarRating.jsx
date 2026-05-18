import { useState } from "react";

const STAR_NO_URL = "/assets/home/star-no.svg";
const STAR_YES_URL = "/assets/home/star-yes.svg";

export default function StarRating({ value = 0, disabled = false, onSelect }) {
  const [hovered, setHovered] = useState(0);
  const display = hovered || value;

  return (
    <div
      className="star-rating"
      role="radiogroup"
      aria-label="서비스 만족도 별점"
      onMouseLeave={() => setHovered(0)}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const filled = star <= display;
        return (
          <button
            key={star}
            type="button"
            className={`figma-piece figma-star figma-star--${filled ? "yes" : "no"} star-rating__star`}
            disabled={disabled}
            role="radio"
            aria-checked={value === star}
            aria-label={`${star}점`}
            onMouseEnter={() => !disabled && setHovered(star)}
            onFocus={() => !disabled && setHovered(star)}
            onBlur={() => setHovered(0)}
            onClick={() => onSelect?.(star)}
          >
            <img
              className="figma-star__icon"
              src={filled ? STAR_YES_URL : STAR_NO_URL}
              alt=""
              aria-hidden="true"
            />
          </button>
        );
      })}
    </div>
  );
}
