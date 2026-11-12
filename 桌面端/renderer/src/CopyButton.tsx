import { useState } from "react";
import { bridge } from "./bridge.js";

const api = bridge();

export function CopyButton({ text, label = "复制" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn sm ghost"
      onClick={() => {
        void api.copyText(text).then(() => {
          setDone(true);
          window.setTimeout(() => setDone(false), 1200);
        });
      }}
    >
      {done ? "已复制" : label}
    </button>
  );
}
