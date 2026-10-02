import { Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import ListView from "./pages/ListView";

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/list/:id" element={<ListView />} />
      </Routes>
    </div>
  );
}

export default App;
