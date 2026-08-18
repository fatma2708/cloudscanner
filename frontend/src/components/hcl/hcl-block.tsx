import { useMemo } from "react";
import { cn } from "@/lib/utils";

type TokenType =
  | "comment"
  | "string"
  | "number"
  | "keyword"
  | "key"
  | "function"
  | "boolean"
  | "punctuation"
  | "text";

interface Token {
  type: TokenType;
  text: string;
}

const TOKEN_STYLE: Record<TokenType, string> = {
  comment: "text-slate-500 italic",
  string: "text-emerald-300",
  number: "text-amber-300",
  keyword: "text-violet-400 font-medium",
  key: "text-sky-300",
  function: "text-pink-300",
  boolean: "text-amber-300",
  punctuation: "text-slate-500",
  text: "text-slate-300",
};

const BLOCK_KEYWORDS = new Set([
  "resource",
  "data",
  "variable",
  "output",
  "provider",
  "terraform",
  "module",
  "locals",
  "backend",
  "moved",
  "import",
  "check",
  "required_providers",
]);

const MASTER = new RegExp(
  [
    "(/\\*[\\s\\S]*?\\*/)", // 1 block comment
    "((?:#|//)[^\\n]*)", // 2 line comment
    '("(?:\\\\.|[^"\\\\])*")', // 3 string
    "(-?\\b\\d+(?:\\.\\d+)?\\b)", // 4 number
    "(\\b(?:true|false|null)\\b)", // 5 boolean
    "(\\$\\{[\\s\\S]*?\\})", // 6 interpolation (outside strings)
    "(\\b[A-Za-z_][\\w]*)(?=\\s*(?:[\\w-]+\\s*)?\\{)", // 7 block keyword
    "(\\b[A-Za-z_][\\w-]*)(?=\\s*=)", // 8 attribute key
    "(\\b[A-Za-z_][\\w]*(?=\\())", // 9 function call
  ].join("|"),
  "gm",
);

function tokenize(code: string): Token[] {
  const tokens: Token[] = [];
  const re = new RegExp(MASTER.source, "gm");
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(code)) !== null) {
    if (match.index > last) {
      tokens.push({ type: "text", text: code.slice(last, match.index) });
    }
    let type: TokenType = "text";
    if (match[1]) type = "comment";
    else if (match[2]) type = "comment";
    else if (match[3]) type = "string";
    else if (match[4]) type = "number";
    else if (match[5]) type = "boolean";
    else if (match[6]) type = "string";
    else if (match[7]) {
      type = BLOCK_KEYWORDS.has(match[7]) ? "keyword" : "text";
      // Block types that aren't keywords (aws_instance, aws_s3_bucket) render as text.
    } else if (match[8]) type = "key";
    else if (match[9]) type = "function";
    tokens.push({ type, text: match[0] });
    last = match.index + match[0].length;
  }
  if (last < code.length) tokens.push({ type: "text", text: code.slice(last) });
  return tokens;
}

interface HclBlockProps {
  code: string;
  maxHeight?: number;
  className?: string;
}

export function HclBlock({ code, maxHeight, className }: HclBlockProps) {
  const tokens = useMemo(() => tokenize(code), [code]);
  return (
    <pre
      className={cn(
        "overflow-auto rounded-lg border border-border bg-zinc-950 p-4 font-mono text-[12.5px] leading-relaxed",
        className,
      )}
      style={maxHeight ? { maxHeight } : undefined}
    >
      <code>
        {tokens.map((tok, i) => (
          <span key={i} className={TOKEN_STYLE[tok.type]}>
            {tok.text}
          </span>
        ))}
      </code>
    </pre>
  );
}
