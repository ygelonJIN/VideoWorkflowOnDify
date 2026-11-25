import { createRoot } from "react-dom/client";
import { App } from "./App.js";
import { installWheelRule } from "./wheel.js";

installWheelRule();

const root = document.getElementById("root");
if (!root) throw new Error("缺少 #root");
createRoot(root).render(<App />);
