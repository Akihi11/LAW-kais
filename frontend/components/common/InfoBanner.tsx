interface InfoBannerProps {
  tone?: "info" | "warning" | "error";
  title: string;
  description?: string;
}

export function InfoBanner({
  tone = "info",
  title,
  description,
}: InfoBannerProps) {
  const toneClassName =
    tone === "error"
      ? "info-banner-error"
      : tone === "warning"
        ? "info-banner-warning"
        : "info-banner-info";

  return (
    <div className={`info-banner ${toneClassName}`}>
      <p className="font-semibold">{title}</p>
      {description ? <p className="mt-1 text-sm leading-7">{description}</p> : null}
    </div>
  );
}