import { useEffect, useRef, useState, type ReactNode } from "react";

type TooltipProps = {
  content: ReactNode;
  children: ReactNode;
  maxWidthClassName?: string;
};

export function Tooltip({
  content,
  children,
  maxWidthClassName = "max-w-[90vw] w-96 sm:w-[28rem] md:w-[32rem]",
}: TooltipProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (e: PointerEvent) => {
      if (!rootRef.current) return;
      if (rootRef.current.contains(e.target as Node)) return;
      setOpen(false);
    };

    window.addEventListener("pointerdown", handlePointerDown, { capture: true });
    return () => window.removeEventListener("pointerdown", handlePointerDown, { capture: true } as any);
  }, [open]);

  return (
    <span
      ref={rootRef}
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        className="inline-flex"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        {children}
      </span>

      {open && (
        <span
          role="tooltip"
          className={`absolute left-1/2 top-full z-50 mt-2 -translate-x-1/2 rounded-2xl border border-gray-200 bg-white px-5 py-4 text-center text-xs text-gray-700 shadow-lg ${maxWidthClassName}`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
