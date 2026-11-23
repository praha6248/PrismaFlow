import "@fontsource/crimson-text/400.css";
import "@fontsource/montserrat/400.css";
import "@fontsource/montserrat/500.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

const THEMES = ["glass", "white"];
try {
  const asked = new URLSearchParams(window.location.search).get("theme");
  if (asked && THEMES.includes(asked)) localStorage.setItem("pf-theme", asked);
  const theme = localStorage.getItem("pf-theme");
  if (theme && THEMES.includes(theme)) document.documentElement.dataset.theme = theme;
} catch {
  document.documentElement.dataset.theme = "glass";
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
