import { createContext, useContext } from 'react'

/**
 * Lets the shared `Topbar` render a mobile hamburger button that opens the
 * workspace sidebar drawer, without prop-drilling a callback through every
 * page that renders a `Topbar`. Only `EstimationLayout`/`InvoiceLayout`
 * provide a value — pages outside a workspace (e.g. Home) render `Topbar`
 * with no sidebar to open, so `useOpenSidebar()` returning `null` there is
 * expected and `Topbar` simply skips the hamburger button.
 */
const SidebarMenuContext = createContext<(() => void) | null>(null)

export const SidebarMenuProvider = SidebarMenuContext.Provider

export function useOpenSidebar() {
  return useContext(SidebarMenuContext)
}
