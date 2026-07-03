function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function outlineSignature(outline = []) {
  return (outline || [])
    .map((item) => {
      const title = normalizeText(item?.title)
      const points = (item?.points || []).map(normalizeText).join('~')
      return `${title}:${points}`
    })
    .join('|')
}

export function summaryAnimationKey({ task, view, url }) {
  const taskKey = task?.id || task?.url || url || 'summary'
  const contentKey = [
    normalizeText(view?.overview),
    (view?.key_points || []).map(normalizeText).join('|'),
    outlineSignature(view?.outline),
  ].join('::')

  return `${taskKey}::${contentKey}`
}
