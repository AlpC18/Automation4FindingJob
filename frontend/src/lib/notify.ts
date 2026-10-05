/** Shows a short message in the corner of the app instead of a blocking browser pop-up. */
export function notify(message: unknown): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("app-notify", { detail: String(message ?? "") }));
}
