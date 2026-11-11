// 用 esbuild 原生二进制打包渲染进程；不走 Vite，规避本机沙箱里 esbuild 服务起不来的问题。
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const candidates = [
  "node_modules/@esbuild/darwin-arm64/bin/esbuild",
  "node_modules/esbuild/bin/esbuild",
  "node_modules/esbuild/bin/esbuild.exe",
];
const binary = candidates.find((candidate) => existsSync(candidate));
if (!binary) {
  console.error("找不到 esbuild 二进制；先 npm install esbuild");
  process.exit(1);
}
mkdirSync("renderer/dist", { recursive: true });
execFileSync(
  resolve(binary),
  [
    "renderer/src/main.tsx",
    "--bundle",
    "--outfile=renderer/dist/app.js",
    "--format=esm",
    "--platform=browser",
    "--jsx=automatic",
    "--loader:.tsx=tsx",
    "--target=es2022",
    "--sourcemap",
    "--charset=utf8",
    "--log-level=warning",
  ],
  { stdio: "inherit" },
);
console.log("renderer/dist/app.js 已生成");
