'use client'

import Link from 'next/link'
import { ArrowRight, Activity, Zap, Database, Cpu, Workflow, Shield } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background to-background/95">
      {/* Navigation */}
      <header className="border-b border-border/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-primary"></div>
            <h1 className="text-lg font-bold tracking-tight text-foreground">ML Monitor</h1>
          </div>
          <Link
            href="/dashboard/overview"
            className="text-sm font-medium text-foreground/70 hover:text-foreground transition-colors"
          >
            Dashboard
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 py-20 lg:py-32">
        <div className="text-center space-y-6">
          <div className="inline-flex items-center justify-center">
            <div className="px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-sm font-medium text-primary">
              Real-time ML Monitoring
            </div>
          </div>
          
          <h1 className="text-5xl lg:text-6xl font-bold text-foreground leading-tight">
            Self-Healing Machine Learning System
          </h1>
          
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Real-time prediction, drift detection, and automatic model retraining
          </p>

          <div className="pt-4">
            <Link
              href="/dashboard/overview"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition-colors"
            >
              Go to Dashboard
              <ArrowRight size={20} />
            </Link>
          </div>
        </div>
      </section>

      {/* What This Is */}
      <section className="border-t border-border/50 bg-card/30">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center max-w-3xl mx-auto space-y-4">
            <h2 className="text-2xl lg:text-3xl font-bold text-foreground">What This Is</h2>
            <p className="text-lg text-muted-foreground leading-relaxed">
              This is a real-time ML system that monitors prediction performance and automatically retrains and replaces models when data drift is detected. It keeps your models accurate and reliable without manual intervention.
            </p>
          </div>
        </div>
      </section>

      {/* Problems Section */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <div className="space-y-8">
          <h2 className="text-2xl lg:text-3xl font-bold text-foreground text-center">The Problem</h2>
          
          <div className="grid md:grid-cols-3 gap-6">
            <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/30 transition-colors">
              <div className="text-3xl mb-3">📉</div>
              <h3 className="font-semibold text-foreground mb-2">Models Degrade Over Time</h3>
              <p className="text-muted-foreground">Performance drops as patterns in real-world data shift away from training data.</p>
            </div>

            <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/30 transition-colors">
              <div className="text-3xl mb-3">🔄</div>
              <h3 className="font-semibold text-foreground mb-2">Data Changes Constantly</h3>
              <p className="text-muted-foreground">Seasonality, demand patterns, and user behavior evolve faster than manual processes can adapt.</p>
            </div>

            <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/30 transition-colors">
              <div className="text-3xl mb-3">⏳</div>
              <h3 className="font-semibold text-foreground mb-2">Manual Retraining is Slow</h3>
              <p className="text-muted-foreground">Waiting for engineers to notice and fix drift issues means hours or days of degraded predictions.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Solution Flow */}
      <section className="border-t border-border/50 bg-card/30">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <h2 className="text-2xl lg:text-3xl font-bold text-foreground text-center mb-12">The Solution</h2>
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 overflow-x-auto pb-4">
            {[
              { label: 'Ingest', icon: Database },
              { label: 'Predict', icon: Zap },
              { label: 'Monitor', icon: Activity },
              { label: 'Detect Drift', icon: Shield },
              { label: 'Retrain', icon: Cpu },
              { label: 'Promote', icon: Workflow },
            ].map((step, idx) => {
              const Icon = step.icon
              return (
                <div key={idx} className="flex items-center gap-4 flex-shrink-0">
                  <div className="flex flex-col items-center gap-3 min-w-fit">
                    <div className="p-3 rounded-lg bg-primary/15 text-primary border border-primary/30">
                      <Icon size={24} />
                    </div>
                    <span className="text-sm font-semibold text-foreground">{step.label}</span>
                  </div>
                  {idx < 5 && (
                    <ArrowRight size={20} className="text-muted-foreground flex-shrink-0 hidden md:block" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Key Features */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-2xl lg:text-3xl font-bold text-foreground text-center mb-12">Key Features</h2>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="p-6 rounded-xl border border-border bg-card">
            <Zap size={24} className="text-primary mb-4" />
            <h3 className="font-semibold text-foreground mb-2">Real-time Streaming</h3>
            <p className="text-muted-foreground">Kafka + Spark pipeline processes data in real-time for instant predictions and monitoring.</p>
          </div>

          <div className="p-6 rounded-xl border border-border bg-card">
            <Shield size={24} className="text-primary mb-4" />
            <h3 className="font-semibold text-foreground mb-2">Drift Detection</h3>
            <p className="text-muted-foreground">Automatically detect when data patterns change and trigger retraining cycles.</p>
          </div>

          <div className="p-6 rounded-xl border border-border bg-card">
            <Workflow size={24} className="text-primary mb-4" />
            <h3 className="font-semibold text-foreground mb-2">Self-Healing Retraining</h3>
            <p className="text-muted-foreground">Models retrain and replace themselves automatically when drift is detected.</p>
          </div>

          <div className="p-6 rounded-xl border border-border bg-card">
            <Database size={24} className="text-primary mb-4" />
            <h3 className="font-semibold text-foreground mb-2">Model Versioning</h3>
            <p className="text-muted-foreground">Track all model versions, performance metrics, and easily rollback if needed.</p>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="border-t border-border/50 bg-card/30">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <h2 className="text-2xl lg:text-3xl font-bold text-foreground text-center mb-8">Tech Stack</h2>
          
          <div className="flex flex-wrap justify-center gap-3">
            {['Kafka', 'Spark', 'XGBoost', 'Python', 'Parquet'].map((tech) => (
              <span
                key={tech}
                className="px-4 py-2 rounded-lg border border-primary/30 bg-primary/10 text-sm font-medium text-primary"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-8 md:p-12 text-center">
          <h2 className="text-3xl font-bold text-foreground mb-4">Ready to Monitor Your Models?</h2>
          <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
            Access the live dashboard to view real-time predictions, drift detection, system health, and control your ML pipeline.
          </p>
          <Link
            href="/dashboard/overview"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition-colors"
          >
            Go to Dashboard
            <ArrowRight size={20} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 mt-20 py-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-sm text-muted-foreground">
          <p>Self-Healing Machine Learning System • Real-time Monitoring & Control</p>
        </div>
      </footer>
    </div>
  )
}
