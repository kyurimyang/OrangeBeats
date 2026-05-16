import { Route, Routes } from "react-router-dom";
import ContactPage from "./pages/ContactPage.jsx";
import FaqPage from "./pages/FaqPage.jsx";
import HelpPage from "./pages/HelpPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import PlaylistUrlPage from "./pages/PlaylistUrlPage.jsx";
import ResultListPage from "./pages/ResultListPage.jsx";
import ResultAnalysisModesPage from "./pages/ResultAnalysisModesPage.jsx";
import PlaylistCreatedPage from "./pages/PlaylistCreatedPage.jsx";
import RatingPage from "./pages/RatingPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/create" element={<PlaylistUrlPage />} />
      <Route path="/result/analysis" element={<ResultAnalysisModesPage />} />
      <Route path="/result" element={<ResultListPage />} />
      <Route path="/result/created" element={<PlaylistCreatedPage />} />
      <Route path="/result/rating" element={<RatingPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/faq" element={<FaqPage />} />
      <Route path="/contact" element={<ContactPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
