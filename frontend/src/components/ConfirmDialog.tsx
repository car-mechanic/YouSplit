import { Loader2 } from "lucide-react";
import Modal from "./Modal";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  /** "emerald" für normale Aktionen, "danger" für destruktive (Löschen). */
  tone?: "emerald" | "danger";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Bestätigungs-Dialog mit Abbrechen/Bestätigen. Wird sowohl für die
 * Duplikats-Warnung ("Trotzdem speichern?") als auch fürs Löschen genutzt.
 */
function ConfirmDialog({
  title,
  message,
  confirmLabel,
  tone = "emerald",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmColor =
    tone === "danger"
      ? "bg-red-600 hover:bg-red-700"
      : "bg-emerald-600 hover:bg-emerald-700";

  return (
    <Modal title={title} onClose={onCancel}>
      <p className="text-sm leading-relaxed text-gray-600">{message}</p>

      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
        >
          Abbrechen
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={loading}
          className={`flex items-center justify-center gap-2 rounded-xl px-4 py-3 font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 ${confirmColor}`}
        >
          {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
