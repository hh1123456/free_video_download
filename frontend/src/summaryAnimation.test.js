import test from 'node:test'
import assert from 'node:assert/strict'
import { summaryAnimationKey } from './summaryAnimation.js'

test('summaryAnimationKey changes when the same task receives richer content', () => {
  const task = { id: 'task-1' }
  const fastResult = {
    overview: 'fast overview',
    outline: [{ title: '快速章节', points: [] }],
  }
  const detailedResult = {
    overview: 'fast overview',
    outline: [{ title: '快速章节', points: ['详细解释'] }],
  }

  assert.notEqual(
    summaryAnimationKey({ task, view: fastResult, url: 'https://example.com/video' }),
    summaryAnimationKey({ task, view: detailedResult, url: 'https://example.com/video' })
  )
})

test('summaryAnimationKey stays stable for equivalent summary content', () => {
  const first = {
    task: { id: 'task-1' },
    view: {
      overview: 'same',
      key_points: ['point'],
      outline: [{ title: 'part', points: ['detail'] }],
    },
    url: 'https://example.com/video',
  }
  const second = {
    task: { id: 'task-1' },
    view: {
      overview: 'same',
      key_points: ['point'],
      outline: [{ title: 'part', points: ['detail'] }],
    },
    url: 'https://example.com/video',
  }

  assert.equal(summaryAnimationKey(first), summaryAnimationKey(second))
})
