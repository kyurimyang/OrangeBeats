import { BrandMark } from './brand-mark';

const LINKS: [string, string[]][] = [
  ['Product',   ['Convert', 'Pricing', 'Changelog', 'Roadmap']],
  ['Resources', ['FAQ', 'How to use', 'API', 'Status']],
  ['Company',   ['About', 'Privacy', 'Terms', 'Contact']],
];

export function Footer() {
  return (
    <footer className="border-t border-white/5 mt-32">
      <div className="mx-auto max-w-[1280px] px-8 py-14 grid grid-cols-12 gap-8">
        <div className="col-span-5">
          <BrandMark />
          <p className="mt-4 text-white/50 text-[14px] leading-relaxed max-w-sm">
            Youtube 플레이리스트를 한 번에 Spotify로. 음악을 옮기는 가장 부드러운 방법.
          </p>
          <p className="mt-6 text-white/30 text-[12px] font-mono">
            © 2026 ORANGEBEATS — paran studio
          </p>
        </div>
        <div className="col-span-7 grid grid-cols-3 gap-8 text-[13px]">
          {LINKS.map(([heading, items]) => (
            <div key={heading}>
              <div className="text-white/40 uppercase tracking-[0.18em] text-[11px] mb-4">{heading}</div>
              <ul className="space-y-2.5">
                {items.map((item) => (
                  <li key={item}>
                    <a className="text-white/70 hover:text-white transition-colors" href="#">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}
