import fs from "node:fs";
import path from "node:path";
import { marked } from "marked";

export const dynamic = "force-dynamic";

export default function MethodologyPage() {
  const filePath = path.join(process.cwd(), "..", "METHODOLOGY.md");
  const content = fs.readFileSync(filePath, "utf-8");
  const html = marked.parse(content, { async: false }) as string;

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <div
        className="markdown-body"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
