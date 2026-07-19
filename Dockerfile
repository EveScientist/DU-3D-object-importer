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
# grid ~391 (60M voxels) ~= a few GB; tune to your machine or override at `docker run`.
ENV OBJTODU_MAX_VOXELS=60000000 \
    OBJTODU_PIPELINE=/app \
    PYTHONUNBUFFERED=1

EXPOSE 5002

# 2 workers, long timeout: a max-res solid voxelization can take tens of seconds.
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5002", "--timeout", "300", \
     "--chdir", "/app/webapp", "app:app"]
