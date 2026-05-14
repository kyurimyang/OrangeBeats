interface IconProps {
  size?: number;
  color?: string;
}

export function IconYT({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2.5" y="5.5" width="19" height="13" rx="3.5" />
      <path d="M10.5 9.5 L15 12 L10.5 14.5 Z" fill={color} stroke="none" />
    </svg>
  );
}

export function IconSpotify({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M6.5 9.5c3.5-1.2 7.5-1.2 11 .3" />
      <path d="M7 12.5c3-1 6.5-1 9.5.3" />
      <path d="M7.5 15.2c2.5-.8 5.4-.8 7.7.3" />
    </svg>
  );
}

interface IconArrowProps extends IconProps {
  dir?: 'right' | 'left' | 'down' | 'up';
}
export function IconArrow({ size = 18, color = 'currentColor', dir = 'right' }: IconArrowProps) {
  const rotate = dir === 'left' ? 'scaleX(-1)' : dir === 'down' ? 'rotate(90deg)' : dir === 'up' ? 'rotate(-90deg)' : 'none';
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ transform: rotate }}>
      <path d="M5 12h14" /><path d="M13 6l6 6-6 6" />
    </svg>
  );
}

export function IconCheck({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.5l4 4L19 7" />
    </svg>
  );
}

export function IconSparkle({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <path d="M12 2 L13.6 9.6 L21 11 L13.6 12.4 L12 20 L10.4 12.4 L3 11 L10.4 9.6 Z" />
    </svg>
  );
}

interface IconPlayProps extends IconProps {
  filled?: boolean;
}
export function IconPlay({ size = 18, color = 'currentColor', filled = true }: IconPlayProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? color : 'none'} stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round">
      <path d="M7 5 L19 12 L7 19 Z" />
    </svg>
  );
}

export function IconRefresh({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}

export function IconClose({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round">
      <path d="M6 6 L18 18 M18 6 L6 18" />
    </svg>
  );
}

interface IconChevronProps extends IconProps {
  dir?: 'down' | 'up' | 'left' | 'right';
}
export function IconChevron({ size = 18, color = 'currentColor', dir = 'down' }: IconChevronProps) {
  const rotate = dir === 'up' ? 'rotate(180deg)' : dir === 'left' ? 'rotate(90deg)' : dir === 'right' ? 'rotate(-90deg)' : 'none';
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: rotate, transition: 'transform .2s' }}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function IconExternal({ size = 14, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 5h5v5" /><path d="M19 5L10 14" /><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" />
    </svg>
  );
}

interface IconHeartProps extends IconProps {
  filled?: boolean;
}
export function IconHeart({ size = 18, color = 'currentColor', filled = false }: IconHeartProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? color : 'none'} stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 21s-7-4.5-9.3-9.3C1 8 3.5 4.5 7 4.5c2 0 3.6 1.1 5 3 1.4-1.9 3-3 5-3 3.5 0 6 3.5 4.3 7.2C19 16.5 12 21 12 21z" />
    </svg>
  );
}

export function IconScan({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8V5a2 2 0 0 1 2-2h3" /><path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" /><path d="M21 16v3a2 2 0 0 1-2 2h-3" />
      <path d="M7 12h10" />
    </svg>
  );
}

export function IconMic({ size = 18, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" />
    </svg>
  );
}

export function IconStar({ active }: { active: boolean }) {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill={active ? '#FD6D11' : 'none'} stroke={active ? '#FD6D11' : 'rgba(255,255,255,0.3)'} strokeWidth="1.5" strokeLinejoin="round">
      <path d="M12 2 L14.6 9.5 L22 9.8 L16.2 14.4 L18.4 21.5 L12 17.3 L5.6 21.5 L7.8 14.4 L2 9.8 L9.4 9.5 Z" />
    </svg>
  );
}
