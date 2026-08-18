export function LoadingPanel() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-md-primary-container/30 border-t-md-primary" />
        <p className="text-sm text-md-on-surface-variant">Analyzing infrastructure…</p>
      </div>
    </div>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="max-w-md rounded-xl border border-md-error/30 bg-md-error-container/20 p-6 text-center">
        <p className="text-sm font-medium text-md-error">Could not load analysis</p>
        <p className="mt-2 text-xs text-md-on-surface-variant">{message}</p>
      </div>
    </div>
  );
}
