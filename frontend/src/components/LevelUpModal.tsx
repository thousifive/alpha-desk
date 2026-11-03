import { AnimatePresence, motion } from 'framer-motion'
import { useEffect } from 'react'

import type { Level } from '../api/types'

export function LevelUpModal({ level, onClose }: { level: Level | null; onClose: () => void }) {
  useEffect(() => {
    if (!level) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [level, onClose])

  return (
    <AnimatePresence>
      {level && (
        <motion.div
          className="fixed inset-0 z-50 grid place-items-center bg-bg/80 px-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-labelledby="levelup-title"
        >
          <motion.div
            className="relative w-full max-w-sm overflow-hidden rounded-xl border border-amber/40 bg-panel p-8 text-center"
            initial={{ scale: 0.6, rotate: -4 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 16 }}
            onClick={(e) => e.stopPropagation()}
          >
            <motion.div
              className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,var(--color-amber),transparent_60%)]"
              initial={{ opacity: 0.5 }}
              animate={{ opacity: 0.12 }}
              transition={{ duration: 1.2 }}
              aria-hidden
            />
            <p className="relative font-mono text-xs tracking-[0.3em] text-muted">PROMOTION</p>
            <motion.h2
              id="levelup-title"
              className="relative mt-3 font-mono text-4xl font-bold text-amber"
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              {level.title}
            </motion.h2>
            <p className="relative mt-3 text-sm text-muted">
              HR has updated your badge.
              {level.next_title && (
                <>
                  {' '}
                  Next stop: <span className="text-ink">{level.next_title}</span> at{' '}
                  {level.next_min_xp?.toLocaleString()} XP.
                </>
              )}
            </p>
            <button
              onClick={onClose}
              autoFocus
              className="relative mt-6 rounded bg-amber px-5 py-2 font-mono text-sm font-semibold text-bg"
            >
              BACK TO WORK
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
