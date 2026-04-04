'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart3,
  Activity,
  AlertCircle,
  Zap,
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
    active: false,
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
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-sidebar text-sidebar-foreground transition-transform duration-300 lg:relative lg:w-64 lg:translate-x-0 border-r border-sidebar-border flex flex-col',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-sidebar-border">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-sidebar-primary"></div>
            <h1 className="text-lg font-bold tracking-tight">ML Monitor</h1>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden text-sidebar-foreground/60 hover:text-sidebar-foreground"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
          {navigationItems.map((item) => {
            const isActive = pathname.includes(item.href)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium',
                  isActive
                    ? 'bg-sidebar-primary/20 text-sidebar-primary border border-sidebar-primary/30'
                    : 'text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50'
                )}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-sidebar-border text-xs text-sidebar-foreground/60">
          <p className="mb-1 uppercase tracking-wider text-sidebar-foreground/50">Status</p>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <p>Connected</p>
          </div>
        </div>
      </aside>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="border-b border-border bg-card px-6 py-4 backdrop-blur-sm bg-card/95">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden text-foreground/60 hover:text-foreground transition-colors"
            >
              <Menu size={20} />
            </button>
            <div>
              <h2 className="text-xl font-semibold text-foreground tracking-tight">Dashboard</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Real-time ML monitoring & control</p>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-gradient-to-br from-background via-background to-background/95">
          <div className="p-6 max-w-7xl mx-auto">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
