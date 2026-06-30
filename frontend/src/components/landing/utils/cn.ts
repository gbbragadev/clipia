// Minimal clsx-equivalent (sem deps). Suporta string/number, arrays, objetos
// {classe: bool} e valores falsy. Sem tailwind-merge — se um conflito real de
// utilitário aparecer no QA, dá pra trocar por twMerge. ponytail: 12 linhas > 2 deps.
type ClassValue = string | number | false | null | undefined | ClassValue[] | Record<string, boolean | undefined | null>;

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const input of inputs) {
    if (!input) continue;
    if (typeof input === "string" || typeof input === "number") {
      out.push(String(input));
    } else if (Array.isArray(input)) {
      const inner = cn(...input);
      if (inner) out.push(inner);
    } else if (typeof input === "object") {
      for (const key in input) if (input[key]) out.push(key);
    }
  }
  return out.join(" ");
}
