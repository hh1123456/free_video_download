import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createAiSummaryCache,
  shouldAnimateSummaryView,
} from './aiSummaryState.js'

test('summary cache restores an in-flight task by URL', () => {
  const cache = createAiSummaryCache()
  const url = 'https://example.com/video'
  cache.save(url, {
    open: true,
    task: { id: 'task-1', status: 'summarizing', stage: 'AI 正在总结...' },
    view: null,
    origin: null,
  })

  assert.deepEqual(cache.restore(url), {
    open: true,
    task: { id: 'task-1', status: 'summarizing', stage: 'AI 正在总结...' },
    view: null,
    origin: null,
  })
})

test('summary cache removes expired running tasks', () => {
  const cache = createAiSummaryCache({ now: () => 1_000, ttlMs: 100 })
  cache.save('https://example.com/video', {
    open: true,
    task: { id: 'task-1', status: 'summarizing' },
  })

  cache.setNow(() => 1_200)

  assert.equal(cache.restore('https://example.com/video'), null)
})

test('completed summaries skip the typewriter animation', () => {
  assert.equal(shouldAnimateSummaryView({ task: { status: 'completed' }, tab: 'markdown' }), false)
})

test('enriching summaries can use the typewriter animation', () => {
  assert.equal(shouldAnimateSummaryView({ task: { status: 'enriching' }, tab: 'markdown' }), true)
})

