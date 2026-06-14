import Markdown from "@/components/markdown";

export function MarkdownRenderer({ content, className }: { content?: string | null; className?: string }) {
  return <Markdown value={content ?? ""} className={className} />;
}
