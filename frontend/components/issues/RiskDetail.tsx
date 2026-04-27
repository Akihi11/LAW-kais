import { type ReactNode } from "react";

import { FindingListItem } from "@/lib/result-helpers";

const SUGGESTION_EMPTY = "未提供修改建议";
const COMPARISON_EMPTY = "未提供建议修订";

interface RiskDetailProps {
  item: FindingListItem;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[15px] font-bold text-[#475569]">{title}</div>
      <div className="mt-2 whitespace-pre-line text-[15px] leading-8 text-[#334155]">{children}</div>
    </div>
  );
}

export function RiskDetail({ item }: RiskDetailProps) {
  const revisionSuggestion = item.revisionSuggestion ?? SUGGESTION_EMPTY;
  const comparisonSuggestionText = item.comparisonSuggestionText ?? COMPARISON_EMPTY;
  const comparisonTitle = item.isExtraRiskTopic ? "相关原文与建议对比" : "原文与建议对比";
  const originalTitle = item.isExtraRiskTopic ? "相关原文" : "原条款";

  return (
    <div className="space-y-5">
      {item.riskReason ? <Section title="风险说明">{item.riskReason}</Section> : null}
      {item.isExtraRiskTopic && item.topicCategory ? <Section title="主题分类">{item.topicCategory}</Section> : null}
      {item.coreIssue ? <Section title="核心问题">{item.coreIssue}</Section> : null}
      {item.evidencePosition ? <Section title="证据位置">{item.evidencePosition}</Section> : null}

      {item.evidenceQuote ? (
        <div>
          <div className="text-[15px] font-bold text-[#475569]">证据引用</div>
          <div className="mt-2 rounded-[12px] border border-[#fde68a] bg-[#fffbea] px-4 py-4 text-[15px] leading-8 text-[#1f2937]">
            {item.evidenceQuote}
          </div>
        </div>
      ) : null}

      {item.supplementaryNote ? <Section title="补充说明">{item.supplementaryNote}</Section> : null}

      <Section title="修改建议">{revisionSuggestion}</Section>

      <div>
        <div className="text-[15px] font-bold text-[#475569]">{comparisonTitle}</div>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div className="rounded-[16px] border border-[#e5e7eb] bg-white px-4 py-4">
            <div className="text-sm font-bold text-[#64748b]">{originalTitle}</div>
            <div className="mt-3 whitespace-pre-line text-[15px] leading-8 text-[#334155]">{item.originalClauseText}</div>
          </div>
          <div className="rounded-[16px] border border-[#bfdbfe] bg-[#f8fbff] px-4 py-4">
            <div className="text-sm font-bold text-[#2563eb]">建议修订</div>
            <div className="mt-3 whitespace-pre-line text-[15px] leading-8 text-[#1e3a8a]">{comparisonSuggestionText}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
