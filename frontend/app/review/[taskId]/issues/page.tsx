"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { InfoBanner } from "@/components/common/InfoBanner";
import { PageShell } from "@/components/common/PageShell";
import { ContractViewer } from "@/components/issues/ContractViewer";
import { RiskFilter } from "@/components/issues/RiskFilter";
import { RiskList } from "@/components/issues/RiskList";
import { getErrorDisplayContent } from "@/lib/error-messages";
import {
  filterFindingItems,
  getClauseRiskStats,
  getContractSections,
  getOrderedFindings,
  groupFindingsByClause,
  resolveClauseGroupTargetSectionId,
  resolveFindingTargetSectionId,
} from "@/lib/result-helpers";
import { useReviewTask } from "@/lib/useReviewTask";
import { useReviewStore } from "@/stores/reviewStore";

interface IssuesPageProps {
  params: {
    taskId: string;
  };
}

const PAGE_TITLE = "逐条重点问题";
const RIGHT_PANEL_TITLE = "风险项";
const WAITING_TITLE = "正在审查中";
const WAITING_DESC = "逐条重点问题会在最终结果生成后展示。";

export default function IssuesPage({ params }: IssuesPageProps) {
  const taskId = decodeURIComponent(params.taskId);
  const currentFilter = useReviewStore((state) => state.currentFilter);
  const expandedIssueId = useReviewStore((state) => state.expandedIssueId);
  const setFilter = useReviewStore((state) => state.setFilter);
  const setExpandedIssueId = useReviewStore((state) => state.setExpandedIssueId);
  const { result, error } = useReviewTask(taskId, {
    shouldFetchResult: true,
    shouldPoll: true,
  });

  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [activeSectionSignal, setActiveSectionSignal] = useState(0);
  const initializedSelectionRef = useRef(false);

  const contractSections = useMemo(() => getContractSections(result), [result]);
  const allItems = useMemo(() => getOrderedFindings(result), [result]);
  const stats = useMemo(() => getClauseRiskStats(result), [result]);
  const filteredItems = useMemo(() => filterFindingItems(allItems, currentFilter), [allItems, currentFilter]);
  const groupedItems = useMemo(() => groupFindingsByClause(filteredItems), [filteredItems]);
  const errorDisplay = getErrorDisplayContent(error);

  const activateSection = (sectionId: string | null) => {
    setActiveSectionId(sectionId);
    setActiveSectionSignal((value) => value + 1);
  };

  const handleToggleClause = (groupId: string) => {
    const group = groupedItems.find((item) => item.id === groupId);
    if (!group) {
      return;
    }

    const sectionId = resolveClauseGroupTargetSectionId(group, contractSections);
    initializedSelectionRef.current = true;

    if (expandedIssueId === group.id) {
      setExpandedIssueId(null);
      setActiveFindingId(null);
      activateSection(sectionId);
      return;
    }

    setExpandedIssueId(group.id);
    setActiveFindingId(group.findings[0]?.id ?? null);
    activateSection(sectionId);
  };

  const handleSelectFinding = (groupId: string, findingId: string) => {
    const group = groupedItems.find((item) => item.id === groupId);
    if (!group) {
      return;
    }

    const finding = group.findings.find((item) => item.id === findingId);
    if (!finding) {
      return;
    }

    const sectionId =
      resolveFindingTargetSectionId(finding, contractSections) ?? resolveClauseGroupTargetSectionId(group, contractSections);

    initializedSelectionRef.current = true;
    setExpandedIssueId(group.id);
    setActiveFindingId(finding.id);
    activateSection(sectionId);
  };

  useEffect(() => {
    if (!result) {
      initializedSelectionRef.current = false;
      setActiveFindingId(null);
      setActiveSectionId(null);
      return;
    }

    if (!groupedItems.length) {
      if (expandedIssueId) {
        setExpandedIssueId(null);
      }
      if (activeFindingId) {
        setActiveFindingId(null);
      }
      if (activeSectionId) {
        setActiveSectionId(null);
      }
      return;
    }

    const activeGroup = expandedIssueId ? groupedItems.find((group) => group.id === expandedIssueId) ?? null : null;

    if (!activeGroup) {
      if (!initializedSelectionRef.current || expandedIssueId !== null) {
        const firstGroup = groupedItems[0];
        initializedSelectionRef.current = true;
        setExpandedIssueId(firstGroup.id);
        setActiveFindingId(firstGroup.findings[0]?.id ?? null);
        activateSection(resolveClauseGroupTargetSectionId(firstGroup, contractSections));
      } else if (activeFindingId && !filteredItems.some((item) => item.id === activeFindingId)) {
        setActiveFindingId(null);
      }
      return;
    }

    if (!activeGroup.findings.some((item) => item.id === activeFindingId)) {
      setActiveFindingId(activeGroup.findings[0]?.id ?? null);
    }
  }, [
    activeFindingId,
    activeSectionId,
    contractSections,
    expandedIssueId,
    filteredItems,
    groupedItems,
    result,
    setExpandedIssueId,
  ]);

  return (
    <PageShell>
      <div className="space-y-6">
        <div className="section-heading">
          <div>
            <h1 className="section-title">{PAGE_TITLE}</h1>
          </div>
        </div>

        {!result ? (
          <>
            <InfoBanner
              tone={errorDisplay?.tone ?? "warning"}
              title={errorDisplay?.title ?? WAITING_TITLE}
              description={errorDisplay?.description ?? WAITING_DESC}
            />
            <section className="glass-card p-7">
              <div className="empty-state-card">{WAITING_DESC}</div>
            </section>
          </>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)] xl:items-start">
            <ContractViewer
              sections={contractSections}
              activeSectionId={activeSectionId}
              activeSignal={activeSectionSignal}
            />

            <section className="glass-card p-5 sm:p-6">
              <div className="space-y-4">
                <h2 className="text-[22px] font-extrabold text-[#0f2345]">{RIGHT_PANEL_TITLE}</h2>

                <RiskFilter items={allItems} stats={stats} currentFilter={currentFilter} onChange={setFilter} />

                <RiskList
                  groups={groupedItems}
                  activeClauseId={expandedIssueId}
                  activeFindingId={activeFindingId}
                  onToggleClause={(group) => handleToggleClause(group.id)}
                  onSelectFinding={(group, finding) => handleSelectFinding(group.id, finding.id)}
                />
              </div>
            </section>
          </div>
        )}
      </div>
    </PageShell>
  );
}
