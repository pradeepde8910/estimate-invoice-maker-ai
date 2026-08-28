/**
 * Builds a human-readable, disambiguated display label for a client record.
 *
 * Priority order for the qualifier shown in parentheses:
 *   1. GSTIN  (most unique — legally 1:1 with a registered business)
 *   2. Phone  (usually unique per entity)
 *   3. Email  (usually unique per entity)
 *   4. Contact person name (useful when the same company has multiple contacts)
 *
 * Examples:
 *   "Pradeep Technologies (33AABCP1234A1Z5)"
 *   "Pradeep Technologies (9876543210)"
 *   "Pradeep Technologies (pradeep@gmail.com)"
 *   "Pradeep Technologies (John Doe)"
 *   "Pradeep Technologies"   ← no qualifier available at all
 */

interface ClientLike {
  company_name?: string | null
  contact_person?: string | null
  email?: string | null
  phone?: string | null
  gstin?: string | null
}

/**
 * Returns a compact display label for a client, appending a unique qualifier
 * in parentheses when available, so that two clients with the same company
 * name can be told apart.
 */
export function clientDisplayLabel(c: ClientLike): string {
  const name = c.company_name || c.contact_person || 'Unnamed Client'

  // Pick the best available disambiguator
  const qualifier = c.gstin || c.phone || c.email || (c.company_name && c.contact_person ? c.contact_person : null)

  return qualifier ? `${name} (${qualifier})` : name
}
