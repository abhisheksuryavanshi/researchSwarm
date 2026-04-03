import { NavLink, Outlet } from 'react-router-dom'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  [
    'block rounded-[var(--rs-radius-md)] px-3 py-2 text-sm transition-colors',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--rs-accent)]',
    isActive
      ? 'bg-[var(--rs-accent-muted)] text-[var(--rs-accent)]'
      : 'text-[var(--rs-text-muted)] hover:bg-[var(--rs-surface-elevated)] hover:text-[var(--rs-text)]',
  ].join(' ')

export function Layout() {
  return (
    <div className="flex min-h-full">
      <nav
        className="w-52 shrink-0 border-r border-[var(--rs-border)] bg-[var(--rs-surface)] p-4"
        aria-label="Main navigation"
      >
        <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-[var(--rs-text-muted)]">
          Research Swarm
        </p>
        <ul className="flex flex-col gap-1">
          <li>
            <NavLink to="/" className={linkClass} end>
              Chat
            </NavLink>
          </li>
          <li>
            <NavLink to="/tools" className={linkClass}>
              Tools
            </NavLink>
          </li>
          <li>
            <NavLink to="/stats" className={linkClass}>
              Stats
            </NavLink>
          </li>
        </ul>
      </nav>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
