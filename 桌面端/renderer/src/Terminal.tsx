import { useEffect, useRef, useState } from "react";
import { bridge } from "./bridge.js";
import type { TermPreset } from "./types.js";

const api = bridge();

function stripAnsi(text: string): string {
  return text.replace(/\u001b\[[0-9;]*[A-Za-z]/g, "");
}

export function Terminal() {
  const [output, setOutput] = useState("");
  const [command, setCommand] = useState("");
  const [running, setRunning] = useState(false);
  const [presets, setPresets] = useState<TermPreset[]>([]);
  const box = useRef<HTMLPreElement>(null);

  useEffect(() => {
    api.presets().then(setPresets).catch(() => setPresets([]));
  }, []);

  useEffect(() => {
    const off = api.onTerm((event) => {
      if (event.kind === "data") {
        setOutput((previous) => previous + stripAnsi(event.text ?? ""));
      } else {
        setRunning(false);
        setOutput((previous) => `${previous}\n[exit ${event.code ?? -1} · ${event.ms ?? 0}ms]\n`);
      }
    });
    return off;
  }, []);

  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [output]);

  async function run(cmd: string) {
    if (!cmd.trim() || running) return;
    setRunning(true);
    setOutput((previous) => `${previous}$ ${cmd}\n`);
    try {
      await api.exec({ cmd });
    } catch (error) {
      setRunning(false);
      setOutput((previous) => `${previous}[启动失败] ${(error as Error).message}\n`);
    }
  }

  return (
    <div className="term-panel">
      <div className="term-presets">
        {presets.map((preset) => (
          <button key={preset.id} className="btn" onClick={() => void run(preset.cmd)} disabled={running}>
            {preset.label}
          </button>
        ))}
        <span className="spacer" />
        <button className="btn" onClick={() => setOutput("")} disabled={running}>清空</button>
      </div>
      <pre className="term-output" ref={box}>{output || "命令输出会显示在这里。预设命令都在工作区根目录执行。\n"}</pre>
      <form
        className="term-input"
        onSubmit={(event) => {
          event.preventDefault();
          void run(command);
          setCommand("");
        }}
      >
        <span className="prompt">$</span>
        <input
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          placeholder="输入命令，回车执行"
          disabled={running}
        />
        <button className="btn primary" type="submit" disabled={running || !command.trim()}>执行</button>
      </form>
    </div>
  );
}
