/** Whether a role may see something. No `allowed` list means everyone. */
export function canSee(allowed: string[] | undefined, role: string | null): boolean {
  if (!allowed) return true
  return !!role && allowed.includes(role)
}
