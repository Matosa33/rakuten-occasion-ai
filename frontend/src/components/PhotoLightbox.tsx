// Cycle 17.4 (D-035) — visionneuse plein écran réutilisable :
// photos catalogue des candidats (étape 2) ET photos vendeur de l'annonce (étape 3).
// Navigation ←/→ + clavier, fermeture Échap/clic fond, compteur.

import { useCallback, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

export function PhotoLightbox({
  images,
  index,
  onIndexChange,
  onClose,
}: {
  images: string[];
  index: number | null; // null = fermé
  onIndexChange: (i: number) => void;
  onClose: () => void;
}) {
  const open = index !== null && images.length > 0;

  const prev = useCallback(
    () => onIndexChange(((index ?? 0) - 1 + images.length) % images.length),
    [index, images.length, onIndexChange]
  );
  const next = useCallback(
    () => onIndexChange(((index ?? 0) + 1) % images.length),
    [index, images.length, onIndexChange]
  );

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, prev, next, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/85 p-4"
          role="dialog"
          aria-label="Visionneuse de photos"
        >
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-1.5 text-xl text-white hover:bg-white/20"
          >
            ×
          </button>

          {images.length > 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                prev();
              }}
              aria-label="Photo précédente"
              className="absolute left-3 rounded-full bg-white/10 px-3.5 py-2 text-2xl text-white hover:bg-white/20"
            >
              ‹
            </button>
          )}

          <img
            src={images[index ?? 0]}
            alt={`Photo ${(index ?? 0) + 1} sur ${images.length}`}
            onClick={(e) => e.stopPropagation()}
            className="max-h-[85vh] max-w-[90vw] rounded-xl bg-white object-contain shadow-2xl"
          />

          {images.length > 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                next();
              }}
              aria-label="Photo suivante"
              className="absolute right-3 rounded-full bg-white/10 px-3.5 py-2 text-2xl text-white hover:bg-white/20"
            >
              ›
            </button>
          )}

          {images.length > 1 && (
            <span className="absolute bottom-4 rounded-full bg-white/15 px-3 py-1 text-xs text-white">
              {(index ?? 0) + 1} / {images.length}
            </span>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
