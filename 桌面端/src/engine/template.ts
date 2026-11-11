import type { VariablePool } from "./vars.js";
import { stringValue } from "./vars.js";

const DIFY_REF = /\{\{#([^}#]+)#\}\}/g;

/** 把提示词里的 `{{#node.field#}}` 换成变量值；找不到就是空串（Dify 行为）。 */
export function interpolateDify(text: string, pool: VariablePool): string {
  if (!text) return "";
  return text.replace(DIFY_REF, (_match, selector: string) => {
    const parts = selector.trim().split(".");
    if (parts.length < 2) return "";
    return stringValue(pool.get(parts));
  });
}

/** 找出文本里引用到的所有选择器，用于运行前 lint。 */
export function difySelectors(text: string): string[][] {
  const found: string[][] = [];
  for (const match of text.matchAll(DIFY_REF)) {
    const selector = (match[1] ?? "").trim();
    if (selector) found.push(selector.split("."));
  }
  return found;
}

const JINJA_VAR = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\|\s*default\(\s*(?:"([^"]*)"|'([^']*)')\s*\))?\s*\}\}/g;

/**
 * template-transform 用。Dify 那边是 Jinja2，我们只支持最常见的两种写法：
 * `{{ name }}` 和 `{{ name | default("x") }}`。复杂模板会在运行前被 lint 标记。
 */
export function renderTemplateJinja(template: string, variables: Record<string, unknown>): string {
  return template.replace(JINJA_VAR, (_match, name: string, doubleQuoted?: string, singleQuoted?: string) => {
    const value = variables[name];
    if (value === undefined || value === null || value === "") {
      const fallback = doubleQuoted ?? singleQuoted;
      return fallback !== undefined ? fallback : stringValue(value);
    }
    return stringValue(value);
  });
}
