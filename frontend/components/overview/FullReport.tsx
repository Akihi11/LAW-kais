import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

interface FullReportProps {
  report: string | null | undefined;
}

const TITLE = "完整报告";
const EMPTY = "完整报告尚未生成。";

export function FullReport({ report }: FullReportProps) {
  return (
    <section className="glass-card p-7">
      <h2 className="text-[22px] font-extrabold text-[#0f2345]">{TITLE}</h2>
      <div className="mt-5 rounded-[18px] border border-[#e5e7eb] bg-[#fafafa] px-6 py-5">
        {report?.trim() ? <MarkdownRenderer content={report} /> : <div className="empty-state-card">{EMPTY}</div>}
      </div>
    </section>
  );
}
