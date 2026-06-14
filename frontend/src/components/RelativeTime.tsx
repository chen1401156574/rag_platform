import { formatFullDateTime, formatRelativeTime } from "@/utils/time";

export function RelativeTime({
  value,
  updatedBy
}: {
  value?: string | null;
  updatedBy?: string | null;
}) {
  const relative = formatRelativeTime(value);
  const full = formatFullDateTime(value);

  return (
    <span title={full || undefined} className="inline-flex flex-col gap-0.5 leading-tight">
      <span>{relative}</span>
      {updatedBy ? <span className="text-xs text-muted-foreground">{updatedBy}</span> : null}
    </span>
  );
}
