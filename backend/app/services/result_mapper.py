from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.schemas.domain import IssueLevel, TaskRecord, TaskStatus, WorkflowExecutionStatus
from app.utils.workflow_display import sort_workflow_node_payloads
from app.schemas.response import ReviewResultResponse


JSON_PATH = tuple[str, ...]


def build_default_workflow_groups() -> list[dict[str, Any]]:
    return [
        {
            "name": "文件收集",
            "status": WorkflowExecutionStatus.DONE.value,
            "nodes": [
                {"name": "文件收集", "status": WorkflowExecutionStatus.DONE.value},
                {"name": "文件类型判断", "status": WorkflowExecutionStatus.DONE.value},
                {"name": "文档解析", "status": WorkflowExecutionStatus.DONE.value},
            ],
        },
        {
            "name": "合同审查",
            "status": WorkflowExecutionStatus.DONE.value,
            "nodes": [
                {"name": "条款抽取", "status": WorkflowExecutionStatus.DONE.value},
                {"name": "风险分析", "status": WorkflowExecutionStatus.DONE.value},
                {"name": "报告生成", "status": WorkflowExecutionStatus.DONE.value},
            ],
        },
    ]


class ResultMapper:
    def map_result(self, task: TaskRecord, raw_payload: Any) -> ReviewResultResponse:
        payload = self._normalize_raw_payload(raw_payload)
        sources = self._collect_sources(payload)
        source_document_text = self._extract_source_document_text(payload)

        contract_type = self._coalesce(
            self._string_or_none(self._value_from_paths(sources, ("contract_type",))),
            self._string_or_none(self._value_from_paths(sources, ("contractType",))),
            self._string_or_none(self._value_from_paths(sources, ("basicInfo", "contractType"))),
        )
        overall_conclusion = self._coalesce(
            self._string_or_none(self._value_from_paths(sources, ("overall_conclusion",))),
            self._string_or_none(self._value_from_paths(sources, ("overallConclusion",))),
            self._string_or_none(self._value_from_paths(sources, ("summary", "conclusion"))),
            self._string_or_none(self._value_from_paths(sources, ("conclusion",))),
        )
        overall_risk_level = self._normalize_risk_level(
            self._value_from_paths(
                sources,
                ("overall_risk_level",),
                ("overallRiskLevel",),
                ("summary", "riskLevel"),
                ("riskLevel",),
            )
        )
        findings = self._extract_clause_ordered_findings(sources)
        extra_risk_topics = self._extract_extra_risk_topics(sources)
        issues = self._extract_legacy_issues(sources, findings)
        clause_risk_stats = self._extract_clause_risk_stats(sources, findings, extra_risk_topics, issues)
        need_manual_review = self._extract_need_manual_review(sources, findings, extra_risk_topics)
        final_review_report = self._extract_final_review_report(sources)
        workflow = self._extract_workflow(sources)
        contract_sections = self._normalize_contract_sections(
            self._value_from_paths(sources, ("contractSections",)),
            source_document_text,
        )
        basic_info = self._extract_basic_info(task, sources, contract_type)

        return ReviewResultResponse.model_validate(
            {
                "taskId": task.task_id,
                "status": TaskStatus.SUCCEEDED.value,
                "contract_type": contract_type,
                "overall_conclusion": overall_conclusion,
                "overall_risk_level": overall_risk_level,
                "need_manual_review": need_manual_review,
                "clause_risk_stats": clause_risk_stats,
                "clause_ordered_findings": findings,
                "extra_risk_topics": extra_risk_topics,
                "final_review_report": final_review_report,
                "workflow": workflow,
                "contractSections": contract_sections,
                "basicInfo": basic_info,
                "summary": {
                    "riskLevel": overall_risk_level,
                    "conclusion": overall_conclusion,
                },
                "stats": {
                    "high": clause_risk_stats.get("high_count") if clause_risk_stats else None,
                    "medium": clause_risk_stats.get("medium_count") if clause_risk_stats else None,
                    "low": clause_risk_stats.get("low_count") if clause_risk_stats else None,
                    "manualReview": need_manual_review,
                },
                "fullReport": final_review_report,
                "issues": issues,
            }
        )

    def _normalize_raw_payload(self, raw_payload: Any) -> dict[str, Any]:
        if isinstance(raw_payload, dict):
            return {str(key): value for key, value in raw_payload.items()}
        if isinstance(raw_payload, str):
            parsed = self._maybe_parse_json(raw_payload)
            if isinstance(parsed, dict):
                return parsed
            return {"reportText": raw_payload}
        return {"reportText": self._stringify(raw_payload)}

    def _collect_sources(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        seen: set[str] = set()

        def append_candidate(candidate: Any) -> None:
            if isinstance(candidate, str):
                parsed = self._maybe_parse_json(candidate)
                if isinstance(parsed, dict):
                    append_candidate(parsed)
                return

            if not isinstance(candidate, dict):
                return

            cleaned = {str(key): value for key, value in candidate.items() if not str(key).startswith("_")}
            fingerprint = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, default=str)
            if fingerprint in seen:
                return

            seen.add(fingerprint)
            sources.append(cleaned)

            for nested_key in ("report_material", "result", "data", "output", "review_result"):
                append_candidate(cleaned.get(nested_key))

            for text_key in ("reportText", "fullReport", "analysis", "final_review_report"):
                append_candidate(cleaned.get(text_key))

        append_candidate(payload)
        return sources

    def _extract_basic_info(self, task: TaskRecord, sources: list[dict[str, Any]], contract_type: str | None) -> dict[str, Any]:
        contract_name = self._coalesce(
            self._string_or_none(self._value_from_paths(sources, ("contract_name",))),
            self._string_or_none(self._value_from_paths(sources, ("contractName",))),
            self._string_or_none(self._value_from_paths(sources, ("basicInfo", "contractName"))),
        )
        return {
            "contractName": contract_name or None,
            "contractType": contract_type,
            "perspective": task.review_role.value,
        }

    def _extract_workflow(self, sources: list[dict[str, Any]]) -> dict[str, Any] | None:
        groups = self._value_from_paths(sources, ("workflow", "groups"), ("workflowGroups",))
        if isinstance(groups, list):
            normalized_groups = self._normalize_workflow_groups(groups)
            if normalized_groups:
                return {"groups": normalized_groups}

        steps = self._value_from_paths(sources, ("steps",))
        if isinstance(steps, list) and steps:
            return {"groups": self._workflow_from_steps(steps)}

        return None

    def _extract_clause_ordered_findings(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw_findings = self._value_from_paths(sources, ("clause_ordered_findings",))
        if isinstance(raw_findings, list):
            normalized = self._normalize_findings(raw_findings)
            if normalized:
                return normalized

        evidence_index = self._value_from_paths(sources, ("evidence_index",))
        if isinstance(evidence_index, list):
            normalized = self._normalize_findings(evidence_index)
            if normalized:
                return normalized

        return []

    def _extract_extra_risk_topics(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw_topics = self._value_from_paths(sources, ("extra_risk_topics",))
        if isinstance(raw_topics, list):
            return self._normalize_extra_risk_topics(raw_topics)
        return []

    def _normalize_findings(self, findings: list[Any], default_missing_clause_order: bool = False) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for item in findings:
            if not isinstance(item, dict):
                continue

            clause_order = self._normalize_clause_order(item.get("clause_order") or item.get("clauseOrder"))
            if clause_order is None and default_missing_clause_order:
                clause_order = 99999

            clause_title = self._coalesce(
                self._string_or_none(item.get("clause_title")),
                self._string_or_none(item.get("clauseTitle")),
                self._string_or_none(item.get("title")),
                self._string_or_none(item.get("topic_name")),
                self._string_or_none(item.get("item_name")),
                self._string_or_none(item.get("mechanism_name")),
            )
            clause_type = self._coalesce(
                self._string_or_none(item.get("clause_type")),
                self._string_or_none(item.get("clauseType")),
                self._string_or_none(item.get("topic_category")),
            )
            core_issue = self._coalesce(
                self._string_or_none(item.get("core_issue")),
                self._string_or_none(item.get("coreIssue")),
                self._string_or_none(item.get("finding")),
                self._string_or_none(item.get("summary")),
            )
            evidence_position = self._coalesce(
                self._string_or_none(item.get("evidence_position")),
                self._string_or_none(item.get("evidencePosition")),
            )
            evidence_quote = self._coalesce(
                self._string_or_none(item.get("evidence_quote")),
                self._string_or_none(item.get("evidenceQuote")),
            )
            need_manual_review = self._read_bool(
                item.get("need_manual_review")
                if "need_manual_review" in item
                else item.get("needManualReview")
            )
            revision_suggestion = self._coalesce(
                self._string_or_none(item.get("revision_suggestion")),
                self._string_or_none(item.get("revisionSuggestion")),
                self._string_or_none(item.get("suggestion")),
                self._string_or_none(item.get("suggested_action")),
                self._string_or_none(item.get("action")),
                self._string_or_none(item.get("suggested_direction")),
            )
            proposed_amendment = self._coalesce(
                self._string_or_none(item.get("proposed_amendment")),
                self._string_or_none(item.get("proposedAmendment")),
            )
            risk_level = self._normalize_risk_level(item.get("risk_level") or item.get("riskLevel"))
            risk_reason = self._coalesce(
                self._string_or_none(item.get("risk_reason")),
                self._string_or_none(item.get("riskReason")),
                self._string_or_none(item.get("why_not_in_13")),
                self._string_or_none(item.get("core_reason")),
                self._string_or_none(item.get("finding")),
            )

            normalized.append(
                {
                    "clause_order": clause_order,
                    "clause_title": clause_title or ("关键缺失项" if clause_order == 99999 else None),
                    "clause_type": clause_type or None,
                    "core_issue": core_issue or None,
                    "evidence_position": evidence_position or None,
                    "evidence_quote": evidence_quote or None,
                    "need_manual_review": need_manual_review,
                    "revision_suggestion": revision_suggestion or None,
                    "proposed_amendment": proposed_amendment or None,
                    "risk_level": risk_level,
                    "risk_reason": risk_reason or None,
                }
            )

        return normalized

    def _normalize_extra_risk_topics(self, topics: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for item in topics:
            if not isinstance(item, dict):
                continue

            related_clause_titles = item.get("related_clause_titles")
            if not isinstance(related_clause_titles, list):
                related_clause_titles = item.get("relatedClauseTitles")

            normalized.append(
                {
                    "topic_name": self._coalesce(
                        self._string_or_none(item.get("topic_name")),
                        self._string_or_none(item.get("topicName")),
                        self._string_or_none(item.get("title")),
                        self._string_or_none(item.get("item_name")),
                    )
                    or None,
                    "topic_category": self._coalesce(
                        self._string_or_none(item.get("topic_category")),
                        self._string_or_none(item.get("topicCategory")),
                        self._string_or_none(item.get("category")),
                        self._string_or_none(item.get("type")),
                    )
                    or None,
                    "core_issue": self._coalesce(
                        self._string_or_none(item.get("core_issue")),
                        self._string_or_none(item.get("coreIssue")),
                        self._string_or_none(item.get("finding")),
                        self._string_or_none(item.get("summary")),
                    )
                    or None,
                    "evidence_position": self._coalesce(
                        self._string_or_none(item.get("evidence_position")),
                        self._string_or_none(item.get("evidencePosition")),
                    )
                    or None,
                    "evidence_quote": self._coalesce(
                        self._string_or_none(item.get("evidence_quote")),
                        self._string_or_none(item.get("evidenceQuote")),
                    )
                    or None,
                    "suggested_action": self._coalesce(
                        self._string_or_none(item.get("suggested_action")),
                        self._string_or_none(item.get("suggestedAction")),
                        self._string_or_none(item.get("action")),
                        self._string_or_none(item.get("revision_suggestion")),
                        self._string_or_none(item.get("revisionSuggestion")),
                    )
                    or None,
                    "need_manual_review": self._read_bool(
                        item.get("need_manual_review")
                        if "need_manual_review" in item
                        else item.get("needManualReview")
                    ),
                    "risk_level": self._normalize_risk_level(item.get("risk_level") or item.get("riskLevel")),
                    "why_not_in_13": self._coalesce(
                        self._string_or_none(item.get("why_not_in_13")),
                        self._string_or_none(item.get("whyNotIn13")),
                    )
                    or None,
                    "related_clause_titles": self._normalize_string_list(related_clause_titles),
                }
            )

        return normalized

    def _extract_clause_risk_stats(
        self,
        sources: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        extra_risk_topics: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        raw_stats = self._value_from_paths(sources, ("clause_risk_stats",))
        computed_stats = self._compute_clause_risk_stats(findings)
        issue_stats = self._compute_issue_level_stats(issues) if not findings else None

        high_count = computed_stats.get("high_count")
        medium_count = computed_stats.get("medium_count")
        low_count = computed_stats.get("low_count")

        if high_count is None and issue_stats is not None:
            high_count = issue_stats.get("high_count")
        if medium_count is None and issue_stats is not None:
            medium_count = issue_stats.get("medium_count")
        if low_count is None and issue_stats is not None:
            low_count = issue_stats.get("low_count")

        extra_risk_topic_count = len(extra_risk_topics)

        if isinstance(raw_stats, dict):
            if high_count is None:
                high_count = self._read_int(raw_stats.get("high_count"))
            if medium_count is None:
                medium_count = self._read_int(raw_stats.get("medium_count"))
            if low_count is None:
                low_count = self._read_int(raw_stats.get("low_count"))

            extra_count = self._read_int(raw_stats.get("extra_risk_topic_count"))
            if extra_risk_topic_count == 0 and extra_count is not None:
                extra_risk_topic_count = extra_count

        return {
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "extra_risk_topic_count": extra_risk_topic_count,
        }

    def _compute_clause_risk_stats(self, findings: list[dict[str, Any]]) -> dict[str, int | None]:
        if not findings:
            return {
                "high_count": None,
                "medium_count": None,
                "low_count": None,
            }

        high_count = 0
        medium_count = 0
        low_count = 0

        for finding in findings:
            risk_level = self._normalize_risk_level(finding.get("risk_level"))
            if risk_level == "高":
                high_count += 1
            elif risk_level == "中":
                medium_count += 1
            elif risk_level == "低":
                low_count += 1

        return {
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
        }

    def _compute_issue_level_stats(self, issues: list[dict[str, Any]]) -> dict[str, int | None] | None:
        if not issues:
            return None

        high_count = 0
        medium_count = 0
        low_count = 0

        for issue in issues:
            level = self._stringify(issue.get("level")).lower()
            if level == IssueLevel.HIGH.value:
                high_count += 1
            elif level == IssueLevel.MEDIUM.value:
                medium_count += 1
            elif level == IssueLevel.LOW.value:
                low_count += 1

        return {
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
        }

    def _extract_need_manual_review(
        self,
        sources: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        extra_risk_topics: list[dict[str, Any]],
    ) -> bool | None:
        direct_value = self._value_from_paths(
            sources,
            ("need_manual_review",),
            ("manual_review_decision", "need_manual_review"),
            ("stats", "manualReview"),
            ("manualReview",),
        )
        parsed_direct = self._read_bool(direct_value)
        if parsed_direct is not None:
            return parsed_direct

        review_flags = [
            item.get("need_manual_review")
            for item in [*findings, *extra_risk_topics]
            if item.get("need_manual_review") is not None
        ]
        if review_flags:
            return any(bool(value) for value in review_flags)

        return None

    def _extract_final_review_report(self, sources: list[dict[str, Any]]) -> str | None:
        report = self._string_or_none(self._value_from_paths(sources, ("final_review_report",)))
        if report:
            return report

        for path in (("fullReport",), ("reportText",), ("analysis",)):
            candidate = self._string_or_none(self._value_from_paths(sources, path))
            if not candidate:
                continue
            parsed = self._maybe_parse_json(candidate)
            if isinstance(parsed, (dict, list)):
                continue
            return candidate

        return None

    def _extract_legacy_issues(self, sources: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if findings:
            return self._build_legacy_issues(findings)

        raw_issues = self._value_from_paths(sources, ("issues",))
        if isinstance(raw_issues, list):
            return self._normalize_legacy_issues(raw_issues)
        return []

    def _normalize_legacy_issues(self, raw_issues: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for index, item in enumerate(raw_issues, start=1):
            if not isinstance(item, dict):
                continue

            title = self._coalesce(
                self._string_or_none(item.get("title")),
                self._string_or_none(item.get("position")),
                f"重点问题 {index}",
            )
            risk_value = item.get("level") if item.get("level") is not None else item.get("risk_level") or item.get("riskLevel")
            proposed_amendment = self._coalesce(
                self._string_or_none(item.get("proposed_amendment")),
                self._string_or_none(item.get("proposedAmendment")),
                self._string_or_none(item.get("revised")),
            )
            revision_suggestion = self._coalesce(
                proposed_amendment,
                self._string_or_none(item.get("suggestion")),
                self._string_or_none(item.get("revision_suggestion")),
            )
            normalized.append(
                {
                    "id": self._string_or_none(item.get("id")) or f"issue_{index:03d}",
                    "title": title,
                    "level": self._normalize_issue_level(risk_value, False),
                    "position": self._string_or_none(item.get("position")),
                    "summary": self._coalesce(
                        self._string_or_none(item.get("summary")),
                        self._string_or_none(item.get("risk_reason")),
                        self._string_or_none(item.get("core_issue")),
                    )
                    or None,
                    "evidence": self._coalesce(
                        self._string_or_none(item.get("evidence")),
                        self._string_or_none(item.get("evidence_quote")),
                        self._string_or_none(item.get("evidence_position")),
                    )
                    or None,
                    "suggestion": revision_suggestion or None,
                    "original": self._string_or_none(item.get("original")),
                    "revised": proposed_amendment,
                    "anchor": self._string_or_none(item.get("anchor")),
                }
            )

        return normalized

    def _build_legacy_issues(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        for index, finding in enumerate(findings, start=1):
            clause_order = finding.get("clause_order")
            clause_title = finding.get("clause_title")
            is_missing_item = clause_order == 99999
            title_parts: list[str] = []
            if isinstance(clause_order, int) and clause_order > 0 and not is_missing_item:
                title_parts.append(f"第{clause_order}条")
            if clause_title:
                title_parts.append(str(clause_title))
            title = " - ".join(title_parts) or ("关键缺失项" if is_missing_item else f"重点问题 {index}")
            evidence = self._coalesce(
                self._string_or_none(finding.get("evidence_quote")),
                self._string_or_none(finding.get("evidence_position")),
            )
            proposed_amendment = self._string_or_none(finding.get("proposed_amendment"))
            revision_suggestion = self._coalesce(
                proposed_amendment,
                self._string_or_none(finding.get("revision_suggestion")),
            )
            issues.append(
                {
                    "id": f"issue_{index:03d}",
                    "title": title,
                    "level": self._normalize_issue_level(finding.get("risk_level"), is_missing_item),
                    "position": self._string_or_none(finding.get("evidence_position")),
                    "summary": self._coalesce(
                        self._string_or_none(finding.get("risk_reason")),
                        self._string_or_none(finding.get("core_issue")),
                    )
                    or None,
                    "evidence": evidence or None,
                    "suggestion": revision_suggestion or None,
                    "original": None,
                    "revised": proposed_amendment,
                    "anchor": f"issue-anchor-{index}",
                }
            )

        return issues

    def _normalize_contract_sections(self, sections_value: Any, source_document_text: str) -> list[dict[str, Any]]:
        if isinstance(sections_value, list):
            normalized: list[dict[str, Any]] = []
            for index, section in enumerate(sections_value, start=1):
                if not isinstance(section, dict):
                    continue
                title = self._coalesce(self._string_or_none(section.get("title")), f"第 {index} 部分")
                paragraphs = section.get("paragraphs")
                if not isinstance(paragraphs, list):
                    paragraphs = []
                normalized.append(
                    {
                        "id": self._coalesce(self._string_or_none(section.get("id")), f"section-{index}"),
                        "title": title,
                        "paragraphs": [str(paragraph).strip() for paragraph in paragraphs if str(paragraph).strip()],
                    }
                )
            if normalized:
                return normalized

        return self._build_contract_sections(source_document_text)

    def _build_contract_sections(self, text: str) -> list[dict[str, Any]]:
        normalized_text = text.strip()
        if not normalized_text:
            return []

        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for line in lines:
            if self._looks_like_contract_heading(line):
                if current is not None and current["paragraphs"]:
                    sections.append(current)
                current = {
                    "id": f"section-{len(sections) + 1}",
                    "title": line,
                    "paragraphs": [],
                }
                continue

            if current is None:
                current = {
                    "id": "section-1",
                    "title": "合同原文",
                    "paragraphs": [],
                }
            current["paragraphs"].append(line)

        if current is not None and current["paragraphs"]:
            sections.append(current)

        if sections:
            return sections[:30]

        return [
            {
                "id": "section-1",
                "title": "合同原文",
                "paragraphs": lines[:30],
            }
        ]

    def _extract_source_document_text(self, payload: dict[str, Any]) -> str:
        source = payload.get("_source_document_text")
        return self._stringify(source)

    def _workflow_from_steps(self, steps: list[Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for step in steps[:24]:
            if not isinstance(step, dict):
                continue
            name = self._coalesce(
                self._string_or_none(step.get("name")),
                self._string_or_none(step.get("title")),
                self._string_or_none(step.get("id")),
                "未命名节点",
            )
            status = self._coalesce(
                self._string_or_none(step.get("status")),
                WorkflowExecutionStatus.DONE.value,
            )
            nodes.append({"name": name, "status": status})

        ordered_nodes = sort_workflow_node_payloads(nodes)
        if not ordered_nodes:
            return []

        return [
            {
                "name": "平台执行轨迹",
                "status": self._derive_workflow_group_status(ordered_nodes),
                "nodes": ordered_nodes,
            }
        ]

    def _normalize_workflow_groups(self, groups: list[Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        group_name = ""

        for group in groups:
            if not isinstance(group, dict):
                continue
            if not group_name:
                group_name = self._string_or_none(group.get("name")) or ""
            raw_nodes = group.get("nodes")
            if not isinstance(raw_nodes, list):
                continue
            for node in raw_nodes:
                if not isinstance(node, dict):
                    continue
                node_name = self._coalesce(
                    self._string_or_none(node.get("name")),
                    self._string_or_none(node.get("title")),
                    self._string_or_none(node.get("id")),
                    "未命名节点",
                )
                node_status = self._coalesce(
                    self._string_or_none(node.get("status")),
                    WorkflowExecutionStatus.PENDING.value,
                )
                nodes.append({"name": node_name, "status": node_status})

        ordered_nodes = sort_workflow_node_payloads(nodes)
        if not ordered_nodes:
            return []

        return [
            {
                "name": group_name or "平台执行轨迹",
                "status": self._derive_workflow_group_status(ordered_nodes),
                "nodes": ordered_nodes,
            }
        ]

    def _derive_workflow_group_status(self, nodes: list[dict[str, Any]]) -> str:
        statuses = {self._stringify(node.get("status")).lower() for node in nodes}
        if WorkflowExecutionStatus.FAILED.value in statuses:
            return WorkflowExecutionStatus.FAILED.value
        if WorkflowExecutionStatus.RUNNING.value in statuses:
            return WorkflowExecutionStatus.RUNNING.value
        if statuses and statuses.issubset({WorkflowExecutionStatus.DONE.value}):
            return WorkflowExecutionStatus.DONE.value
        return WorkflowExecutionStatus.PENDING.value

    def _value_from_paths(self, sources: list[dict[str, Any]], *paths: JSON_PATH) -> Any:
        for source in sources:
            for path in paths:
                value = self._get_nested(source, path)
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                return value
        return None

    def _get_nested(self, candidate: Any, path: JSON_PATH) -> Any:
        current = candidate
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _normalize_clause_order(self, value: Any) -> int | None:
        parsed = self._read_int(value)
        if parsed is None:
            return None
        if parsed >= 99999:
            return 99999
        return parsed

    def _normalize_risk_level(self, value: Any) -> str | None:
        text = self._stringify(value).lower()
        if not text:
            return None
        if text in {"high", "高", "高风险"}:
            return "高"
        if text in {"medium", "中", "中风险"}:
            return "中"
        if text in {"low", "低", "低风险"}:
            return "低"
        return None

    def _normalize_issue_level(self, value: Any, is_missing_item: bool) -> str:
        normalized = self._normalize_risk_level(value)
        if normalized == "高":
            return IssueLevel.HIGH.value
        if normalized == "中":
            return IssueLevel.MEDIUM.value
        if normalized == "低":
            return IssueLevel.LOW.value
        return IssueLevel.HIGH.value if is_missing_item else IssueLevel.MEDIUM.value

    def _maybe_parse_json(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        text = value.strip()
        if not text:
            return ""

        candidates = [text]
        fenced_blocks = re.findall(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
        candidates.extend(fenced_blocks)

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        return text

    def _read_int(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+", value)
            if match:
                return int(match.group())
        return None

    def _read_bool(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "是"}:
                return True
            if normalized in {"false", "0", "no", "n", "否"}:
                return False
        return None

    def _looks_like_contract_heading(self, text: str) -> bool:
        return bool(re.match(r"^(第[一二三四五六七八九十百千万0-9]+[条章节部分]|[一二三四五六七八九十]+、)", text))

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _string_or_none(self, value: Any) -> str | None:
        text = self._stringify(value)
        return text or None

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for text in (self._stringify(item) for item in value) if text]

    @staticmethod
    def _coalesce(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
