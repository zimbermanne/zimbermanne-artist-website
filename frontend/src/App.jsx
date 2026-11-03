import React, { useEffect, useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { getMusic, getSite, registerVisit } from "./api";
import { AuthProvider } from "./auth";
import { Footer, Nav } from "./components";
import { AdminLayout, Account, Catalog, Dashboard, Fans, Inbox, Login } from "./admin";
import { Home, NotFound, SongPage, UnsubscribePage } from "./pages";
import { LyricsModal, PlayerBar, PlayerProvider } from "./player";

function ScrollManager() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    const el = hash ? document.getElementById(hash.slice(1)) : null;
    if (el) el.scrollIntoView(); else window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

function PublicSite({ albums, site }) {
  const { pathname } = useLocation();
  const home = pathname === "/";
  return (
    <>
      <Nav home={home} views={site.views} />
      <Outlet />
      <Footer views={home ? site.views : null} />
      <PlayerBar />
      <LyricsModal />
    </>
  );
}

export default function App() {
  const [albums, setAlbums] = useState([]);
  const [failed, setFailed] = useState(false);
  const [site, setSite] = useState({ whatsappUrl: null, views: null });

  useEffect(() => {
    getMusic().then(setAlbums).catch(() => setFailed(true));
    getSite().then((s) => setSite((p) => ({ whatsappUrl: s.whatsappUrl, views: p.views ?? s.views }))).catch(() => {});
    registerVisit().then((v) => setSite((p) => ({ ...p, views: v.views }))).catch(() => {});
  }, []);

  return (
    <AuthProvider>
      <PlayerProvider albums={albums}>
        <ScrollManager />
        <Routes>
          <Route element={<PublicSite albums={albums} site={site} />}>
            <Route index element={<Home albums={albums} failed={failed} whatsappUrl={site.whatsappUrl} />} />
            <Route path="song/:slug" element={<SongPage />} />
            <Route path="unsubscribe/:token" element={<UnsubscribePage />} />
            <Route path="*" element={<NotFound />} />
          </Route>

          <Route path="admin/login" element={<Login />} />
          <Route path="admin" element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="catalog" element={<Catalog />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="fans" element={<Fans />} />
            <Route path="account" element={<Account />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Route>
        </Routes>
      </PlayerProvider>
    </AuthProvider>
  );
}
