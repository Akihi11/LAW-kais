"use client";

import { useRef, useState } from "react";

import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE_MB } from "@/lib/constants";
import { formatFileSize } from "@/lib/review-helpers";

interface UploadPanelProps {
  selectedFile: File | null;
  onFileSelect: (file: File | null) => void;
  errorMessage: string | null;
}

const TITLE = "拖拽上传或点击选择文件";
const DESCRIPTION = "支持 .docx / .pdf，文件通过后将进入解析、审查与结果生成流程。";
const PICK_FILE = "选择合同文件";
const FILE_HELPER = `单个文件不超过 ${MAX_FILE_SIZE_MB}MB，支持 .docx / .pdf`;
const EMPTY_FILE = "当前未选择合同文件";
const CLEAR_FILE = "清除当前文件";
const UPLOADED_PREFIX = "已选择：";
const ERROR_TITLE = "上传校验未通过";

export function UploadPanel({ selectedFile, onFileSelect, errorMessage }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          const file = event.dataTransfer.files?.[0] ?? null;
          onFileSelect(file);
        }}
        className={`flex min-h-[320px] flex-1 flex-col justify-center gap-4 rounded-[22px] border border-dashed p-8 transition sm:p-10 ${
          isDragging ? "border-[#60a5fa] bg-[#eef6ff]" : "border-[#93c5fd] bg-[#f8fbff]"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FILE_TYPES}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0] ?? null;
            onFileSelect(file);
          }}
        />

        <div className="space-y-3">
          <p className="text-[24px] font-extrabold text-[#0f2345]">{TITLE}</p>
          <p className="max-w-[720px] text-base leading-8 text-[#64748b]">{DESCRIPTION}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => inputRef.current?.click()} className="primary-action px-5 py-3">
            {PICK_FILE}
          </button>
          <span className="text-sm text-[#64748b]">{FILE_HELPER}</span>
        </div>

        <div className="inline-flex min-h-[58px] w-full max-w-[760px] items-center rounded-[16px] border border-[#e5e7eb] bg-white px-4 text-[16px] text-[#334155]">
          {selectedFile ? `${UPLOADED_PREFIX}${selectedFile.name}（${formatFileSize(selectedFile.size)}）` : EMPTY_FILE}
        </div>

        {selectedFile ? (
          <button
            type="button"
            onClick={() => {
              onFileSelect(null);
              if (inputRef.current) {
                inputRef.current.value = "";
              }
            }}
            className="w-fit text-sm font-semibold text-[#2563eb] transition hover:text-[#1d4ed8]"
          >
            {CLEAR_FILE}
          </button>
        ) : null}
      </div>

      {errorMessage ? (
        <div className="info-banner info-banner-error">
          <p className="font-semibold">{ERROR_TITLE}</p>
          <p className="mt-1">{errorMessage}</p>
        </div>
      ) : null}
    </div>
  );
}
