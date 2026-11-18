// mermaid 形状模块的依赖重定向：只把"运行期环境"换掉，几何代码原样跑。
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import { existsSync } from 'node:fs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SHIMS = path.join(HERE, 'shims');

const MAP = [
  [/^d3$/, 'd3.mjs'],
  [/^roughjs$/, 'rough.mjs'],
  [/^khroma$/, 'khroma.mjs'],
  [/^dompurify$/, 'noui.mjs'],
  [/^cytoscape/, 'noui.mjs'],
  [/^elkjs/, 'noui.mjs'],
  [/^dagre-d3-es/, 'noui.mjs'],
  [/^d3-sankey$/, 'noui.mjs'],
  [/^fastdom$/, 'env.mjs'],
  [/diagram-api\/diagramAPI\.(js|ts)$/, 'env.mjs'],
  [/\/config\.(js|ts)$/, 'env.mjs'],
  [/\/config\.type\.(js|ts)$/, 'env.mjs'],
  [/\/defaultConfig\.(js|ts)$/, 'env.mjs'],
  [/\/utils\.(js|ts)$/, 'env.mjs'],
  [/\/logger\.(js|ts)$/, 'env.mjs'],
  [/\/profiler\.(js|ts)$/, 'env.mjs'],
  [/diagrams\/common\/common\.(js|ts)$/, 'env.mjs'],
  [/diagrams\/common\/colorThemeGate\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/createText\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/fastdom\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/icons\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/uid\.(js|ts)$/, 'uid.mjs'],
  [/rendering-elements\/shapes\/util\.(js|ts)$/, 'util.mjs'],
  [/rendering-elements\/shapes\/labelImageUtils\.(js|ts)$/, 'env.mjs'],
  [/rendering-elements\/shapes\/c4LabelHelper\.(js|ts)$/, 'env.mjs'],
  [/rendering-elements\/intersect\/.*\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/styles\.(js|ts)$/, 'env.mjs'],
  [/rendering-util\/insertElementsForSize\.(js|ts)$/, 'env.mjs'],
  [/rendering-elements\/clusters\.(js|ts)$/, 'env.mjs'],
  [/mermaidAPI\.(js|ts)$/, 'env.mjs'],
  [/\/diagram\.(js|ts)$/, 'env.mjs'],
];

export async function resolve(specifier, context, nextResolve) {
  for (const [re, file] of MAP) {
    if (re.test(specifier)) {
      return { url: pathToFileURL(path.join(SHIMS, file)).href, shortCircuit: true };
    }
  }
  // mermaid 的 import 写的是 .js，盘上是 .ts（TS 约定）；先自己找 .ts，再交回默认解析。
  if (specifier.startsWith('.') || specifier.startsWith('/')) {
    const base = specifier.startsWith('/')
      ? specifier
      : path.resolve(path.dirname(fileURLToPath(context.parentURL)), specifier);
    const cands = [base, base.replace(/\.(js|ts)$/, '.ts'), base.replace(/\.(js|ts)$/, '.tsx'),
      path.join(base, 'index.ts'), base + '.ts'];
    for (const c of cands) {
      if (!existsSync(c) || c.endsWith('/')) continue;
      // 命中影子表（按绝对路径再试一遍）：把运行期环境挡在外面
      for (const [re, file] of MAP) {
        if (re.test(specifier) || re.test(c)) {
          if (process.env.DBG && /fastdom|util/.test(c)) console.error('DBG map', specifier, '->', file);
          return { url: pathToFileURL(path.join(SHIMS, file)).href, shortCircuit: true };
        }
      }
      return { url: pathToFileURL(c).href, shortCircuit: true };
    }
  }
  return nextResolve(specifier, context);
}
