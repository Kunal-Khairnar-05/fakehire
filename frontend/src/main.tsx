import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Geist (Vercel's typeface) is bundled with the app: no request to a font CDN.
// Sans for text, Mono for scores, IDs, domains and timings.
import "@fontsource/geist-sans/400.css";
import "@fontsource/geist-sans/500.css";
import "@fontsource/geist-sans/600.css";
import "@fontsource/geist-mono/400.css";
import "@fontsource/geist-mono/500.css";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
