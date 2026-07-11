import { Fragment } from "react";

/** Renderiza texto com trechos entre *asteriscos* destacados (coral por padrão). */
export function Highlight({
  text,
  className = "text-coral",
}: {
  text: string;
  className?: string;
}) {
  const parts = text.split("*");
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} className={className}>
            {p}
          </span>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        )
      )}
    </>
  );
}
