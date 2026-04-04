export const DEMO_MODE_KEY = 'bda_demo_mode'
export const DEMO_PIPELINE_RUNNING_KEY = 'bda_demo_pipeline_running'
export const DEMO_PIPELINE_STARTED_AT_KEY = 'bda_demo_pipeline_started_at'
export const DEMO_STATE_EVENT = 'bda-demo-state-changed'

interface DemoState {
  enabled: boolean
  pipelineRunning: boolean
  pipelineStartedAt: string | null
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function emitDemoStateChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(DEMO_STATE_EVENT))
  }
}

export function getDemoState(): DemoState {
  if (!canUseStorage()) {
    return {
      enabled: false,
      pipelineRunning: false,
      pipelineStartedAt: null,
    }
  }

  return {
    enabled: window.localStorage.getItem(DEMO_MODE_KEY) === '1',
    pipelineRunning: window.localStorage.getItem(DEMO_PIPELINE_RUNNING_KEY) === '1',
    pipelineStartedAt: window.localStorage.getItem(DEMO_PIPELINE_STARTED_AT_KEY),
  }
}

export function setDemoModeEnabled(enabled: boolean) {
  if (!canUseStorage()) return

  window.localStorage.setItem(DEMO_MODE_KEY, enabled ? '1' : '0')
  emitDemoStateChanged()
}

export function startDemoPipeline() {
  if (!canUseStorage()) return

  window.localStorage.setItem(DEMO_MODE_KEY, '1')
  window.localStorage.setItem(DEMO_PIPELINE_RUNNING_KEY, '1')
  window.localStorage.setItem(DEMO_PIPELINE_STARTED_AT_KEY, new Date().toISOString())
  emitDemoStateChanged()
}

export function stopDemoPipeline() {
  if (!canUseStorage()) return

  window.localStorage.setItem(DEMO_PIPELINE_RUNNING_KEY, '0')
  emitDemoStateChanged()
}
