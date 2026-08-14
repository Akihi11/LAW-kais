import {
  ClauseOrderedFinding,
  ClauseRiskStats,
  ContractSection,
  ExtraRiskTopic,
  IssueFilter,
  IssueItem,
  IssueLevel,
  ReviewResultResponse,
  RiskLevel,
} from "@/lib/types";

const MISSING_CLAUSE_ORDER = 99999;
const ORIGINAL_CLAUSE_EMPTY = "未提取到完整原条款";

const RISK_PRIORITY: Record<IssueLevel, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

const CHINESE_NUMBER_MAP: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
};

const CHINESE_UNIT_MAP: Record<string, number> = {
  十: 10,
  百: 100,
  千: 1000,
  万: 10000,
};

export type FindingRiskLabel = RiskLevel | "缺失项";

export interface FindingListItem {
  id: string;
  sourceIndex: number;
  clauseKey: string;
  clauseOrder: number | null;
  clauseTitle: string;
  clauseType: string | null;
  typeLabel: string;
  isMissingItem: boolean;
  isExtraRiskTopic: boolean;
  level: IssueLevel | null;
  riskLabel: FindingRiskLabel | null;
  riskReason: string | null;
  coreIssue: string | null;
  evidenceQuote: string | null;
  evidencePosition: string | null;
  revisionSuggestion: string | null;
  proposedAmendment: string | null;
  comparisonSuggestionText: string | null;
  needManualReview: boolean | null;
  sectionId: string | null;
  originalClauseText: string;
  topicCategory: string | null;
  supplementaryNote: string | null;
  relatedClauseTitles: string[];
}

export interface ClauseFindingGroup {
  id: string;
  clauseKey: string;
  clauseOrder: number | null;
  title: string;
  isMissingItem: boolean;
  isExtraRiskTopic: boolean;
  highestLevel: IssueLevel | null;
  riskLabel: FindingRiskLabel | null;
  needManualReview: boolean;
  sectionId: string | null;
  findings: FindingListItem[];
  sourceIndex: number;
}

export interface OverviewSummary {
  contractType: string | null;
  overallConclusion: string | null;
  overallRiskLevel: RiskLevel | null;
  needManualReview: boolean | null;
  stats: ClauseRiskStats | null;
  finalReviewReport: string | null;
}

interface IssueFallbackEntry {
  item: IssueItem;
  normalizedTitle: string;
  normalizedPosition: string;
  normalizedEvidence: string;
  suggestion: string | null;
}

function safeText(value: string | null | undefined) {
  return (value ?? "").trim();
}

function normalizeText(value: string) {
  return value.replace(/\s+/g, "").replace(/[，。；：、“”‘’（）【】《》·,.;:()\[\]{}'"<>]/g, "").toLowerCase();
}

function hasNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value);
}

function toSectionId(value: string | null | undefined, index: number) {
  const text = safeText(value);
  return text || `section-${index + 1}`;
}

function buildContractSections(sections: ContractSection[] | null | undefined): ContractSection[] {
  return (Array.isArray(sections) ? sections : []).map((section, index) => ({
    id: toSectionId(section?.id ?? null, index),
    title: safeText(section?.title ?? null) || `第 ${index + 1} 部分`,
    paragraphs: Array.isArray(section?.paragraphs)
      ? section.paragraphs.map((paragraph) => safeText(paragraph)).filter(Boolean)
      : [],
  }));
}

export function getContractSections(result: ReviewResultResponse | null): ContractSection[] {
  return buildContractSections(result?.contractSections ?? []);
}

export function normalizeRiskLevel(value: string | null | undefined): RiskLevel | null {
  const text = safeText(value).toLowerCase();

  if (["高", "高风险", "high", "critical"].includes(text)) {
    return "高";
  }
  if (["中", "中风险", "medium", "moderate"].includes(text)) {
    return "中";
  }
  if (["低", "低风险", "low"].includes(text)) {
    return "低";
  }

  return null;
}

function buildFindingLevel(riskLevel: string | null | undefined): IssueLevel | null {
  const normalized = normalizeRiskLevel(riskLevel);
  if (normalized === "高") {
    return "high";
  }
  if (normalized === "中") {
    return "medium";
  }
  if (normalized === "低") {
    return "low";
  }
  return null;
}

function resolveNeedManualReview(level: IssueLevel | null, value: boolean | null | undefined): boolean | null {
  if (level === "high" || level === "medium") {
    return true;
  }
  return typeof value === "boolean" ? value : null;
}

function getRiskLabelFromLevel(level: IssueLevel | null, isMissingItem: boolean): FindingRiskLabel | null {
  if (isMissingItem) {
    return "缺失项";
  }
  if (level === "high") {
    return "高";
  }
  if (level === "medium") {
    return "中";
  }
  if (level === "low") {
    return "低";
  }
  return null;
}

export function isMissingClauseOrder(value: number | null | undefined) {
  return value === MISSING_CLAUSE_ORDER;
}

function buildClauseTitle(finding: ClauseOrderedFinding, isMissingItem: boolean) {
  const clauseTitle = safeText(finding.clause_title);
  if (clauseTitle) {
    return clauseTitle;
  }

  const evidencePosition = safeText(finding.evidence_position);
  if (evidencePosition) {
    return evidencePosition;
  }

  return isMissingItem ? "关键缺失项" : "未命名条款";
}

function buildTypeLabel(clauseType: string | null, fallbackLabel: string) {
  return safeText(clauseType) || fallbackLabel;
}

function buildClauseKey(
  clauseOrder: number | null,
  clauseTitle: string,
  isMissingItem: boolean,
  fallbackKey: string,
  index: number,
) {
  const normalizedTitle = normalizeText(clauseTitle || fallbackKey);

  if (isMissingItem) {
    if (normalizedTitle) {
      return `missing::${normalizedTitle}`;
    }
    if (hasNumber(clauseOrder) && clauseOrder !== null) {
      return `missing-order::${clauseOrder}`;
    }
    return `missing::${index}`;
  }
  if (normalizedTitle) {
    return `clause::${normalizedTitle}`;
  }
  if (hasNumber(clauseOrder) && clauseOrder !== null) {
    return `clause-order::${clauseOrder}`;
  }
  return `clause::${index}`;
}

function buildExtraRiskTopicKey(topicTitle: string, fallbackKey: string, index: number) {
  const normalizedTitle = normalizeText(topicTitle || fallbackKey);
  return normalizedTitle ? `extra::${normalizedTitle}` : `extra::${index}`;
}

function mergeClauseOrder(current: number | null, candidate: number | null) {
  const currentHasOrder = hasNumber(current) && current !== null;
  const candidateHasOrder = hasNumber(candidate) && candidate !== null;

  if (!currentHasOrder) {
    return candidateHasOrder ? candidate : current;
  }
  if (!candidateHasOrder) {
    return current;
  }

  return Math.min(current, candidate);
}

function findSectionByTitle(candidate: string, sections: ContractSection[]) {
  const normalizedCandidate = normalizeText(candidate);
  if (!normalizedCandidate) {
    return null;
  }

  const exactMatch = sections.find((section) => normalizeText(section.title) === normalizedCandidate);
  if (exactMatch) {
    return exactMatch;
  }

  return (
    sections.find((section) => normalizeText(section.title).includes(normalizedCandidate)) ??
    sections.find((section) => normalizedCandidate.includes(normalizeText(section.title))) ??
    null
  );
}

function findSectionByEvidenceQuote(candidate: string, sections: ContractSection[]) {
  const normalizedCandidate = normalizeText(candidate).slice(0, 80);
  if (!normalizedCandidate) {
    return null;
  }

  return (
    sections.find((section) =>
      section.paragraphs.some((paragraph) => {
        const normalizedParagraph = normalizeText(paragraph);
        if (!normalizedParagraph) {
          return false;
        }
        return normalizedParagraph.includes(normalizedCandidate) || normalizedCandidate.includes(normalizedParagraph.slice(0, 80));
      }),
    ) ?? null
  );
}

function findMatchingContractSection(
  sections: ContractSection[],
  evidencePosition: string | null,
  clauseTitle: string,
  evidenceQuote: string | null,
) {
  if (!sections.length) {
    return null;
  }

  const positionText = safeText(evidencePosition);
  if (positionText) {
    const byPosition = findSectionByTitle(positionText, sections);
    if (byPosition) {
      return byPosition;
    }
  }

  const titleText = safeText(clauseTitle);
  if (titleText) {
    const byTitle = findSectionByTitle(titleText, sections);
    if (byTitle) {
      return byTitle;
    }
  }

  const quoteText = safeText(evidenceQuote);
  if (quoteText) {
    return findSectionByEvidenceQuote(quoteText, sections);
  }

  return null;
}

function buildSectionExcerpt(section: ContractSection | null) {
  if (!section) {
    return null;
  }

  const merged = section.paragraphs.filter(Boolean).join("\n").trim();
  if (!merged) {
    return null;
  }
  if (merged.length <= 420) {
    return merged;
  }
  return `${merged.slice(0, 420).trim()}...`;
}

function getHighestRiskLevel(items: FindingListItem[]) {
  let current: IssueLevel | null = null;
  for (const item of items) {
    if (!item.level) {
      continue;
    }
    if (!current || RISK_PRIORITY[item.level] > RISK_PRIORITY[current]) {
      current = item.level;
    }
  }
  return current;
}

function buildIssueFallbackIndex(issues: IssueItem[] | null | undefined): IssueFallbackEntry[] {
  return (Array.isArray(issues) ? issues : []).map((item) => ({
    item,
    normalizedTitle: normalizeText(item.title),
    normalizedPosition: normalizeText(item.position ?? ""),
    normalizedEvidence: normalizeText(item.evidence ?? "").slice(0, 80),
    suggestion: safeText(item.suggestion) || null,
  }));
}

function findMatchingIssueFallback(
  finding: ClauseOrderedFinding,
  clauseTitle: string,
  issueFallbacks: IssueFallbackEntry[],
) {
  const evidencePosition = normalizeText(finding.evidence_position ?? "");
  const normalizedClauseTitle = normalizeText(clauseTitle);
  const evidenceQuote = normalizeText(finding.evidence_quote ?? "").slice(0, 80);

  if (evidencePosition) {
    const byPosition = issueFallbacks.find(
      (issue) => issue.normalizedPosition === evidencePosition || issue.normalizedTitle.includes(evidencePosition),
    );
    if (byPosition) {
      return byPosition;
    }
  }

  if (normalizedClauseTitle) {
    const byTitle = issueFallbacks.find(
      (issue) => issue.normalizedPosition === normalizedClauseTitle || issue.normalizedTitle.includes(normalizedClauseTitle),
    );
    if (byTitle) {
      return byTitle;
    }
  }

  if (evidenceQuote) {
    return (
      issueFallbacks.find(
        (issue) => issue.normalizedEvidence.includes(evidenceQuote) || evidenceQuote.includes(issue.normalizedEvidence),
      ) ?? null
    );
  }

  return null;
}

function parseChineseNumber(value: string) {
  let result = 0;
  let section = 0;
  let number = 0;

  for (const char of value) {
    if (char in CHINESE_NUMBER_MAP) {
      number = CHINESE_NUMBER_MAP[char];
      continue;
    }

    const unit = CHINESE_UNIT_MAP[char];
    if (!unit) {
      continue;
    }

    if (unit === 10000) {
      section = (section + (number || 0)) * unit;
      result += section;
      section = 0;
      number = 0;
      continue;
    }

    section += (number || (unit === 10 ? 1 : 0)) * unit;
    number = 0;
  }

  return result + section + number;
}

function extractClauseOrder(value: string | null | undefined) {
  const text = safeText(value);
  if (!text) {
    return null;
  }

  const digitMatch = text.match(/第\s*(\d+)\s*条/);
  if (digitMatch) {
    return Number.parseInt(digitMatch[1], 10);
  }

  const chineseMatch = text.match(/第\s*([一二三四五六七八九十百千万两〇零]+)\s*条/);
  if (!chineseMatch) {
    return null;
  }

  const parsed = parseChineseNumber(chineseMatch[1]);
  return parsed > 0 ? parsed : null;
}

function extractClauseTitleFromIssue(issue: IssueItem, index: number) {
  const position = safeText(issue.position);
  if (position) {
    return position;
  }

  const title = safeText(issue.title);
  if (!title) {
    return `重点问题 ${index + 1}`;
  }

  const parts = title.split(/·|•|\||｜/).map((part) => part.trim()).filter(Boolean);
  return parts[parts.length - 1] || title;
}

function createFindingItem(
  finding: ClauseOrderedFinding,
  index: number,
  sections: ContractSection[],
  issueFallbacks: IssueFallbackEntry[],
): FindingListItem {
  const clauseOrder = hasNumber(finding.clause_order) ? finding.clause_order ?? null : null;
  const isMissingItem = isMissingClauseOrder(clauseOrder);
  const clauseTitle = buildClauseTitle(finding, isMissingItem);
  const matchedIssue = findMatchingIssueFallback(finding, clauseTitle, issueFallbacks);
  const clauseType = safeText(finding.clause_type) || null;
  const evidenceQuote = safeText(finding.evidence_quote) || null;
  const evidencePosition = safeText(finding.evidence_position) || null;
  const section = findMatchingContractSection(sections, evidencePosition, clauseTitle, evidenceQuote);
  const revisionSuggestion = safeText(finding.revision_suggestion) || null;
  const proposedAmendment = safeText(finding.proposed_amendment) || null;
  const comparisonSuggestionText = proposedAmendment ?? revisionSuggestion ?? matchedIssue?.suggestion ?? null;
  const level = buildFindingLevel(finding.risk_level);
  const typeLabel = buildTypeLabel(clauseType, `子问题 ${index + 1}`);

  return {
    id: `finding-${index + 1}`,
    sourceIndex: index,
    clauseKey: buildClauseKey(clauseOrder, clauseTitle, isMissingItem, typeLabel, index),
    clauseOrder,
    clauseTitle,
    clauseType,
    typeLabel,
    isMissingItem,
    isExtraRiskTopic: false,
    level,
    riskLabel: getRiskLabelFromLevel(level, isMissingItem),
    riskReason: safeText(finding.risk_reason) || null,
    coreIssue: safeText(finding.core_issue) || null,
    evidenceQuote,
    evidencePosition,
    revisionSuggestion,
    proposedAmendment,
    comparisonSuggestionText,
    needManualReview: resolveNeedManualReview(level, finding.need_manual_review),
    sectionId: section?.id ?? null,
    originalClauseText: evidenceQuote || buildSectionExcerpt(section) || ORIGINAL_CLAUSE_EMPTY,
    topicCategory: null,
    supplementaryNote: null,
    relatedClauseTitles: [],
  };
}

function createFindingItemFromIssue(issue: IssueItem, index: number, sections: ContractSection[]): FindingListItem {
  const clauseTitle = extractClauseTitleFromIssue(issue, index);
  const clauseOrder = extractClauseOrder(issue.position ?? issue.title);
  const evidenceQuote = safeText(issue.evidence) || null;
  const evidencePosition = safeText(issue.position) || null;
  const section = findMatchingContractSection(sections, evidencePosition, clauseTitle, evidenceQuote);
  const proposedAmendment = safeText(issue.revised) || null;
  const revisionSuggestion = safeText(issue.suggestion) || null;

  return {
    id: issue.id || `issue-${index + 1}`,
    sourceIndex: index,
    clauseKey: buildClauseKey(clauseOrder, clauseTitle, false, issue.title, index),
    clauseOrder,
    clauseTitle,
    clauseType: null,
    typeLabel: safeText(issue.title) || `子问题 ${index + 1}`,
    isMissingItem: false,
    isExtraRiskTopic: false,
    level: issue.level,
    riskLabel: getRiskLabelFromLevel(issue.level, false),
    riskReason: safeText(issue.summary) || null,
    coreIssue: safeText(issue.summary) || null,
    evidenceQuote,
    evidencePosition,
    revisionSuggestion,
    proposedAmendment,
    comparisonSuggestionText: proposedAmendment ?? revisionSuggestion ?? null,
    needManualReview: resolveNeedManualReview(issue.level, null),
    sectionId: section?.id ?? null,
    originalClauseText: safeText(issue.original) || evidenceQuote || buildSectionExcerpt(section) || ORIGINAL_CLAUSE_EMPTY,
    topicCategory: null,
    supplementaryNote: null,
    relatedClauseTitles: [],
  };
}

function findSectionByRelatedClauseTitles(relatedClauseTitles: string[], sections: ContractSection[]) {
  for (const title of relatedClauseTitles) {
    const matchedSection = findSectionByTitle(title, sections);
    if (matchedSection) {
      return matchedSection;
    }
  }

  return null;
}

function createFindingItemFromExtraRiskTopic(
  topic: ExtraRiskTopic,
  sourceIndex: number,
  sections: ContractSection[],
): FindingListItem {
  const clauseTitle = safeText(topic.topic_name) || `补充风险主题 ${sourceIndex + 1}`;
  const topicCategory = safeText(topic.topic_category) || null;
  const evidenceQuote = safeText(topic.evidence_quote) || null;
  const evidencePosition = safeText(topic.evidence_position) || null;
  const relatedClauseTitles = Array.isArray(topic.related_clause_titles)
    ? topic.related_clause_titles.map((title) => safeText(title)).filter(Boolean)
    : [];
  const section =
    findMatchingContractSection(sections, evidencePosition, relatedClauseTitles[0] ?? clauseTitle, evidenceQuote) ??
    findSectionByRelatedClauseTitles(relatedClauseTitles, sections);
  const revisionSuggestion = safeText(topic.suggested_action) || null;
  const level = buildFindingLevel(topic.risk_level);

  return {
    id: `extra-risk-${sourceIndex + 1}`,
    sourceIndex,
    clauseKey: buildExtraRiskTopicKey(clauseTitle, topicCategory ?? "补充风险主题", sourceIndex),
    clauseOrder: null,
    clauseTitle,
    clauseType: topicCategory,
    typeLabel: buildTypeLabel(topicCategory, "补充风险主题"),
    isMissingItem: false,
    isExtraRiskTopic: true,
    level,
    riskLabel: getRiskLabelFromLevel(level, false),
    riskReason: null,
    coreIssue: safeText(topic.core_issue) || null,
    evidenceQuote,
    evidencePosition,
    revisionSuggestion,
    proposedAmendment: null,
    comparisonSuggestionText: revisionSuggestion,
    needManualReview: resolveNeedManualReview(level, topic.need_manual_review),
    sectionId: section?.id ?? null,
    originalClauseText: evidenceQuote || buildSectionExcerpt(section) || evidencePosition || ORIGINAL_CLAUSE_EMPTY,
    topicCategory,
    supplementaryNote: safeText(topic.why_not_in_13) || null,
    relatedClauseTitles,
  };
}

function getPrimaryFindingItems(result: ReviewResultResponse | null, sections: ContractSection[]): FindingListItem[] {
  const findings = Array.isArray(result?.clause_ordered_findings) ? result.clause_ordered_findings : [];

  if (findings.length) {
    const issueFallbacks = buildIssueFallbackIndex(result?.issues);
    return findings.map((finding, index) => createFindingItem(finding, index, sections, issueFallbacks));
  }

  const issues = Array.isArray(result?.issues) ? result.issues : [];
  return issues.map((issue, index) => createFindingItemFromIssue(issue, index, sections));
}

function getExtraRiskTopicItems(
  result: ReviewResultResponse | null,
  sections: ContractSection[],
  sourceIndexOffset = 0,
): FindingListItem[] {
  const extraRiskTopics = Array.isArray(result?.extra_risk_topics) ? result.extra_risk_topics : [];
  return extraRiskTopics.map((topic, index) => createFindingItemFromExtraRiskTopic(topic, sourceIndexOffset + index, sections));
}

function hasClauseOrderedFindings(result: ReviewResultResponse | null) {
  return Array.isArray(result?.clause_ordered_findings) && result.clause_ordered_findings.length > 0;
}

export function getOrderedFindings(result: ReviewResultResponse | null): FindingListItem[] {
  const sections = getContractSections(result);
  const primaryItems = getPrimaryFindingItems(result, sections);
  const extraRiskTopicItems = getExtraRiskTopicItems(result, sections, primaryItems.length);

  return [...primaryItems, ...extraRiskTopicItems];
}

function calculateClauseRiskStats(items: FindingListItem[], extraRiskTopicCount: number): ClauseRiskStats | null {
  if (!items.length && extraRiskTopicCount === 0) {
    return null;
  }

  if (!items.length) {
    return {
      high_count: null,
      medium_count: null,
      low_count: null,
      extra_risk_topic_count: extraRiskTopicCount,
    };
  }

  let highCount = 0;
  let mediumCount = 0;
  let lowCount = 0;

  for (const item of items) {
    if (item.level === "high") {
      highCount += 1;
    } else if (item.level === "medium") {
      mediumCount += 1;
    } else if (item.level === "low") {
      lowCount += 1;
    }
  }

  return {
    high_count: highCount,
    medium_count: mediumCount,
    low_count: lowCount,
    extra_risk_topic_count: extraRiskTopicCount,
  };
}

export function getClauseRiskStats(result: ReviewResultResponse | null): ClauseRiskStats | null {
  const sections = getContractSections(result);
  const primaryItems = getPrimaryFindingItems(result, sections);
  const extraRiskTopicItems = getExtraRiskTopicItems(result, sections, primaryItems.length);
  const computed = calculateClauseRiskStats([...primaryItems, ...extraRiskTopicItems], extraRiskTopicItems.length);

  if (hasClauseOrderedFindings(result) || primaryItems.length > 0 || extraRiskTopicItems.length > 0) {
    return computed;
  }

  const primary = result?.clause_risk_stats ?? null;
  if (primary && [primary.high_count, primary.medium_count, primary.low_count, primary.extra_risk_topic_count].some(hasNumber)) {
    return {
      high_count: hasNumber(primary.high_count) ? primary.high_count : computed?.high_count ?? null,
      medium_count: hasNumber(primary.medium_count) ? primary.medium_count : computed?.medium_count ?? null,
      low_count: hasNumber(primary.low_count) ? primary.low_count : computed?.low_count ?? null,
      extra_risk_topic_count:
        extraRiskTopicItems.length > 0
          ? extraRiskTopicItems.length
          : hasNumber(primary.extra_risk_topic_count)
            ? primary.extra_risk_topic_count
            : computed?.extra_risk_topic_count ?? null,
    };
  }

  const fallbackStats = result?.stats ?? null;
  if (fallbackStats && [fallbackStats.high, fallbackStats.medium, fallbackStats.low].some(hasNumber)) {
    return {
      high_count: hasNumber(fallbackStats.high) ? fallbackStats.high : computed?.high_count ?? null,
      medium_count: hasNumber(fallbackStats.medium) ? fallbackStats.medium : computed?.medium_count ?? null,
      low_count: hasNumber(fallbackStats.low) ? fallbackStats.low : computed?.low_count ?? null,
      extra_risk_topic_count: extraRiskTopicItems.length > 0 ? extraRiskTopicItems.length : computed?.extra_risk_topic_count ?? null,
    };
  }

  return computed;
}

export function getOverviewSummary(result: ReviewResultResponse | null): OverviewSummary {
  const stats = getClauseRiskStats(result);
  const findings = getOrderedFindings(result);
  const derivedManualReview = findings.some((item) => item.needManualReview === true) ? true : null;

  return {
    contractType: safeText(result?.contract_type) || safeText(result?.basicInfo?.contractType) || null,
    overallConclusion: safeText(result?.overall_conclusion) || safeText(result?.summary?.conclusion) || null,
    overallRiskLevel: normalizeRiskLevel(result?.overall_risk_level) ?? normalizeRiskLevel(result?.summary?.riskLevel) ?? null,
    needManualReview:
      derivedManualReview === true
        ? true
        : typeof result?.need_manual_review === "boolean"
          ? result.need_manual_review
          : typeof result?.stats?.manualReview === "boolean"
            ? result.stats.manualReview
            : null,
    stats,
    finalReviewReport: safeText(result?.final_review_report) || safeText(result?.fullReport) || null,
  };
}

function isOtherFindingItem(item: FindingListItem) {
  return item.isExtraRiskTopic || item.isMissingItem || item.level === null;
}

export function filterFindingItems(items: FindingListItem[], filter: IssueFilter) {
  if (filter === "all") {
    return items;
  }
  if (filter === "other") {
    return items.filter((item) => isOtherFindingItem(item));
  }
  return items.filter((item) => item.level === filter);
}

export function getFindingFilterCount(
  filter: IssueFilter,
  stats: ClauseRiskStats | null,
  items: FindingListItem[],
) {
  if (filter === "all") {
    return items.length;
  }

  if (filter === "high" && hasNumber(stats?.high_count)) {
    return stats?.high_count ?? 0;
  }
  if (filter === "medium" && hasNumber(stats?.medium_count)) {
    return stats?.medium_count ?? 0;
  }
  if (filter === "low" && hasNumber(stats?.low_count)) {
    return stats?.low_count ?? 0;
  }
  if (filter === "other") {
    return items.filter((item) => isOtherFindingItem(item)).length;
  }

  return items.filter((item) => item.level === filter).length;
}

function isOtherFindingGroup(group: ClauseFindingGroup) {
  return group.isExtraRiskTopic || group.isMissingItem || group.highestLevel === null;
}

function compareClauseGroups(left: ClauseFindingGroup, right: ClauseFindingGroup) {
  const leftIsOther = isOtherFindingGroup(left);
  const rightIsOther = isOtherFindingGroup(right);
  if (leftIsOther !== rightIsOther) {
    return leftIsOther ? 1 : -1;
  }

  if (left.isExtraRiskTopic !== right.isExtraRiskTopic) {
    return left.isExtraRiskTopic ? -1 : 1;
  }

  if (left.isMissingItem !== right.isMissingItem) {
    return left.isMissingItem ? 1 : -1;
  }

  const leftHasOrder = hasNumber(left.clauseOrder) && !left.isMissingItem && !left.isExtraRiskTopic;
  const rightHasOrder = hasNumber(right.clauseOrder) && !right.isMissingItem && !right.isExtraRiskTopic;

  if (leftHasOrder && rightHasOrder && left.clauseOrder !== right.clauseOrder) {
    return (left.clauseOrder ?? 0) - (right.clauseOrder ?? 0);
  }
  if (leftHasOrder !== rightHasOrder) {
    return leftHasOrder ? -1 : 1;
  }

  if (left.sourceIndex !== right.sourceIndex) {
    return left.sourceIndex - right.sourceIndex;
  }

  return normalizeText(left.title).localeCompare(normalizeText(right.title));
}

export function groupFindingsByClause(items: FindingListItem[]): ClauseFindingGroup[] {
  const groups = new Map<string, ClauseFindingGroup>();

  for (const item of items) {
    const existing = groups.get(item.clauseKey);
    if (!existing) {
      groups.set(item.clauseKey, {
        id: item.clauseKey,
        clauseKey: item.clauseKey,
        clauseOrder: item.clauseOrder,
        title: item.clauseTitle,
        isMissingItem: item.isMissingItem,
        isExtraRiskTopic: item.isExtraRiskTopic,
        highestLevel: item.level,
        riskLabel: getRiskLabelFromLevel(item.level, item.isMissingItem),
        needManualReview: item.needManualReview === true,
        sectionId: item.sectionId,
        findings: [item],
        sourceIndex: item.sourceIndex,
      });
      continue;
    }

    existing.findings.push(item);
    existing.sourceIndex = Math.min(existing.sourceIndex, item.sourceIndex);
    existing.clauseOrder = mergeClauseOrder(existing.clauseOrder, item.clauseOrder);
    if (!existing.sectionId && item.sectionId) {
      existing.sectionId = item.sectionId;
    }
    if (item.needManualReview === true) {
      existing.needManualReview = true;
    }
  }

  return Array.from(groups.values())
    .map((group) => {
      const sortedFindings = [...group.findings].sort((left, right) => left.sourceIndex - right.sourceIndex);
      const highestLevel = getHighestRiskLevel(sortedFindings);
      return {
        ...group,
        findings: sortedFindings,
        highestLevel,
        riskLabel: getRiskLabelFromLevel(highestLevel, group.isMissingItem),
      };
    })
    .sort(compareClauseGroups);
}

export function splitClauseGroups(groups: ClauseFindingGroup[]) {
  return {
    regularGroups: groups.filter((group) => !isOtherFindingGroup(group)),
    otherGroups: groups.filter((group) => isOtherFindingGroup(group)),
  };
}

export function resolveFindingTargetSectionId(item: FindingListItem, sections: ContractSection[]) {
  if (item.sectionId) {
    return item.sectionId;
  }
  const section = findMatchingContractSection(sections, item.evidencePosition, item.clauseTitle, item.evidenceQuote);
  return section?.id ?? null;
}

export function resolveClauseGroupTargetSectionId(group: ClauseFindingGroup, sections: ContractSection[]) {
  if (group.sectionId) {
    return group.sectionId;
  }
  for (const finding of group.findings) {
    const sectionId = resolveFindingTargetSectionId(finding, sections);
    if (sectionId) {
      return sectionId;
    }
  }
  return null;
}
