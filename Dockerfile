# objtodu -- .obj/.stl/.ply/.gltf mesh -> Dual Universe blueprint web app.
# Repo root is the build context: the pipeline modules (du_*.py, obj_frontend.py) sit
# beside webapp/, and app.py finds them one level up from itself.
FROM python:3.12-slim

# numpy needs no system libs on slim for wheels; keep the image lean.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pipeline modules + the web app. .dockerignore keeps tests/ out and trims exports/
# down to the one Model-skeleton template the emitter clones (build_blueprint_sem).
COPY *.py ./
COPY webapp/ ./webapp/
COPY exports/ ./exports/

# On a PC there is RAM to spare vs the old shared server -- lift the voxel ceiling.
# 134217728 = 512^3, the largest grid the web UI's max_grid field will ever request
# (~8.6 GB peak); tune to your machine or override at `docker run`.
# *_NUM_THREADS=1: our parallelism is PROCESS-level (fork pools in du_voxelize/obj_pipeline),
# so per-process BLAS/OpenMP threads only oversubscribe -- and worse, an active BLAS
# threadpool at fork() time DEADLOCKS the pool workers under gunicorn (zombie workers, parent
# stuck in futex; reproduced at 12 workers/grid 512). Baked in here so the CLI and a fresh
# clone are protected too, not just docker-compose. Must be set before numpy imports.
ENV OBJTODU_MAX_VOXELS=134217728 \
    OBJTODU_PIPELINE=/app \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5002

# 2 workers, long timeout: a max-res (grid 512) solid voxelization can take well over
# 5 minutes on the pure-Python emitter, so 300s was killing legitimate large conversions.
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5002", "--timeout", "1800", \
     "--chdir", "/app/webapp", "app:app"]
