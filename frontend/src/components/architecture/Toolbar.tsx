interface Props {
  visibleCount: number;
  edgeCount: number;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  showSupporting: boolean;
  onToggleSupporting: (v: boolean) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
}

export function Toolbar({
  visibleCount,
  edgeCount,
  searchQuery,
  onSearchChange,
  showSupporting,
  onToggleSupporting,
  onZoomIn,
  onZoomOut,
  onFit,
}: Props) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <button
        onClick={onZoomIn}
        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
        title="Zoom in"
      >
        <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="7" cy="7" r="5" />
          <path d="M11 11l3 3M5 7h4M7 5v4" />
        </svg>
      </button>
      <button
        onClick={onZoomOut}
        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
        title="Zoom out"
      >
        <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="7" cy="7" r="5" />
          <path d="M11 11l3 3M5 7h4" />
        </svg>
      </button>
      <button
        onClick={onFit}
        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
        title="Fit to screen"
      >
        <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="2" y="2" width="12" height="12" rx="2" />
          <path d="M6 2v12M2 6h12" />
        </svg>
      </button>

      <input
        type="text"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search nodes\u2026"
        className="ml-2 px-2.5 py-1 text-[11px] rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-300 w-36"
      />

      <label className="flex items-center gap-1.5 text-[11px] text-gray-500 cursor-pointer select-none ml-2">
        <input
          type="checkbox"
          checked={showSupporting}
          onChange={(e) => onToggleSupporting(e.target.checked)}
          className="rounded border-gray-300 accent-blue-500"
        />
        Implementation
      </label>

      <span className="text-[10px] text-gray-400 ml-auto">
        {visibleCount} nodes \u00b7 {edgeCount} edges
      </span>
    </div>
  );
}
