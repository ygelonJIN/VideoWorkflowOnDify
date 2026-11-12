export interface ImagePrompt {
  id?: string;
  scene_id?: string;
  role?: string;
  prompt?: string;
  prompt_zh?: string;
  negative?: string;
  size?: string;
}

export interface ImagePlan {
  prefix: string;
  images: ImagePrompt[];
}

/** 解析 H01P/H01PV 产出的 image_plan_json；不合法就返回 null，不抛错。 */
export function parseImagePlanValue(value: unknown): ImagePlan | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const plan = JSON.parse(value) as { prompt_prefix?: unknown; images?: unknown };
    if (!plan || !Array.isArray(plan.images)) return null;
    const images = plan.images.filter((item): item is ImagePrompt => Boolean(item) && typeof item === "object");
    if (images.length === 0) return null;
    return { prefix: String(plan.prompt_prefix ?? ""), images };
  } catch {
    return null;
  }
}

/** 跑完之后从 outputsByNode 里找图像计划：不需要用户再点节点。 */
export function findImagePlan(outputsByNode?: Record<string, Record<string, unknown>> | null): ImagePlan | null {
  if (!outputsByNode) return null;
  for (const outputs of Object.values(outputsByNode)) {
    const plan = parseImagePlanValue(outputs?.["image_plan_json"]);
    if (plan) return plan;
  }
  return null;
}
