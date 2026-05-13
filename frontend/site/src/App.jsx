import { Route, Routes } from "react-router-dom";
import ContactPage from "./pages/ContactPage.jsx";
import FaqPage from "./pages/FaqPage.jsx";
import HelpPage from "./pages/HelpPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import PlaylistUrlPage from "./pages/PlaylistUrlPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/create" element={<PlaylistUrlPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/faq" element={<FaqPage />} />
      <Route path="/contact" element={<ContactPage />} />
    </Routes>
  );
}
