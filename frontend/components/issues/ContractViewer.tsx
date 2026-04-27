"use client";

import { useEffect, useRef } from "react";

import { ContractSection } from "@/lib/types";

interface ContractViewerProps {
  sections: ContractSection[];
  activeSectionId: string | null;
  activeSignal?: number;
}

const TITLE = "合同原文";
const EMPTY = "暂未返回可定位的合同原文。";

export function ContractViewer({ sections, activeSectionId, activeSignal = 0 }: ContractViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!activeSectionId) {
      return;
    }

    const container = containerRef.current;
    const target = sectionRefs.current[activeSectionId];
    if (!container || !target) {
      return;
    }

    const containerBox = container.getBoundingClientRect();
    const targetBox = target.getBoundingClientRect();
    const paddingTop = Number.parseFloat(window.getComputedStyle(container).paddingTop) || 0;
    const topOffset = paddingTop + 12;
    const nextScrollTop = container.scrollTop + (targetBox.top - containerBox.top) - topOffset;

    container.scrollTo({
      top: Math.max(nextScrollTop, 0),
      behavior: "smooth",
    });
  }, [activeSectionId, activeSignal]);

  return (
    <section className="glass-card flex h-[1240px] flex-col self-start p-5 sm:h-[1360px] sm:p-6 xl:h-[calc(200vh-352px)] xl:max-h-[1720px]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 className="text-[22px] font-extrabold text-[#0f2345]">{TITLE}</h2>
        {activeSectionId ? (
          <span className="status-pill border border-[#e5e7eb] bg-white text-[#64748b]">联动定位中</span>
        ) : null}
      </div>

      <div
        ref={containerRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-[18px] border border-[#e5e7eb] bg-[#f8fafc] p-4"
      >
        {!sections.length ? (
          <div className="empty-state-card">{EMPTY}</div>
        ) : (
          <div className="space-y-3">
            {sections.map((section, index) => {
              const isActive = section.id === activeSectionId;
              const domId = `contract-section-${section.id || index + 1}`;
              const shouldShowTitle = !(index === 0 && section.title.trim() === TITLE);

              return (
                <div
                  key={section.id || domId}
                  id={domId}
                  data-section-id={section.id}
                  ref={(node) => {
                    sectionRefs.current[section.id] = node;
                  }}
                  className={`rounded-[16px] border px-4 py-4 transition ${
                    isActive
                      ? "border-[#facc15] bg-[#fff7d6] shadow-[0_0_0_4px_rgba(250,204,21,0.18)]"
                      : "border-transparent bg-white"
                  }`}
                >
                  {shouldShowTitle ? (
                    <h3 className="text-[18px] font-extrabold text-[#0f2345]">{section.title}</h3>
                  ) : null}
                  <div className={`${shouldShowTitle ? "mt-3 " : ""}space-y-2 text-[15px] leading-8 text-[#334155]`}>
                    {section.paragraphs.map((paragraph, paragraphIndex) => (
                      <p key={`${section.id}-${paragraphIndex}`}>{paragraph}</p>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
