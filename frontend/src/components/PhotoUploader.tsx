// Cycle 17.3 (D-035) — upload photos OBLIGATOIRE : la photo est la preuve
// acheteur et l'entrée du pipeline d'identification.
// Drag&drop desktop + capture caméra mobile (capture=environment).

import { useRef, useState } from "react";
import { uploadPhoto } from "../api";

export interface UploadedPhoto {
  imageId: string;
  url: string; // URL servie par l'API (préviews + annonce finale)
}

const MAX_PHOTOS = 5;

export function PhotoUploader({
  photos,
  onChange,
  disabled,
}: {
  photos: UploadedPhoto[];
  onChange: (photos: UploadedPhoto[]) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFiles(files: FileList | File[]) {
    setError(null);
    const list = Array.from(files).slice(0, MAX_PHOTOS - photos.length);
    if (list.length === 0) return;
    setUploading(true);
    const next = [...photos];
    try {
      for (const file of list) {
        if (!file.type.startsWith("image/")) {
          setError(`${file.name} n'est pas une image.`);
          continue;
        }
        const res = await uploadPhoto(file);
        next.push({ imageId: res.image_id, url: `/api${res.url}` });
      }
      onChange(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur d'upload");
    } finally {
      setUploading(false);
    }
  }

  function remove(imageId: string) {
    onChange(photos.filter((p) => p.imageId !== imageId));
  }

  return (
    <div>
      <span className="text-sm font-medium text-slate-700">
        Photos de votre objet <span className="text-rose-600">*</span>
        <span className="ml-1 font-normal text-slate-400">
          (au moins 1 — c'est la preuve pour l'acheteur)
        </span>
      </span>

      {/* Préviews des photos uploadées */}
      {photos.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {photos.map((p) => (
            <div key={p.imageId} className="relative">
              <img
                src={p.url}
                alt="Photo du produit"
                className="h-20 w-20 rounded-lg border border-slate-200 object-cover"
              />
              <button
                type="button"
                onClick={() => remove(p.imageId)}
                aria-label="Supprimer cette photo"
                className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-700 text-xs text-white hover:bg-rose-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Zone de drop / bouton caméra */}
      {photos.length < MAX_PHOTOS && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (!disabled && !uploading) handleFiles(e.dataTransfer.files);
          }}
          onClick={() => !disabled && !uploading && inputRef.current?.click()}
          className={`mt-2 cursor-pointer rounded-xl border-2 border-dashed p-4 text-center text-sm transition ${
            dragOver
              ? "border-rose-400 bg-rose-50 text-rose-600"
              : "border-slate-300 text-slate-500 hover:border-rose-300 hover:bg-slate-50"
          }`}
        >
          {uploading ? (
            "Envoi en cours…"
          ) : (
            <>
              📷 Prenez une photo ou glissez-la ici
              <span className="mt-0.5 block text-xs text-slate-400">
                JPEG, PNG, WebP — {MAX_PHOTOS - photos.length} restante(s)
              </span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            capture="environment"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files) handleFiles(e.target.files);
              e.target.value = ""; // permet de re-sélectionner le même fichier
            }}
          />
        </div>
      )}

      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
