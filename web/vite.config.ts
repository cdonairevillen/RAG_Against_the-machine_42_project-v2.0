import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages serves the site under /<repository>/; VITE_BASE sets it at
// build time (see .github/workflows/pages.yml). Local dev uses "/".
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? "/",
});
