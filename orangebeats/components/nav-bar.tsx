'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BrandMark } from './brand-mark';
import { IconSpotify } from './icons';
import { checkLoginStatus, getSpotifyLoginUrl, logout } from '@/lib/api';

const NAV_LINKS = [
  { href: '/',        label: 'Home' },
  { href: '/url',     label: 'Convert' },
  { href: '/faq',     label: 'FAQ' },
  { href: '/pricing', label: 'Pricing' },
];

function getFrontendRedirectUrl(): string {
  const url = new URL(window.location.href);
  url.searchParams.delete('spotify_login');
  url.searchParams.delete('reason');
  return url.toString();
}

export function NavBar() {
  const pathname = usePathname();
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [loginNotice, setLoginNotice] = useState<'success' | 'failed' | null>(null);

  // Handle Spotify OAuth callback (?spotify_login=success/failed)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('spotify_login');
    if (status === 'success') {
      history.replaceState(null, '', window.location.pathname);
      setLoggedIn(true);
      setLoginNotice('success');
      setTimeout(() => setLoginNotice(null), 4000);
    } else if (status === 'failed') {
      history.replaceState(null, '', window.location.pathname);
      setLoginNotice('failed');
      setTimeout(() => setLoginNotice(null), 5000);
    }
  }, []);

  useEffect(() => {
    checkLoginStatus()
      .then((s) => setLoggedIn(s.logged_in))
      .catch(() => setLoggedIn(false));
  }, []);

  async function handleSpotifyLogin() {
    try {
      const { login_url } = await getSpotifyLoginUrl(getFrontendRedirectUrl());
      window.location.href = login_url;
    } catch {
      /* backend unreachable — ignore */
    }
  }

  async function handleLogout() {
    try {
      await logout();
      setLoggedIn(false);
    } catch {
      setLoggedIn(false);
    }
  }

  return (
    <>
    {loginNotice && (
      <div className={`fixed top-[68px] inset-x-0 z-40 flex justify-center pointer-events-none`}>
        <div className={`mt-3 px-5 py-3 rounded-full text-[13px] font-medium shadow-lg ${
          loginNotice === 'success'
            ? 'bg-mint/10 border border-mint/30 text-mint'
            : 'bg-red-500/10 border border-red-500/30 text-red-400'
        }`}>
          {loginNotice === 'success' ? 'Spotify 로그인 완료! 이제 플레이리스트를 만들 수 있어요.' : 'Spotify 로그인에 실패했어요. 다시 시도해주세요.'}
        </div>
      </div>
    )}
    <header className="ob-nav fixed top-0 inset-x-0 z-50 h-[68px] flex items-center">
      <div className="mx-auto w-full max-w-[1280px] px-8 flex items-center justify-between">
        <Link href="/" className="flex items-center">
          <BrandMark />
        </Link>

        <nav className="flex items-center gap-1">
          {NAV_LINKS.map((l) => {
            const active = pathname === l.href || (l.href !== '/' && pathname.startsWith(l.href));
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`px-3.5 py-2 rounded-full text-[14px] transition-colors ${
                  active ? 'text-white bg-white/[0.06]' : 'text-white/60 hover:text-white'
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          {loggedIn ? (
            <button
              onClick={handleLogout}
              className="ob-btn-ghost h-9 px-3.5 rounded-full text-[13px] text-white/80 hover:text-white inline-flex items-center gap-1.5"
            >
              로그아웃
            </button>
          ) : (
            <button
              onClick={handleSpotifyLogin}
              className="ob-btn-ghost h-9 px-3.5 rounded-full text-[13px] text-white/80 hover:text-white inline-flex items-center gap-1.5"
            >
              로그인
            </button>
          )}

          <button
            onClick={loggedIn ? () => {} : handleSpotifyLogin}
            className="h-9 pl-3 pr-4 rounded-full text-[13px] font-medium inline-flex items-center gap-2 text-black transition-opacity hover:opacity-90"
            style={{ background: 'linear-gradient(180deg, #fff, #d8d8d8)' }}
          >
            <IconSpotify size={14} color="#0a0a0a" />
            {loggedIn ? 'Spotify 연결됨' : 'Spotify 연동'}
          </button>
        </div>
      </div>
    </header>
    </>
  );
}
