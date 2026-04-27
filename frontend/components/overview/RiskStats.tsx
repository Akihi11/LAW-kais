import { ClauseRiskStats } from "@/lib/types";

interface RiskStatsProps {
  stats: ClauseRiskStats | null;
  needManualReview: boolean | null;
}

const ITEMS = [
  { key: "high_count", label: "高风险问题", className: "text-[#ef4444]" },
  { key: "medium_count", label: "中风险问题", className: "text-[#d97706]" },
  { key: "low_count", label: "低风险问题", className: "text-[#2563eb]" },
  { key: "extra_risk_topic_count", label: "缺失风险问题", className: "text-[#f97316]" },
] as const;

function getDisplayValue(value: number | null | undefined) {
  return typeof value === "number" ? String(value) : "—";
}

function getExtraRiskTopicDisplayValue(value: number | null | undefined) {
  return typeof value === "number" && value > 0 ? `${value}项` : "无";
}

export function RiskStats({ stats, needManualReview }: RiskStatsProps) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {ITEMS.map((item) => {
        const value =
          item.key === "extra_risk_topic_count"
            ? getExtraRiskTopicDisplayValue(stats?.[item.key])
            : getDisplayValue(stats?.[item.key]);

        return (
          <div key={item.key} className="glass-card p-5 text-center">
            <div className="text-sm text-[#64748b]">{item.label}</div>
            <div className={`mt-4 text-[40px] font-extrabold leading-none ${item.className}`}>{value}</div>
          </div>
        );
      })}

      <div className="glass-card p-5 text-center">
        <div className="text-sm text-[#64748b]">人工复核判断</div>
        <div className="mt-4 text-[24px] font-extrabold leading-tight text-[#0f2345]">
          {needManualReview === true ? "需要人工复核" : needManualReview === false ? "无需人工复核" : "待确认"}
        </div>
      </div>
    </section>
  );
}
