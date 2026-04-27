import { RiskDetail } from "@/components/issues/RiskDetail";
import { ClauseFindingGroup, FindingListItem, splitClauseGroups } from "@/lib/result-helpers";
import { getIssueLevelBadgeClass, getLevelLabel } from "@/lib/review-helpers";

interface RiskListProps {
  groups: ClauseFindingGroup[];
  activeClauseId: string | null;
  activeFindingId: string | null;
  onToggleClause: (group: ClauseFindingGroup) => void;
  onSelectFinding: (group: ClauseFindingGroup, finding: FindingListItem) => void;
}

const EMPTY = "当前筛选条件下暂无重点问题。";
const OTHER_GROUP_TITLE = "其他";

function getRiskBadgeClass(group: ClauseFindingGroup) {
  if (group.isExtraRiskTopic) {
    return "bg-[#ecfeff] text-[#0f766e]";
  }
  if (group.isMissingItem) {
    return "bg-[#ffedd5] text-[#ea580c]";
  }
  if (group.highestLevel) {
    return getIssueLevelBadgeClass(group.highestLevel);
  }
  return "bg-[#f3f4f6] text-[#6b7280]";
}

function getRiskBadgeText(group: ClauseFindingGroup) {
  if (group.isExtraRiskTopic) {
    return "补充风险主题";
  }
  if (group.isMissingItem) {
    return "缺失项";
  }
  if (group.highestLevel) {
    return getLevelLabel(group.highestLevel);
  }
  return "待评估";
}

function getGroupCardClassName(group: ClauseFindingGroup, isExpanded: boolean) {
  if (group.isExtraRiskTopic) {
    return isExpanded
      ? "border-[#67e8f9] bg-[#f4feff] shadow-[0_8px_18px_rgba(15,118,110,0.08)]"
      : "border-[#a5f3fc] bg-[#f8feff]";
  }

  if (group.isMissingItem) {
    return isExpanded
      ? "border-[#fdba74] shadow-[0_8px_18px_rgba(249,115,22,0.08)]"
      : "border-[#fed7aa] bg-[#fffaf5]";
  }

  return isExpanded
    ? "border-[#93c5fd] shadow-[0_8px_18px_rgba(37,99,235,0.06)]"
    : "border-[#e5e7eb] bg-white";
}

function getFindingRiskBadgeClass(finding: FindingListItem) {
  if (finding.isMissingItem) {
    return "bg-[#ffedd5] text-[#ea580c]";
  }
  if (finding.level) {
    return getIssueLevelBadgeClass(finding.level);
  }
  return "bg-[#f3f4f6] text-[#6b7280]";
}

function getFindingRiskBadgeText(finding: FindingListItem) {
  if (finding.isMissingItem) {
    return "缺失项";
  }
  if (finding.level) {
    return getLevelLabel(finding.level);
  }
  return "待评估";
}

function ClauseCard({
  group,
  isExpanded,
  activeFindingId,
  onToggle,
  onSelectFinding,
}: {
  group: ClauseFindingGroup;
  isExpanded: boolean;
  activeFindingId: string | null;
  onToggle: () => void;
  onSelectFinding: (finding: FindingListItem) => void;
}) {
  const groupSubtitle = group.isExtraRiskTopic ? group.findings[0]?.topicCategory ?? null : null;

  return (
    <div className={`overflow-hidden rounded-[20px] border transition ${getGroupCardClassName(group, isExpanded)}`}>
      <button type="button" onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-4 text-left">
        <div className="min-w-0 flex-1">
          <div className="text-[17px] font-extrabold leading-7 text-[#0f2345]">{group.title}</div>
          {groupSubtitle ? <div className="mt-1 text-sm font-medium text-[#0f766e]">{groupSubtitle}</div> : null}
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <span className="status-pill border border-[#e5e7eb] bg-white text-[#475569]">{group.findings.length} 个问题</span>
          <span className={`status-pill ${getRiskBadgeClass(group)}`}>{getRiskBadgeText(group)}</span>
          {group.needManualReview ? (
            <span className="status-pill bg-[#fff7ed] text-[#c2410c]">建议人工复核</span>
          ) : null}
        </div>

        <span className={`pt-1 text-sm text-[#94a3b8] transition ${isExpanded ? "rotate-180" : ""}`}>v</span>
      </button>

      {isExpanded ? (
        <div className="border-t border-[#eef2f7] bg-[#fcfdff] px-5 py-5">
          <div className="space-y-4">
            {group.findings.map((finding) => {
              const isActiveFinding = finding.id === activeFindingId;
              return (
                <div
                  key={finding.id}
                  className={`rounded-[18px] border px-4 py-4 transition ${
                    isActiveFinding
                      ? "border-[#bfdbfe] bg-[#f8fbff] shadow-[0_6px_14px_rgba(37,99,235,0.08)]"
                      : "border-[#e5e7eb] bg-white"
                  }`}
                >
                  <button type="button" onClick={() => onSelectFinding(finding)} className="mb-4 block w-full text-left">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-[16px] font-bold text-[#0f2345]">{finding.typeLabel}</div>
                      <div className="flex flex-wrap items-center gap-2">
                        {finding.isExtraRiskTopic ? (
                          <span className="status-pill bg-[#ecfeff] text-[#0f766e]">补充风险主题</span>
                        ) : null}
                        <span className={`status-pill ${getFindingRiskBadgeClass(finding)}`}>{getFindingRiskBadgeText(finding)}</span>
                        {finding.needManualReview === true ? (
                          <span className="status-pill bg-[#fff7ed] text-[#c2410c]">建议人工复核</span>
                        ) : finding.needManualReview === false ? (
                          <span className="status-pill bg-[#ecfdf5] text-[#059669]">无需人工复核</span>
                        ) : null}
                      </div>
                    </div>
                  </button>

                  <RiskDetail item={finding} />
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function RiskList({ groups, activeClauseId, activeFindingId, onToggleClause, onSelectFinding }: RiskListProps) {
  if (!groups.length) {
    return <div className="empty-state-card">{EMPTY}</div>;
  }

  const { regularGroups, otherGroups } = splitClauseGroups(groups);

  return (
    <div className="space-y-4">
      {regularGroups.map((group) => (
        <ClauseCard
          key={group.id}
          group={group}
          isExpanded={group.id === activeClauseId}
          activeFindingId={activeFindingId}
          onToggle={() => onToggleClause(group)}
          onSelectFinding={(finding) => onSelectFinding(group, finding)}
        />
      ))}

      {otherGroups.length ? (
        <div className="space-y-3 pt-2">
          <div className="text-sm font-bold tracking-[0.08em] text-[#0f766e]">{OTHER_GROUP_TITLE}</div>
          {otherGroups.map((group) => (
            <ClauseCard
              key={group.id}
              group={group}
              isExpanded={group.id === activeClauseId}
              activeFindingId={activeFindingId}
              onToggle={() => onToggleClause(group)}
              onSelectFinding={(finding) => onSelectFinding(group, finding)}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
