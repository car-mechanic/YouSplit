import { Link, Route, Routes, useMatch } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import Home from "./pages/Home";
import ListView from "./pages/ListView";
import ThemeToggle from "./components/ThemeToggle";

function App() {
  // The back link only makes sense inside a list
  const inList = useMatch("/list/:id") !== null;

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-4 pt-2">
        {inList ? (
          <Link
            to="/"
            className="inline-flex items-center gap-1 rounded-full px-2 py-2 text-sm text-gray-500 transition hover:bg-gray-200 hover:text-gray-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Übersicht
          </Link>
        ) : (
          <span />
        )}
        <ThemeToggle />
      </div>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/list/:id" element={<ListView />} />
      </Routes>
    </div>
  );
}

export default App;
