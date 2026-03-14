/**
 * Vite 库模式构建配置
 *
 * 用法：pnpm run build:lib
 * 产物：dist/xyzw-token-manager.es.js  (ESM)
 *       dist/xyzw-token-manager.umd.js  (UMD)
 */
import { defineConfig } from "vite";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@utils": path.resolve(__dirname, "src/utils"),
      "@stores": path.resolve(__dirname, "src/stores"),
    },
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, "src/lib.js"),
      name: "XyzwTokenManager",
      fileName: (format) =>
        format === "es"
          ? "xyzw-token-manager.mjs"
          : "xyzw-token-manager.cjs",
    },
    rollupOptions: {
      // 不打包的外部依赖（使用方自行安装）
      external: ["lz4js"],
      output: {
        globals: {
          lz4js: "lz4",
        },
      },
    },
    outDir: "dist",
    emptyOutDir: false,
  },
});
