import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";

function findWorkspace(): string {
  let dir = process.cwd();
  for (;;) {
    if (existsSync(resolve(dir, "Dify工作流"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) throw new Error("找不到工作区根（含 Dify工作流 的目录）");
    dir = parent;
  }
}

export const WORKSPACE = findWorkspace();
export const WORKFLOW = resolve(WORKSPACE, "Dify工作流/04_黑帧口播_分组生成.yml");
export const WORKFLOW_01 = resolve(WORKSPACE, "Dify工作流/01_有数字人完整视频工作流.yml");
export const DESKTOP = resolve(WORKSPACE, "桌面端");
export const FIXTURES = resolve(DESKTOP, "fixtures");
export const STUB_DIR = resolve(FIXTURES, "stub");
export const INPUT = resolve(FIXTURES, "input.json");
export const A01_STUB = resolve(STUB_DIR, "a01.txt");
