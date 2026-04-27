import { REVIEW_ROLES } from "@/lib/constants";
import { ReviewRole } from "@/lib/types";

interface PerspectiveSelectorProps {
  value: ReviewRole;
  onChange: (role: ReviewRole) => void;
}

const LABEL = "审查视角";

export function PerspectiveSelector({ value, onChange }: PerspectiveSelectorProps) {
  return (
    <div className="space-y-3">
      <p className="field-label">{LABEL}</p>
      <div className="flex flex-wrap gap-3">
        {REVIEW_ROLES.map((role) => {
          const isActive = role === value;
          return (
            <button
              key={role}
              type="button"
              onClick={() => onChange(role)}
              className={`min-w-[96px] rounded-full border px-5 py-3 text-[17px] font-bold transition ${
                isActive
                  ? "border-[#93c5fd] bg-[#dbeafe] text-[#1d4ed8]"
                  : "border-[#e5e7eb] bg-white text-[#334155] hover:border-[#93c5fd] hover:bg-[#eef5ff]"
              }`}
            >
              {role}
            </button>
          );
        })}
      </div>
    </div>
  );
}
