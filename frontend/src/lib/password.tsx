/**
 * Politica de senha compartilhada — alinhada com o backend
 * (app/auth/schemas.py: RegisterRequest.validate_password_strength):
 *   - minimo 8 caracteres
 *   - pelo menos 1 letra maiuscula
 *   - pelo menos 1 digito
 *
 * Mesmas regras em register, reset-password e change-password (settings),
 * para que o que o usuario digita no UI nunca seja rejeitado pelo backend.
 */

const PWD_CRITERIA = [
  (p: string) => p.length >= 8,
  (p: string) => /[A-Z]/.test(p),
  (p: string) => /\d/.test(p),
  (p: string) => p.length >= 12 || /[^A-Za-z0-9]/.test(p),
];

const STRENGTH = [
  { label: "", color: "" },
  { label: "Fraca", color: "#ef4444" },
  { label: "Média", color: "#f59e0b" },
  { label: "Boa", color: "#3b82f6" },
  { label: "Forte", color: "#22c55e" },
];

/** Retorna mensagem de erro caso a senha viole a politica, ou null se estiver ok. */
export function meetsPasswordPolicy(password: string): string | null {
  if (password.length < 8) return "Senha deve ter no mínimo 8 caracteres";
  if (!/[A-Z]/.test(password)) return "Senha deve conter pelo menos 1 letra maiúscula";
  if (!/\d/.test(password)) return "Senha deve conter pelo menos 1 número";
  return null;
}

/** Medidor de forca visual — reuso em todos os formularios de senha. */
export function PasswordStrength({ password }: { password: string }) {
  if (!password) {
    return <p className="text-xs text-slate-400 mt-1.5">Mínimo 8 caracteres, 1 maiúscula e 1 número.</p>;
  }
  const score = PWD_CRITERIA.filter((test) => test(password)).length;
  const { label, color } = STRENGTH[score];
  return (
    <div className="mt-2">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="h-1 flex-1 rounded-full transition-colors duration-300"
            style={{ background: i < score ? color : "rgba(255,255,255,0.1)" }}
          />
        ))}
      </div>
      <p className="text-xs mt-1.5 font-medium" style={{ color: color || undefined }}>
        Força da senha: {label}
      </p>
    </div>
  );
}
