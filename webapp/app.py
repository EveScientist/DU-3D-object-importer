"""objtodu.evescientist.net -- .obj mesh -> Dual Universe blueprint web front-end.

Thin Flask wrapper over the proven single-core pipeline in /home/du (obj_frontend ->
du_voxelize -> du_semantic -> du_envelope). Upload a mesh, pick core size + options, get a
.blueprint back. Served by gunicorn on 127.0.0.1:5002, proxied by nginx (vhost_nginx.conf).
"""
import os
import sys
import tempfile
import traceback
import uuid

# Find the pipeline modules (du_*.py / obj_frontend.py). In the git repo they live in the
# repo root, one level up from this webapp/ folder; OBJTODU_PIPELINE overrides for other
# layouts (e.g. the live server, which historically kept them in /home/du).
_here = os.path.dirname(os.path.abspath(__file__))
_pipeline = os.environ.get('OBJTODU_PIPELINE', os.path.dirname(_here))
sys.path.insert(0, _pipeline)

from flask import Flask, request, send_file, render_template, jsonify

import obj_frontend as F
import du_envelope as E

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024      # 64 MB upload cap

CORE_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']           # cap at XXL (XXXL+ impractical)
CORE_TYPES = ['static', 'dynamic', 'space']
WORKDIR = '/tmp/objtodu'
os.makedirs(WORKDIR, exist_ok=True)

# Interactive-preview grid ceiling. Voxelization is now parallelized (fork pools), so the old
# grid-96 cap -- set when a serial grid-160 preview took ~19s -- is over-conservative. 160 is
# ~2.7x the detail of 96 at ~9 MB payload / ~3 s preview_mesh (the remaining single-threaded
# cost). Raise via OBJTODU_PREVIEW_CAP on a fast local box; payload/mesh time scale ~linearly
# with grid, so 192 ~= 11 MB / ~4 s. (The DOWNLOAD still uses the full max_grid; this caps the
# live preview only.)
PREVIEW_CAP = int(os.environ.get('OBJTODU_PREVIEW_CAP') or 160)


@app.route('/')
def index():
    rows = [(s, E.core_voxel_size(s), E.core_build_voxels(s)) for s in CORE_SIZES]
    return render_template('index.html', core_sizes=CORE_SIZES, core_types=CORE_TYPES,
                           core_rows=rows)


def _opts(form):
    def _f(k, d):
        try:
            return float(form.get(k, d))
        except ValueError:
            return float(d)
    def _i(k, d):
        try:
            return int(form.get(k, d))
        except ValueError:
            return int(d)
    size = form.get('size', 'M').upper()
    core_type = form.get('core_type', 'static')
    return dict(
        size=size if size in CORE_SIZES else 'M',
        core_type=core_type if core_type in CORE_TYPES else 'static',
        mode=form.get('mode', 'scale'),
        hollow=form.get('hollow') == 'on',
        smooth=form.get('smooth') == 'on',
        rotate_to_z_up=form.get('rotate_to_z_up') == 'on',  # default on (checked by default in HTML)
        crease_deg=min(max(_f('crease_deg', 35.0), 5.0), 80.0),  # snappiness: 5-80°
        fill=min(max(_f('fill', 0.9), 0.05), 1.0),
        max_grid=min(max(_i('max_grid', 256), 32), 512),
        min_thickness=min(max(_i('min_thickness', 2), 1), 16),
        second_material=form.get('second_material') == 'on',
    )


@app.route('/preview', methods=['POST'])
def preview():
    """Return the VOXELIZED + smoothed result as a surface mesh (flat vertex/tri arrays) so
    the browser can show what DU will actually build. Voxelized at a capped grid for speed."""
    up = request.files.get('mesh')
    if up is None or up.filename == '' or not up.filename.lower().endswith(('.obj','.stl','.ply','.gltf','.glb')):
        return jsonify(error='Upload a .obj / .stl / .ply / .gltf / .glb mesh.'), 400
    o = _opts(request.form)
    token = uuid.uuid4().hex[:8]
    _ext = os.path.splitext(up.filename)[1].lower()
    obj_path = os.path.join(WORKDIR, f'{token}_pv{_ext}')
    up.save(obj_path)
    try:
        # preview at the DOWNLOAD resolution, capped (PREVIEW_CAP / OBJTODU_PREVIEW_CAP) for a
        # snappy interactive re-render -- payload + preview_mesh time scale with surface area.
        pv_cap = PREVIEW_CAP
        pv_grid = min(o['max_grid'], pv_cap)
        voxels, smooth_fn, labels = F.voxelize_obj(
            obj_path, size=o['size'], fill_fraction=o['fill'], hollow=o['hollow'],
            want_anchors=o['smooth'], max_grid=pv_grid, min_thickness=o['min_thickness'],
            rotate_to_z_up=o['rotate_to_z_up'], crease_deg=o['crease_deg'])
        verts, tris = F.preview_mesh(voxels, smooth_fn if o['smooth'] else None)
        full = min(int(round(E.core_build_voxels(o['size']) * o['fill'])), o['max_grid'])
        return jsonify(v=[round(x, 3) for x in verts], f=tris,
                       voxels=len(voxels), size=o['size'], mode=o['mode'],
                       fill=o['fill'], build=E.core_build_voxels(o['size']),
                       preview_grid=min(full, pv_cap), full_grid=full)
    except Exception as ex:
        traceback.print_exc()
        return jsonify(error=f'Preview failed: {ex}'), 500
    finally:
        try:
            os.remove(obj_path)
        except OSError:
            pass


@app.route('/convert', methods=['POST'])
def convert():
    up = request.files.get('mesh')
    if up is None or up.filename == '':
        return jsonify(error='No .obj file uploaded.'), 400
    if not up.filename.lower().endswith(('.obj', '.stl', '.ply', '.gltf', '.glb')):
        return jsonify(error='Upload a .obj / .stl / .ply / .gltf / .glb mesh.'), 400

    o = _opts(request.form)
    size, core_type, mode = o['size'], o['core_type'], o['mode']
    hollow, smooth = o['hollow'], o['smooth']
    fill, max_grid, min_thickness = o['fill'], o['max_grid'], o['min_thickness']
    rotate_to_z_up, crease_deg = o['rotate_to_z_up'], o['crease_deg']
    second_material = o['second_material']

    stem = os.path.splitext(os.path.basename(up.filename))[0][:40] or 'model'
    token = uuid.uuid4().hex[:8]
    _ext = os.path.splitext(up.filename)[1].lower()
    obj_path = os.path.join(WORKDIR, f'{token}{_ext}')
    out_path = os.path.join(WORKDIR, f'{token}.blueprint')
    up.save(obj_path)

    try:
        if mode == 'auto':
            m = F.obj_to_blueprints(obj_path, os.path.join(WORKDIR, token), mode='auto',
                                    core_type=core_type, resolution=max_grid, hollow=hollow,
                                    smooth=smooth, name=stem, second_material=second_material)
            produced = m['files'][0]
            size = m['size']
        else:
            F.obj_to_blueprint(obj_path, out_path, size=size, core_type=core_type,
                               fill_fraction=fill, hollow=hollow, smooth=smooth,
                               name=stem, max_grid=max_grid, min_thickness=min_thickness,
                               rotate_to_z_up=rotate_to_z_up, crease_deg=crease_deg,
                               second_material=second_material)
            produced = out_path
        return send_file(produced, as_attachment=True,
                         download_name=f'{stem}_{size}.blueprint',
                         mimetype='application/octet-stream')
    except Exception as ex:
        traceback.print_exc()
        return jsonify(error=f'Conversion failed: {ex}'), 500
    finally:
        try:
            os.remove(obj_path)
        except OSError:
            pass


@app.route('/health')
def health():
    return jsonify(ok=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5002, debug=True)
