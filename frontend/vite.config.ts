import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    // В новых версиях Node есть свой localStorage; он перекрывает хранилище jsdom
    poolOptions: { forks: { execArgv: ["--no-experimental-webstorage"] } },
  },
});
