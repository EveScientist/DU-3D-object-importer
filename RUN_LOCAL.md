# Running objtodu on your own PC

The web app (`.obj/.stl/.ply/.gltf` mesh → Dual Universe blueprint) was memory-bound on the
shared server. On a PC with real RAM you can run it at full resolution. Two ways — Docker is
the recommended one since you already run the DU server in a container.

## Option A — Docker (recommended)

You already run the DU server in Docker/Rancher, so this fits your workflow: pinned deps,
no clash with your system Python, an optional hard memory cap so a big conversion can never
take the whole PC down.

```bash
git clone https://github.com/EveScientist/DU-3D-object-importer.git
cd DU-3D-object-importer
git checkout negative-octant-and-seams        # until this merges to main

docker compose up -d --build                   # build + start
# open http://localhost:5002
docker compose logs -f                          # watch a conversion
docker compose down                             # stop
```

Tuning (in `docker-compose.yml`):
- `OBJTODU_MAX_VOXELS` — peak-RAM ceiling. Default is 134217728 (512^3, ~8.6 GB), the
  largest grid the web UI's max_grid field will ever request; raise it if your PC has the
  memory, lower it if conversions get killed.
- `mem_limit:` — hard-caps the container's RAM (the OOM safety net); default 24g.

## Option B — plain Python (fastest to iterate on the code)

```bash
git clone https://github.com/EveScientist/DU-3D-object-importer.git
cd DU-3D-object-importer
git checkout negative-octant-and-seams
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export OBJTODU_MAX_VOXELS=134217728                 # Windows: set OBJTODU_MAX_VOXELS=134217728
cd webapp
gunicorn -w 2 -b 0.0.0.0:5002 --timeout 300 app:app # or: python app.py  (dev server)
# open http://localhost:5002
```

## CLI (no web server)

```bash
python obj_frontend.py ship.obj ship.blueprint --size L --fill 0.9 --smooth
```

## Notes
- Everything resolves relative to the repo — no absolute paths. `OBJTODU_PIPELINE` and
  `OBJTODU_TEMPLATE` override the module/template locations if you rearrange things.
- The Model-skeleton donor `exports/archive/3187_export.blueprint` ships in the repo; the
  emitter clones it (DU recomputes metadata on import), so no game files are needed.
- Peak RAM ≈ `grid³` voxels × ~64 B. grid 512 (the UI's own max) ≈ 134M ≈ 8.6 GB. Set the
  ceiling to taste.
