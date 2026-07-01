"""Interface d'annotation RAPIDE des photos d'éval (Phase 2 - richesse d'entrée).

Saisie minimale côté humain : **photos + texte brut de l'annonce réelle** (titre + description).
Les métadonnées structurées (macro, taxonomie, seller_metadata) sont **dérivées ensuite** par
`derive_meta.py` (LLM) puis relues - pas de formulaire à remplir champ par champ.

Rangement automatique (aucune manip de fichiers) :

    data/photos_eval/<NN>_<slug>/
        01.jpg 02.jpg …        (01 = photo principale, sert seule en condition C1)
        meta.json              ({listing_title, listing_description, photos, annotated:false})

Lancer :

    .venv/Scripts/python.exe scripts/annotation_tool/app.py      # http://127.0.0.1:8200
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "data" / "photos_eval"
TARGET_TOTAL = 100
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

app = FastAPI(title="Annotation rapide - photos d'éval Rakuten")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return (s[:40] or "produit").strip("_")


def _next_index() -> int:
    if not DATASET_DIR.exists():
        return 1
    nums = [
        int(m.group(1))
        for d in DATASET_DIR.iterdir()
        if d.is_dir() and (m := re.match(r"(\d+)_", d.name))
    ]
    return (max(nums) + 1) if nums else 1


def _list_entries() -> list[dict]:
    out: list[dict] = []
    if not DATASET_DIR.exists():
        return out
    for d in sorted(DATASET_DIR.iterdir()):
        meta_f = d / "meta.json"
        if d.is_dir() and meta_f.exists():
            try:
                m = json.loads(meta_f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            out.append(
                {
                    "dir": d.name,
                    "title": m.get("listing_title", "") or m.get("true_name", ""),
                    "n_photos": len(m.get("photos", [])),
                    "annotated": bool(m.get("annotated", False)),
                    "macro": m.get("macro", ""),
                }
            )
    return out


@app.get("/api/list")
def api_list() -> JSONResponse:
    entries = _list_entries()
    return JSONResponse(
        {
            "entries": entries,
            "total": len(entries),
            "target": TARGET_TOTAL,
            "annotated": sum(1 for e in entries if e["annotated"]),
            "thin": sum(1 for e in entries if e["n_photos"] < 2),
        }
    )


@app.post("/api/save")
async def api_save(
    photos: list[UploadFile],
    listing_title: str = Form(""),
    listing_description: str = Form(""),
    main_index: int = Form(0),
) -> JSONResponse:
    listing_title = listing_title.strip()
    listing_description = listing_description.strip()
    if not (listing_title or listing_description):
        raise HTTPException(400, "Colle au moins le titre ou la description de l'annonce.")
    photos = [p for p in photos if p.filename]
    if not photos:
        raise HTTPException(400, "Au moins une photo est requise.")
    for p in photos:
        if Path(p.filename).suffix.lower() not in ALLOWED_EXT:
            raise HTTPException(400, f"Extension non supportée : {p.filename}.")

    # photo principale en premier (= 01) - condition C1 (une seule photo)
    if 0 <= main_index < len(photos):
        photos.insert(0, photos.pop(main_index))

    idx = _next_index()
    slug = _slugify(listing_title or f"produit_{idx}")
    target = DATASET_DIR / f"{idx:02d}_{slug}"
    target.mkdir(parents=True, exist_ok=False)

    saved: list[str] = []
    for i, p in enumerate(photos, start=1):
        ext = Path(p.filename).suffix.lower()
        ext = ".jpg" if ext == ".jpeg" else ext
        fname = f"{i:02d}{ext}"
        (target / fname).write_bytes(await p.read())
        saved.append(fname)

    meta = {
        "listing_title": listing_title,
        "listing_description": listing_description,
        "photos": saved,
        "main_photo": saved[0],
        "annotated": False,  # métadonnées structurées dérivées ensuite par derive_meta.py
    }
    (target / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return JSONResponse({"ok": True, "dir": target.name, "n_photos": len(saved)})


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE.replace("__TARGET__", str(TARGET_TOTAL))


_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Annotation rapide - photos d'éval</title>
<style>
  :root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8;--ok:#22c55e;--warn:#f59e0b}
  *{box-sizing:border-box} body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
  .wrap{max-width:1100px;margin:0 auto;padding:24px;display:grid;grid-template-columns:1fr 320px;gap:24px}
  h1{font-size:20px;margin:0 0 4px} .sub{color:var(--mut);margin:0 0 16px}
  .card{background:var(--card);border:1px solid #334155;border-radius:12px;padding:18px;margin-bottom:16px}
  label{display:block;font-weight:600;margin:12px 0 4px;font-size:13px}
  input,textarea{width:100%;padding:9px 11px;border-radius:8px;border:1px solid #475569;background:#0b1220;color:var(--ink);font:inherit}
  textarea{min-height:120px;resize:vertical} .req{color:var(--acc)}
  .drop{border:2px dashed #475569;border-radius:10px;padding:22px;text-align:center;color:var(--mut);cursor:pointer}
  .drop.hot{border-color:var(--acc);color:var(--acc)}
  .thumbs{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
  .thumb{position:relative;width:96px}
  .thumb img{width:96px;height:96px;object-fit:cover;border-radius:8px;border:2px solid #334155}
  .thumb.main img{border-color:var(--ok)}
  .thumb small{display:block;text-align:center;color:var(--mut);font-size:11px;margin-top:2px}
  .thumb .pick{position:absolute;top:4px;left:4px}
  button{margin-top:16px;width:100%;padding:12px;border:0;border-radius:9px;background:var(--acc);color:#04222f;font-weight:700;font-size:15px;cursor:pointer}
  button:disabled{opacity:.5;cursor:not-allowed}
  .bar{height:8px;background:#0b1220;border-radius:6px;overflow:hidden;margin:6px 0 2px}
  .bar>i{display:block;height:100%;background:var(--ok)}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ok);color:#04220f;padding:12px 20px;border-radius:9px;font-weight:700;opacity:0;transition:.3s}
  .toast.show{opacity:1} .hint{color:var(--warn);font-size:12px;margin-top:4px}
  .list{max-height:300px;overflow:auto;font-size:12px;color:var(--mut)} .list div{padding:2px 0}
  kbd{background:#0b1220;border:1px solid #475569;border-radius:4px;padding:1px 6px;font-size:12px}
</style></head><body>
<div class="wrap">
  <div>
    <h1>📸 Annotation rapide - Phase 2</h1>
    <p class="sub">Tu mets les <b>photos</b> + le <b>texte de l'annonce</b>. Je dérive les métadonnées (macro, taxo…) ensuite. La 1ʳᵉ photo (bordure verte) = principale (sert seule en C1). Astuce : <kbd>Ctrl/Cmd + Entrée</kbd> pour enregistrer.</p>
    <div class="card">
      <div id="drop" class="drop">Glisse les photos ici, ou clique pour choisir (3-5 par produit)</div>
      <input id="files" type="file" accept="image/*" multiple style="display:none">
      <div id="thumbs" class="thumbs"></div>

      <label>Titre de l'annonce <span class="req">*</span></label>
      <input id="listing_title" placeholder="ex: iPhone 13 128 Go noir - très bon état">
      <label>Description de l'annonce (copie-colle l'annonce réelle)</label>
      <textarea id="listing_description" placeholder="Colle ici la description Leboncoin/Vinted… (marque, modèle, état, specs). Plus c'est riche, mieux je dérive la catégorie."></textarea>
      <button id="save" disabled>Enregistrer le produit</button>
    </div>
  </div>

  <div>
    <div class="card">
      <h1 style="font-size:16px">Avancement</h1>
      <div id="count" class="sub">0 / __TARGET__ produits</div>
      <div class="bar"><i id="prog" style="width:0%"></i></div>
      <p id="flags" class="hint"></p>
    </div>
    <div class="card">
      <h1 style="font-size:16px">Produits saisis</h1>
      <div id="list" class="list">-</div>
    </div>
  </div>
</div>
<div id="toast" class="toast"></div>
<script>
const TARGET = __TARGET__;
let files = [], mainIdx = 0;
const $ = id => document.getElementById(id);
const drop=$("drop"), inp=$("files");
drop.onclick=()=>inp.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add("hot")};
drop.ondragleave=()=>drop.classList.remove("hot");
drop.ondrop=e=>{e.preventDefault();drop.classList.remove("hot");addFiles(e.dataTransfer.files)};
inp.onchange=()=>addFiles(inp.files);

function addFiles(fl){ for(const f of fl) if(f.type.startsWith("image/")) files.push(f); renderThumbs(); validate(); }
function renderThumbs(){
  $("thumbs").innerHTML="";
  files.forEach((f,i)=>{
    const url=URL.createObjectURL(f);
    const d=document.createElement("div"); d.className="thumb"+(i===mainIdx?" main":"");
    d.innerHTML=`<input class="pick" type="radio" name="main" ${i===mainIdx?"checked":""} title="photo principale">
      <img src="${url}"><small>${i===mainIdx?"principale":"#"+(i+1)}</small>`;
    d.querySelector(".pick").onchange=()=>{mainIdx=i;renderThumbs()};
    $("thumbs").appendChild(d);
  });
}
$("listing_title").oninput=validate; $("listing_description").oninput=validate;
function validate(){ $("save").disabled = !(($("listing_title").value.trim()||$("listing_description").value.trim()) && files.length); }
document.addEventListener("keydown",e=>{ if((e.ctrlKey||e.metaKey)&&e.key==="Enter"&&!$("save").disabled) save(); });
$("save").onclick=save;

async function save(){
  const fd=new FormData();
  files.forEach(f=>fd.append("photos",f));
  fd.append("listing_title",$("listing_title").value);
  fd.append("listing_description",$("listing_description").value);
  fd.append("main_index",mainIdx);
  $("save").disabled=true;
  const r=await fetch("/api/save",{method:"POST",body:fd});
  if(r.ok){ const j=await r.json(); toast("✓ "+j.dir+" ("+j.n_photos+" photos)");
    files=[];mainIdx=0;renderThumbs();
    $("listing_title").value=""; $("listing_description").value=""; validate(); refresh();
  } else { const e=await r.json(); toast("✗ "+(e.detail||"erreur")); $("save").disabled=false; }
}
function toast(m){ const t=$("toast"); t.textContent=m; t.classList.add("show"); setTimeout(()=>t.classList.remove("show"),2600); }

async function refresh(){
  const j=await (await fetch("/api/list")).json();
  $("count").textContent=j.total+" / "+TARGET+" produits ("+j.annotated+" annotés)";
  $("prog").style.width=Math.min(100,100*j.total/TARGET)+"%";
  const f=[]; if(j.thin) f.push(j.thin+" produit(s) avec <2 photos (ajoute des vues pour le test N>1)");
  $("flags").textContent=f.join(" · ");
  $("list").innerHTML=j.entries.length? j.entries.map(e=>`<div>${e.dir} - ${e.n_photos}📷 ${e.annotated?("✓ "+e.macro):"⏳ à dériver"}</div>`).join("") : "-";
}
refresh();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Dataset -> {DATASET_DIR}")
    print("Interface -> http://127.0.0.1:8200")
    uvicorn.run(app, host="127.0.0.1", port=8200)
