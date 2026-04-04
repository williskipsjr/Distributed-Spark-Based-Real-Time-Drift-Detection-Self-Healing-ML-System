'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart3,
  Activity,
  AlertCircle,
  Zap,
  Cpu,
  ShieldCheck,
  Menu,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigationItems = [
  {
    label: 'Overview',
    href: '/dashboard/overview',
    icon: BarChart3,
    active: false,
  },
  {
    label: 'Drift Detection',
    href: '/dashboard/drift',
    icon: Activity,
    active: false,
  },
  {
    label: 'System Health',
    href: '/dashboard/health',
    icon: AlertCircle,
    active: false,
  },
  {
    label: 'Control',
    href: '/dashboard/control',
    icon: Zap,
  },
  {
    label: 'Self-Healing',
    href: '/dashboard/self-healing',
    icon: ShieldCheck,
  },
  {
    label: 'Model Registry',
    href: '/dashboard/models',
    icon: Cpu,
  },
]

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background" suppressHydrationWarning>
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-72 border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-300 lg:relative lg:w-72 lg:translate-x-0',
          'flex flex-col',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="border-b border-sidebar-border px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="telemetry-label">telemetry hub</p>
              <h1 className="mt-1 text-xl font-bold tracking-wide text-sidebar-foreground">RACE CONTROL</h1>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-sidebar-foreground/60 hover:text-sidebar-foreground lg:hidden"
            >
              <X size={20} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 animate-pulse rounded-full bg-sidebar-primary"></div>
            <p className="text-xs uppercase tracking-[0.12em] text-sidebar-foreground/70">Live systems linked</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-6">
          {navigationItems.map((item) => {
            const isActive = pathname.includes(item.href)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 border px-3 py-3 text-sm font-semibold uppercase tracking-[0.12em]',
                  isActive
                    ? 'border-sidebar-primary/40 bg-sidebar-primary/10 text-sidebar-primary'
                    : 'border-transparent text-sidebar-foreground/70 hover:border-sidebar-border hover:bg-sidebar-accent/70 hover:text-sidebar-foreground'
                )}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-sidebar-border px-6 py-4 text-xs text-sidebar-foreground/70">
          <p className="telemetry-label">operator role</p>
          <p className="mt-1 text-sm font-semibold uppercase tracking-[0.11em] text-sidebar-foreground">ML Ops Engineer</p>
          <div className="mt-3 flex items-center gap-2">
            <div className="h-2 w-2 animate-pulse rounded-full bg-sidebar-primary"></div>
            <p className="uppercase tracking-[0.1em]">Control authority active</p>
          </div>
        </div>
      </aside>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="border-b border-border bg-card px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden text-foreground/60 hover:text-foreground transition-colors"
            >
              <Menu size={20} />
            </button>
            <div>
              <p className="telemetry-label">live telemetry control surface</p>
              <h2 className="text-xl font-bold tracking-[0.08em] text-foreground">SYSTEM DASHBOARD</h2>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden border border-border bg-background/70 px-3 py-2 sm:block">
                <p className="telemetry-label">status</p>
                <p className="mt-1 text-xs font-semibold uppercase tracking-[0.1em] text-primary">streaming live</p>
              </div>
              <div className="border border-border bg-background/70 px-3 py-2">
                <p className="telemetry-label">role</p>
                <p className="mt-1 text-xs font-semibold uppercase tracking-[0.1em] text-foreground">pilot</p>
              </div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-auto" suppressHydrationWarning>
          <div className="mx-auto max-w-[1400px] p-5 md:p-8" suppressHydrationWarning>
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
