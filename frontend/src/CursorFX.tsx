import { useEffect, useRef } from "react";

/** A presentation-only cursor overlay. It does not participate in app state or actions. */
export default function CursorFX() {
  const cursor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = document.documentElement;
    const finePointer = window.matchMedia("(pointer: fine)");
    if (!finePointer.matches) return;

    root.classList.add("cursor-fx-enabled");
    const element = cursor.current;
    if (!element) return;

    let targetX = -80;
    let targetY = -80;
    let currentX = targetX;
    let currentY = targetY;
    let frame = 0;

    const move = (event: PointerEvent) => {
      targetX = event.clientX;
      targetY = event.clientY;
      element.classList.add("is-visible");
      if (!frame) frame = window.requestAnimationFrame(animate);
    };

    const animate = () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const easing = reducedMotion ? 1 : 0.42;
      currentX += (targetX - currentX) * easing;
      currentY += (targetY - currentY) * easing;
      element.style.left = `${currentX}px`;
      element.style.top = `${currentY}px`;
      if (Math.abs(targetX - currentX) > 0.15 || Math.abs(targetY - currentY) > 0.15) {
        frame = window.requestAnimationFrame(animate);
      } else {
        currentX = targetX;
        currentY = targetY;
        element.style.left = `${currentX}px`;
        element.style.top = `${currentY}px`;
        frame = 0;
      }
    };

    const over = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const textEntry = target.closest("input:not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio]),textarea,[contenteditable=true]");
      const embeddedPlayer = target.closest("iframe");
      const large = target.closest(".billboard-poster,.rec-card,.catalog-frame,.detail-poster img,.lobby-card img");
      const compact = target.closest("button,a,[role=button],select,label[for],input[type=checkbox],input[type=radio],.taste-tag,.preference-chip,.catalog-num");
      root.classList.toggle("cursor-fx-native", Boolean(embeddedPlayer));
      root.classList.toggle("cursor-fx-text", Boolean(textEntry));
      element.classList.toggle("is-compact", Boolean(compact && !textEntry));
      element.classList.toggle("is-large", Boolean(large && !textEntry));
      element.classList.toggle("is-pressed", event.type === "pointerdown");
    };

    const leave = () => {
      element.classList.remove("is-visible", "is-pressed");
      root.classList.remove("cursor-fx-native", "cursor-fx-text");
    };
    const down = () => element.classList.add("is-pressed");
    const up = () => element.classList.remove("is-pressed");

    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerover", over, { passive: true });
    document.addEventListener("pointerdown", down, { passive: true });
    document.addEventListener("pointerup", up, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    finePointer.addEventListener("change", leave);

    return () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerover", over);
      document.removeEventListener("pointerdown", down);
      document.removeEventListener("pointerup", up);
      document.documentElement.removeEventListener("pointerleave", leave);
      finePointer.removeEventListener("change", leave);
      if (frame) window.cancelAnimationFrame(frame);
      root.classList.remove("cursor-fx-enabled", "cursor-fx-native", "cursor-fx-text");
    };
  }, []);

  return <div ref={cursor} className="cinema-cursor" aria-hidden="true" />;
}
