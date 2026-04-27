import { getRiskLevelBadgeClass } from "@/lib/review-helpers";
import { RiskLevel } from "@/lib/types";

interface ConclusionBoxProps {
  riskLevel: RiskLevel;
  conclusion: string;
}

const TITLE = "\u603b\u4f53\u7ed3\u8bba";
const PREFIX = "\u98ce\u9669\u7b49\u7ea7\uff1a";

export function ConclusionBox({
  riskLevel,
  conclusion,
}: ConclusionBoxProps) {
  return (
    <div className="mt-6 rounded-[20px] border border-[#fed7aa] bg-[linear-gradient(135deg,#fff8ef,#ffffff)] px-6 py-5 text-[16px] leading-8 text-[#1f2937]">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <strong className="text-[20px] font-extrabold text-[#0f2345]">{TITLE}</strong>
        <span className={`status-pill ${getRiskLevelBadgeClass(riskLevel)}`}>{`${PREFIX}${riskLevel}`}</span>
      </div>
      <div>{conclusion}</div>
    </div>
  );
}
