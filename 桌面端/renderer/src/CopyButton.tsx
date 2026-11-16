import { useState } from "react";
import { bridge } from "./bridge.js";

const api = bridge();

export function CopyButton({
  text,
  label = "复制",
  onCopied,
}: {
  text: string;
  label?: string;
  /** 复制成功后要顺带做的事：出图页用它把「放图」展开。 */
  onCopied?: () => void;
}) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");
  return (
    <button
      className="btn sm ghost"
      onClick={() => {
        const settle = (next: "done" | "failed") => {
          setState(next);
          window.setTimeout(() => setState("idle"), 1400);
        };
        void api
          .copyText(text)
          .then(() => {
            settle("done");
            onCopied?.();
          })
          // 剪贴板失败要说出来：不然点了没反应，看着像按钮坏了
          .catch(() => settle("failed"));
      }}
    >
      {state === "done" ? "已复制" : state === "failed" ? "复制失败" : label}
    </button>
  );
}
