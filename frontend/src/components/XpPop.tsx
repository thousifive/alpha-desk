import { AnimatePresence, motion } from 'framer-motion'

/** Floating "+N XP" that rises and fades. Re-keyed by `id` so repeated passes replay it. */
export function XpPop({ id, amount }: { id: number; amount: number }) {
  return (
    <AnimatePresence>
      {amount > 0 && (
        <motion.span
          key={id}
          initial={{ opacity: 0, y: 8, scale: 0.8 }}
          animate={{ opacity: [0, 1, 1, 0], y: -28, scale: 1.1 }}
          transition={{ duration: 1.6, times: [0, 0.15, 0.7, 1], ease: 'easeOut' }}
          className="pointer-events-none absolute -top-2 right-0 font-mono text-lg font-bold text-amber drop-shadow"
          aria-hidden
        >
          +{amount} XP
        </motion.span>
      )}
    </AnimatePresence>
  )
}
