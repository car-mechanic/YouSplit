import { Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import ListView from "./pages/ListView";
import ThemeToggle from "./components/ThemeToggle";

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto flex max-w-2xl px-4 pt-2">
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
