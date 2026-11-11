import { useEffect, useRef, useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

interface Props {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  width?: number;
  title?: string;
}

/** 主题化下拉：原生 select 的弹层不跟主题，这里自绘；Esc / 点外面关闭。 */
export function Select({ value, options, onChange, placeholder = "请选择", width, title }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((option) => option.value === value);

  useEffect(() => {
    if (!open) return;
    const onDoc = (event: PointerEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDoc, true);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDoc, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={`sel ${open ? "open" : ""}`} ref={ref} style={width ? { width } : undefined}>
      <button
        type="button"
        className="sel-btn"
        title={title ?? current?.label ?? placeholder}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span className="sel-label">{current?.label ?? placeholder}</span>
        <span className="sel-caret" aria-hidden="true" />
      </button>
      {open && (
        <ul className="sel-menu" role="listbox">
          {options.map((option) => (
            <li
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              className={`${option.value === value ? "on" : ""} ${option.disabled ? "disabled" : ""}`}
              onMouseDown={(event) => {
                event.preventDefault();
                if (option.disabled) return;
                setOpen(false);
                onChange(option.value);
              }}
            >
              <span>{option.label}</span>
              {option.hint && <span className="dim">{option.hint}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
