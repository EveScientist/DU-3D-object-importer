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

sys.path.insert(0, '/home/du')

from flask import Flask, request, send_file, render_template, jsonify

import obj_frontend as F
import du_envelope as E

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024      # 64 MB upload cap

CORE_SIZES = list(E.CORE_SIZES)                           # XS .. XXXXXL
CORE_TYPES = ['static', 'dynamic', 'space']
WORKDIR = '/tmp/objtodu'
os.makedirs(WORKDIR, exist_ok=True)


@app.route('/')
def index():
    rows = [(s, E.core_voxel_size(s), E.core_build_voxels(s)) for s in CORE_SIZES]
    return render_template('index.html', core_sizes=CORE_SIZES, core_types=CORE_TYPES,
                           core_rows=rows)


@app.route('/convert', methods=['POST'])
def convert():
    up = request.files.get('mesh')
    if up is None or up.filename == '':
        return jsonify(error='No .obj file uploaded.'), 400
    if not up.filename.lower().endswith('.obj'):
        return jsonify(error='Please upload a .obj mesh file.'), 400

    size = request.form.get('size', 'M').upper()
    core_type = request.form.get('core_type', 'static')
    mode = request.form.get('mode', 'scale')             # scale | auto
    hollow = request.form.get('hollow') == 'on'
    smooth = request.form.get('smooth') == 'on'
    try:
        fill = float(request.form.get('fill', '0.9'))
    except ValueError:
        fill = 0.9
    fill = min(max(fill, 0.05), 1.0)
    try:
        max_grid = int(request.form.get('max_grid', '256'))
    except ValueError:
        max_grid = 256
    max_grid = min(max(max_grid, 32), 512)
    try:
        min_thickness = int(request.form.get('min_thickness', '2'))
    except ValueError:
        min_thickness = 2
    min_thickness = min(max(min_thickness, 1), 16)
    if size not in E.CORE_SIZES:
        size = 'M'
    if core_type not in CORE_TYPES:
        core_type = 'static'

    stem = os.path.splitext(os.path.basename(up.filename))[0][:40] or 'model'
    token = uuid.uuid4().hex[:8]
    obj_path = os.path.join(WORKDIR, f'{token}.obj')
    out_path = os.path.join(WORKDIR, f'{token}.blueprint')
    up.save(obj_path)

    try:
        if mode == 'auto':
            m = F.obj_to_blueprints(obj_path, os.path.join(WORKDIR, token), mode='auto',
                                    core_type=core_type, resolution=max_grid, hollow=hollow,
                                    smooth=smooth, name=stem)
            produced = m['files'][0]
            size = m['size']
        else:
            F.obj_to_blueprint(obj_path, out_path, size=size, core_type=core_type,
                               fill_fraction=fill, hollow=hollow, smooth=smooth,
                               name=stem, max_grid=max_grid, min_thickness=min_thickness)
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
