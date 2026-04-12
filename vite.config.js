import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { NaiveUiResolver } from "unplugin-vue-components/resolvers";
import path from "path";
import { fileURLToPath } from "url";

const PROXY_ENV_KEYS = [
  "HTTP_PROXY",
  "HTTPS_PROXY",
  "ALL_PROXY",
  "NO_PROXY",
  "http_proxy",
  "https_proxy",
  "all_proxy",
  "no_proxy",
];

for (const key of PROXY_ENV_KEYS)
  delete process.env[key];

process.env.NODE_USE_ENV_PROXY = "0";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    vue(),
    Components({
      resolvers: [NaiveUiResolver()],
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@api": path.resolve(__dirname, "src/api"),
      "@stores": path.resolve(__dirname, "src/stores"),
    },
  },
  server: {
    port: 3000,
    open: true,
    host: true,
    proxy: {
      "/card-api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: pathValue => pathValue.replace(/^\/card-api/, ""),
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 800,
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: "modern-compiler",
        silenceDeprecations: ["legacy-js-api"],
        additionalData: '@use "@/assets/styles/variables.scss" as vars;',
      },
    },
  },
});
