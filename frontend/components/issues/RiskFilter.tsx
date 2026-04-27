import { ISSUE_FILTER_OPTIONS } from "@/lib/constants";
import { getFindingFilterCount, type FindingListItem } from "@/lib/result-helpers";
import { ClauseRiskStats, IssueFilter } from "@/lib/types";

interface RiskFilterProps {
  currentFilter: IssueFilter;
  items: FindingListItem[];
  stats: ClauseRiskStats | null;
  onChange: (filter: IssueFilter) => void;
}

export function RiskFilter({ currentFilter, items, stats, onChange }: RiskFilterProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {ISSUE_FILTER_OPTIONS.map((option) => {
        const isActive = option.value === currentFilter;
        const count = getFindingFilterCount(option.value, stats, items);

        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-full border px-4 py-2.5 text-sm font-bold transition ${
              isActive
                ? "border-[#93c5fd] bg-[#eef5ff] text-[#2563eb]"
                : "border-[#e5e7eb] bg-white text-[#334155] hover:border-[#93c5fd] hover:bg-[#eef5ff]"
            }`}
          >
            {`${option.label} ${count}`}
          </button>
        );
      })}
    </div>
  );
}
