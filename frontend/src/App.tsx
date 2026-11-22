import { useState } from "react";
import { Header } from "./components/Header";
import { DiscoverView } from "./discover/DiscoverView";

export function App() {
  const [resetSignal, setResetSignal] = useState(0);
  return (
    <div className="frame">
      <main className="card">
        <Header active={0} onHome={() => setResetSignal((n) => n + 1)} />
        <DiscoverView resetSignal={resetSignal} />
      </main>
    </div>
  );
}
