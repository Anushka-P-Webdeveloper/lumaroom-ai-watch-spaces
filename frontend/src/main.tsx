import { createRoot } from "react-dom/client";
import App from "./App";
import CursorFX from "./CursorFX";
import "./styles.css";
createRoot(document.getElementById("root")!).render(<><App /><CursorFX /></>);
