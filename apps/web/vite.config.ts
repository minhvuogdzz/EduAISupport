import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import { mockLessonPlugin } from "./vite-plugins/mockLesson.ts";

// Port of the session API of services/api (`make api`, `make api-memory`, `make demo`).
const apiPort = process.env.CAVAT_API_PORT ?? "8000";

export default defineConfig({
  plugins: [react(), tailwindcss(), mockLessonPlugin()],
  server: {
    port: 5173,
    // Only used when the app runs with VITE_API=http.
    proxy: { "/v1": { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "vite-plugins/**/*.test.ts"],
  },
});
