import { Navigate, Route, Routes } from "react-router-dom";
import { FileRail } from "./components/FileRail";
import { NotesPanel } from "./components/NotesPanel";
import { SetupGuide } from "./components/SetupGuide";
import { TopBar } from "./components/TopBar";
import { LayoutProvider, useLayout } from "./layout";
import { HomePage } from "./pages/HomePage";
import { ProjectPage } from "./pages/ProjectPage";
import { SearchPage } from "./pages/SearchPage";
import { UploadPage } from "./pages/UploadPage";

function Shell() {
  const { notesOpen, railOpen, closeRail } = useLayout();

  return (
    <div className={`app-shell${notesOpen ? " notes-on" : ""}${railOpen ? " rail-on" : ""}`}>
      <SetupGuide />
      <TopBar />
      <div className="app-body">
        <div className="notes-slot">
          <NotesPanel />
        </div>
        <div className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/projects/:id" element={<ProjectPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        <div className="rail-slot">
          <FileRail onClose={closeRail} />
        </div>
      </div>
    </div>
  );
}

export function App() {
  return (
    <LayoutProvider>
      <Shell />
    </LayoutProvider>
  );
}
