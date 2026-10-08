import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, Link2, Users } from "lucide-react";
import { formatEuro } from "../format";

interface ListHeaderProps {
  title: string;
  expenseCount: number;
  total: number;
  /** Feste Personen der Liste; der Knopf daneben öffnet ihre Bearbeitung. */
  members: string[];
  onEditMembers: () => void;
}

/**
 * Kopf-Card der Liste: Titel, Anzahl Ausgaben, Gesamtsumme und ein Button, der
 * den Teilen-Link (die aktuelle URL) in die Zwischenablage kopiert. Die kurze
 * "Kopiert!"-Rückmeldung ist reine Anzeige und lebt deshalb lokal hier.
 */
function ListHeader({
  title,
  expenseCount,
  total,
  members,
  onEditMembers,
}: ListHeaderProps) {
  const [copied, setCopied] = useState(false);

  function handleCopyLink() {
    // clipboard fehlt ohne HTTPS (z. B. Handy im WLAN über http://192.168…)
    navigator.clipboard
      ?.writeText(window.location.href)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => undefined);
  }

  return (
    <header className="rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-700 p-6 text-white shadow-lg shadow-emerald-600/20">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/"
            className="mb-2 inline-flex items-center gap-1 text-sm text-emerald-100 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Übersicht
          </Link>
          <h1 className="truncate text-2xl font-bold">{title}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-emerald-100">
            {expenseCount} {expenseCount === 1 ? "Ausgabe" : "Ausgaben"}
            <span aria-hidden>·</span>
            <button
              type="button"
              onClick={onEditMembers}
              title={members.join(", ")}
              className="flex items-center gap-1 whitespace-nowrap underline decoration-emerald-300/60 underline-offset-2 transition hover:text-white"
            >
              <Users className="h-3.5 w-3.5" />
              {members.length === 0
                ? "Personen festlegen"
                : `${members.length} ${members.length === 1 ? "Person" : "Personen"}`}
            </button>
          </p>
        </div>
        <button
          type="button"
          onClick={handleCopyLink}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-white/15 px-3 py-2 text-sm font-medium transition hover:bg-white/25"
        >
          {copied ? (
            <>
              <Check className="h-4 w-4" /> Kopiert!
            </>
          ) : (
            <>
              <Link2 className="h-4 w-4" /> Link teilen
            </>
          )}
        </button>
      </div>
      <p className="mt-5 text-4xl font-bold tracking-tight">
        {formatEuro(total)}
      </p>
      <p className="text-sm text-emerald-100">Gesamtausgaben</p>
    </header>
  );
}

export default ListHeader;
