import { payerStorageKey } from "./payerStorage";

/**
 * Merkt sich je Liste und Gerät, dass das Tutorial gelaufen ist (localStorage,
 * wie der gemerkte Zahler). Eine eigene Geräte-ID braucht es dafür nicht: der
 * localStorage gehört ohnehin genau zu diesem Browser auf diesem Gerät.
 */
const doneKey = (listId: string): string =>
  `yousplit:list:${listId}:tutorial-done`;

/**
 * Tutorial zeigen? Nur beim ersten Öffnen der Liste auf diesem Gerät – egal ob
 * selbst angelegt oder über einen geteilten Link. Wer auf dem Gerät schon einen
 * Zahler für die Liste gewählt hat, nutzt sie bereits (Listen von vor dem
 * Tutorial) und bekommt es nicht nachträglich.
 */
export function shouldShowTutorial(listId: string): boolean {
  try {
    return (
      localStorage.getItem(doneKey(listId)) === null &&
      !localStorage.getItem(payerStorageKey(listId))?.trim()
    );
  } catch {
    // Speicher nicht verfügbar (privater Modus): lieber kein Tutorial bei
    // jedem Aufruf
    return false;
  }
}

export function markTutorialDone(listId: string): void {
  try {
    localStorage.setItem(doneKey(listId), "1");
  } catch {
    // Speicher nicht verfügbar: dann kommt das Tutorial beim nächsten Mal wieder
  }
}
