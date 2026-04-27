interface StartReviewButtonProps {
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
}

const START_LABEL = "开始审查";
const LOADING_LABEL = "正在启动审查...";

export function StartReviewButton({ disabled, loading, onClick }: StartReviewButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className="primary-action min-w-[160px] px-6 py-3.5 disabled:cursor-not-allowed disabled:border-transparent disabled:bg-[#94a3b8]"
    >
      {loading ? LOADING_LABEL : START_LABEL}
    </button>
  );
}
