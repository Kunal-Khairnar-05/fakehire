import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Fonts are bundled with the app (no request to Google): faster, private, works offline.
// Poppins matches the logo's wordmark (headings); Inter is a clean, Apple-like text face.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
