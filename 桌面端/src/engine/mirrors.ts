import { readFile } from "node:fs/promises";

/**
 * 提示词 / 代码节点的镜像映射，唯一真源是
 * `HTML视频项目/workflow_runtime/tools/sync_prompts_to_yaml.py` 里的
 * `MAPPING` 与 `CODE_MAPPING`。桌面端不再自己维护一份副本：以前两份表各写各的，
 * 04 新增 h02sm / h02sk 后桌面端没跟着改，编辑时镜像会静默不同步。
 */
export interface MirrorMaps {
  prompts: Record<string, string>;
  codes: Record<string, string>;
  source: string;
  warning?: string;
}

function parseBlock(text: string, name: string): Record<string, string> | null {
  const block = new RegExp(`^${name}\\s*=\\s*\\{([\\s\\S]*?)^\\}`, "m").exec(text)?.[1];
  if (!block) return null;
  const map: Record<string, string> = {};
  for (const line of block.split("\n")) {
    const hit = /^\s*"([^"]+)"\s*:\s*"([^"]+)"\s*,?\s*$/.exec(line);
    if (hit?.[1] && hit[2]) map[hit[1]] = hit[2];
  }
  return Object.keys(map).length > 0 ? map : null;
}

/** 解析失败时返回空表 + warning，由调用方把 warning 回给界面，不能静默跳过同步。 */
export async function loadMirrorMaps(toolPath: string): Promise<MirrorMaps> {
  try {
    const text = await readFile(toolPath, "utf8");
    const prompts = parseBlock(text, "MAPPING");
    const codes = parseBlock(text, "CODE_MAPPING");
    if (!prompts || !codes) throw new Error("没有解析到 MAPPING / CODE_MAPPING");
    return { prompts, codes, source: toolPath };
  } catch (error) {
    return {
      prompts: {},
      codes: {},
      source: toolPath,
      warning: `镜像映射表读取失败（${(error as Error).message}），本次只写 YAML，保留资料/ 未同步`,
    };
  }
}
