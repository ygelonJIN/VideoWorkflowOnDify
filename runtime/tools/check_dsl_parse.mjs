#!/usr/bin/env node
// 用「桌面端导入时同一份 YAML 解析器」解析 Dify工作流/*.yml。
//
// 为什么单独有这一步：仓库里的校验一直是 `python3 -c "yaml.safe_load(...)"`，
// 但桌面端（以及 YAML 1.2 世界的解析器）用的不是 PyYAML。2026-11-20 踩过：
// 改节点 code 时用 PyYAML 回写，折行续行只缩进 2 空格，而 `code:` 键在 8 空格下——
// 续行不够深，`yaml` 包判定标量提前结束，报 `Missing closing "quote`；
// 同一份文件 `yaml.safe_load` 却完全正常。PyYAML 通过 ≠ 能导入。
//
// 用法：
//   node runtime/tools/check_dsl_parse.mjs            # 查 Dify工作流/*.yml
//   node runtime/tools/check_dsl_parse.mjs a.yml b.yml
// 这是格式/环境检查（不是内容检查）：解析不过就退出 1，因为导入一定会失败。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');   // runtime/tools → 仓库根

// 优先用桌面端装的那份 yaml 包——导入走的就是它，版本必须一致
const require = createRequire(path.join(repoRoot, '桌面端/package.json'));
let YAML;
try {
  YAML = require('yaml');
} catch {
  console.error('缺少 yaml 包：请在 桌面端/ 下 npm install（导入用的就是这份）');
  process.exit(2);
}

const targets = process.argv.slice(2).length
  ? process.argv.slice(2)
  : fs.readdirSync(path.join(repoRoot, 'Dify工作流'))
      .filter((f) => f.endsWith('.yml'))
      .map((f) => path.join(repoRoot, 'Dify工作流', f));

let failed = 0;
for (const file of targets) {
  const text = fs.readFileSync(file, 'utf8');
  const rel = path.relative(repoRoot, file);
  try {
    const doc = YAML.parse(text);
    const nodes = doc?.workflow?.graph?.nodes;
    if (!Array.isArray(nodes)) throw new Error('缺少 workflow.graph.nodes');
    const noCode = nodes.filter((n) => n?.data?.type === 'code' && !n.data.code).length;
    const longLine = Math.max(...text.split('\n').map((l) => l.length));
    console.log(`OK   ${rel}  节点 ${nodes.length}  最长行 ${longLine}` +
      (noCode ? `  ⚠ 有 ${noCode} 个 code 节点没有 code` : ''));
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${rel}`);
    console.log('     ' + String(error.message).split('\n')[0]);
  }
}

if (failed) {
  console.log(`\n${failed} 个文件解析不过——导入 Dify 一定会失败，先修格式。`);
  process.exit(1);
}
