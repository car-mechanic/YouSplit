import { ArrowRight, Loader2, PartyPopper, Users } from "lucide-react";
import type { Settlement } from "../api";
import { formatEuro } from "../format";

interface SettlementCardProps {
  settlement: Settlement | null;
  loading: boolean;
}

/**
 * Kassensturz für N Personen. Zeigt die vom Backend berechneten minimalen
 * Ausgleichszahlungen ("wer schuldet wem wie viel") sowie die Salden je Person.
 * Reine Darstellung – die Berechnung liefert der Endpoint /lists/{id}/settlement.
 */
function SettlementCard({ settlement, loading }: SettlementCardProps) {
  const heading = (
    <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
      <Users className="h-4 w-4 text-emerald-600" />
      Kassensturz
      {loading && settlement && (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-600" />
      )}
    </h2>
  );

  // Erster Ladevorgang: es liegt noch kein Ergebnis vor
  if (settlement === null) {
    if (!loading) return null;
    return (
      <section className="mt-4 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
        {heading}
        <div className="mt-3 flex items-center justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
        </div>
      </section>
    );
  }

  const { transactions, balances } = settlement;

  // Ausgeglichen (keine offenen Zahlungen) – SVG-Icon statt Text-Emoji
  if (transactions.length === 0) {
    return (
      <section className="mt-4 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
        {heading}
        <div className="mt-3 flex items-center gap-3 rounded-xl bg-emerald-50 px-4 py-4">
          <PartyPopper className="h-6 w-6 shrink-0 text-emerald-600" />
          <p className="font-semibold text-emerald-700">Alles ausgeglichen!</p>
        </div>
      </section>
    );
  }

  return (
    <section className="mt-4 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
      {heading}

      <p className="mt-3 text-xs text-gray-400">
        So gleicht die Gruppe mit den wenigsten Überweisungen aus:
      </p>

      {/* ---------- Ausgleichszahlungen: wer schuldet wem wie viel ---------- */}
      <ul className="mt-2 space-y-2">
        {transactions.map((tx, index) => (
          <li
            key={`${tx.from_person}-${tx.to_person}-${index}`}
            className="flex items-center justify-between gap-3 rounded-xl bg-emerald-50 px-4 py-3"
          >
            <div className="flex min-w-0 items-center gap-2 font-semibold">
              <span className="truncate text-rose-600">{tx.from_person}</span>
              <ArrowRight className="h-4 w-4 shrink-0 text-gray-400" />
              <span className="truncate text-emerald-700">{tx.to_person}</span>
            </div>
            <span className="shrink-0 text-lg font-bold text-emerald-700">
              {formatEuro(tx.amount)}
            </span>
          </li>
        ))}
      </ul>

      {/* ---------- Salden je Person (Kontext zu den Zahlungen) ---------- */}
      {balances.length > 0 && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
            Salden
          </p>
          <ul className="space-y-1">
            {balances.map((balance) => (
              <li
                key={balance.name}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="truncate text-gray-600">{balance.name}</span>
                <span className={balanceColor(balance.net)}>
                  {balanceLabel(balance.net)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Farbe je nach Saldo: bekommt (grün), schuldet (rot), ausgeglichen (grau). */
function balanceColor(net: number): string {
  if (net > 0.005) return "font-semibold text-emerald-700";
  if (net < -0.005) return "font-semibold text-rose-600";
  return "text-gray-400";
}

/** Text je Saldo, aus Sicht der jeweiligen Person. */
function balanceLabel(net: number): string {
  if (net > 0.005) return `bekommt ${formatEuro(net)}`;
  if (net < -0.005) return `schuldet ${formatEuro(-net)}`;
  return "ausgeglichen";
}

export default SettlementCard;
