import { useEffect, useRef, useState } from "react";
import { MoreVertical, Pencil, Trash2 } from "lucide-react";

interface ListCardMenuProps {
  title: string;
  onRename: () => void;
  onDelete: () => void;
}

/**
 * Three-dot menu in the top right corner of an overview card. It sits outside
 * the card link, so opening it never navigates into the list.
 */
function ListCardMenu({ title, onRename, onDelete }: ListCardMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on a click elsewhere or on Escape, like a native menu
  useEffect(() => {
    if (!open) return;
    function handlePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("pointerdown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  function choose(action: () => void) {
    setOpen(false);
    action();
  }

  const itemClass =
    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition hover:bg-gray-100";

  return (
    <div ref={rootRef} className="absolute top-2 right-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={`Aktionen für „${title}“`}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => choose(onRename)}
            className={`${itemClass} text-gray-700`}
          >
            <Pencil className="h-4 w-4" />
            Umbenennen
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => choose(onDelete)}
            className={`${itemClass} text-red-600`}
          >
            <Trash2 className="h-4 w-4" />
            Löschen
          </button>
        </div>
      )}
    </div>
  );
}

export default ListCardMenu;
