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
import json
import time as time_module

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
    size = size if size in CORE_SIZES else 'M'
    # Default max_grid scales with core size: larger cores allow higher resolution
    core_vox = E.core_build_voxels(size)
    # Grid cap per core size: balanced for practical RAM usage
    # XL @ 1024 is safer than 2048 (which needs 32+ GB RAM)
    grid_cap = {
        'XS': 128, 'S': 256, 'M': 512,
        'L': 1024, 'XL': 1024, 'XXL': 2048,
        'XXXL': 4096, 'XXXXL': 8192, 'XXXXXL': 16384
    }.get(size, 1024)
    default_max_grid = min(core_vox, grid_cap)
    voxel_method = form.get('voxel_method', 'sat').lower()
    voxel_method = voxel_method if voxel_method in ('sat', 'ray', 'sdf', 'flood') else 'sat'
    return dict(
        size=size,
        core_type=core_type if core_type in CORE_TYPES else 'static',
        mode=form.get('mode', 'scale'),
        hollow=form.get('hollow') == 'on',
        smooth=form.get('smooth') == 'on',
        rotate_to_z_up=form.get('rotate_to_z_up') == 'on',  # default on (checked by default in HTML)
        crease_deg=min(max(_f('crease_deg', 35.0), 5.0), 80.0),  # snappiness: 5-80°
        fill=min(max(_f('fill', 0.9), 0.05), 1.0),
        max_grid=min(max(_i('max_grid', default_max_grid), 32), grid_cap),
        min_thickness=min(max(_i('min_thickness', 2), 1), 16),
        voxel_method=voxel_method,
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
        voxels, smooth_fn = F.voxelize_obj(
            obj_path, size=o['size'], fill_fraction=o['fill'], hollow=o['hollow'],
            want_anchors=o['smooth'], max_grid=pv_grid, min_thickness=o['min_thickness'],
            rotate_to_z_up=o['rotate_to_z_up'], crease_deg=o['crease_deg'],
            voxelization_method=o['voxel_method'])
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


_psutil_available = False
try:
    import psutil
    _psutil_available = True
except ImportError:
    pass


def _get_metrics():
    """Get memory and CPU usage metrics."""
    try:
        if _psutil_available:
            p = psutil.Process()
            mem_mb = p.memory_info().rss / 1024 / 1024
            cpu_pct = p.cpu_percent(interval=0.01)
            return {'mem_mb': round(mem_mb, 1), 'cpu_pct': round(cpu_pct, 1)}
    except Exception as e:
        import sys
        print(f"[metrics] Error: {e}", file=sys.stderr)
    return {'mem_mb': 0, 'cpu_pct': 0}


def _emit_progress(messages, stage, detail, percent=None, metrics=None):
    """Format and yield SSE progress message."""
    msg = {'stage': stage, 'detail': detail}
    if percent is not None:
        msg['percent'] = percent
    if metrics is None:
        metrics = _get_metrics()
    msg.update(metrics)
    messages.append(msg)
    data = f"data: {json.dumps(msg)}\n\n"
    yield data.encode('utf-8')


@app.route('/convert-stream', methods=['POST'])
def convert_stream():
    """Stream conversion progress via Server-Sent Events."""
    from io import StringIO

    up = request.files.get('mesh')
    if up is None or up.filename == '':
        return jsonify(error='No .obj file uploaded.'), 400
    if not up.filename.lower().endswith(('.obj', '.stl', '.ply', '.gltf', '.glb')):
        return jsonify(error='Upload a .obj / .stl / .ply / .gltf / .glb mesh.'), 400

    o = _opts(request.form)
    debug = request.form.get('debug') == 'on'
    size, core_type, mode = o['size'], o['core_type'], o['mode']
    hollow, smooth = o['hollow'], o['smooth']
    fill, max_grid, min_thickness = o['fill'], o['max_grid'], o['min_thickness']
    rotate_to_z_up, crease_deg = o['rotate_to_z_up'], o['crease_deg']

    stem = os.path.splitext(os.path.basename(up.filename))[0][:40] or 'model'
    token = uuid.uuid4().hex[:8]
    _ext = os.path.splitext(up.filename)[1].lower()
    obj_path = os.path.join(WORKDIR, f'{token}{_ext}')
    out_path = os.path.join(WORKDIR, f'{token}.blueprint')
    up.save(obj_path)

    import threading
    import time as time_module

    def generate():
        nonlocal size  # Reference outer scope variable
        messages = []
        log_capture = StringIO()
        old_stdout, old_stderr = None, None

        # Queue for heartbeat messages from background thread
        heartbeat_queue = []
        stop_heartbeat = threading.Event()

        def heartbeat_thread():
            """Background thread that emits status updates every 2 seconds."""
            import sys
            import re
            last_progress_pct = None
            last_pct_time = time_module.time()

            try:
                while not stop_heartbeat.is_set():
                    try:
                        metrics = _get_metrics()
                        # Check if voxelization thread is still alive
                        try:
                            is_alive = voxel_thread.is_alive()
                        except NameError:
                            is_alive = False

                        # Extract latest progress % from logs
                        progress_pct = ""
                        speed_info = ""
                        try:
                            recent_logs = log_capture.getvalue().split('\n')[-20:]
                            for line in reversed(recent_logs):
                                match = re.search(r'\((\d+)%\).*?(\d+\.?\d*)\s+voxels/sec.*?ETA\s+(\d+)s', line)
                                if match:
                                    pct = int(match.group(1))
                                    speed = float(match.group(2))
                                    eta = int(match.group(3))
                                    progress_pct = pct
                                    speed_info = f" - {speed:.0f} vox/s, ETA {eta}s"
                                    progress_pct = f" {pct}%"
                                    break
                                else:
                                    match = re.search(r'\((\d+)%\)', line)
                                    if match:
                                        pct = int(match.group(1))
                                        progress_pct = f" {pct}%"
                                        break
                        except:
                            pass

                        # Detect stall: if percentage hasn't changed for 60+ seconds
                        now = time_module.time()
                        if progress_pct and last_progress_pct == progress_pct and (now - last_pct_time) > 60:
                            speed_info += " ⚠️ STALLED (no progress for 60s)"
                        elif progress_pct and last_progress_pct != progress_pct:
                            last_pct_time = now
                            last_progress_pct = progress_pct

                        status = f"Processing... ({metrics.get('mem_mb', 0)} MB, {metrics.get('cpu_pct', 0)}% CPU){progress_pct}{speed_info}" + \
                                 (" [THREAD RUNNING]" if is_alive else " [THREAD STOPPED!]")
                        msg = {'stage': 'progress', 'detail': status}
                        msg.update(metrics)
                        heartbeat_queue.append(msg)
                    except Exception as e:
                        print(f"[heartbeat] Error creating message: {e}", file=sys.stderr)
                        heartbeat_queue.append({
                            'stage': 'progress',
                            'detail': f'Heartbeat error: {str(e)[:100]}',
                            'mem_mb': 0,
                            'cpu_pct': 0
                        })
                    try:
                        time_module.sleep(2)
                    except Exception as e:
                        print(f"[heartbeat] Sleep error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[heartbeat] Thread fatal error: {e}", file=sys.stderr)
                heartbeat_queue.append({
                    'stage': 'error',
                    'detail': f'Heartbeat thread crashed: {str(e)[:100]}',
                    'mem_mb': 0,
                    'cpu_pct': 0
                })

        try:
            # Set up logging capture if debug
            if debug:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = log_capture
                sys.stderr = log_capture

            yield from _emit_progress(messages, 'init', 'Loading mesh file...', 0)

            try:
                # Container for result from worker thread
                result_container = {'produced': None, 'size': None, 'error': None}

                def run_voxelization():
                    """Run voxelization in a thread so we can stream heartbeats."""
                    try:
                        if mode == 'auto':
                            m = F.obj_to_blueprints(obj_path, os.path.join(WORKDIR, token), mode='auto',
                                                    core_type=core_type, resolution=max_grid, hollow=hollow,
                                                    smooth=smooth, name=stem, voxelization_method=o['voxel_method'])
                            result_container['produced'] = m['files'][0]
                            result_container['size'] = m['size']
                        else:
                            F.obj_to_blueprint(obj_path, out_path, size=size, core_type=core_type,
                                               fill_fraction=fill, hollow=hollow, smooth=smooth,
                                               name=stem, max_grid=max_grid, min_thickness=min_thickness,
                                               rotate_to_z_up=rotate_to_z_up, crease_deg=crease_deg,
                                               voxelization_method=o['voxel_method'])
                            result_container['produced'] = out_path
                            result_container['size'] = size
                    except Exception as e:
                        result_container['error'] = str(e)

                if mode == 'auto':
                    yield from _emit_progress(messages, 'load', 'Parsing mesh...', 5)
                    yield from _emit_progress(messages, 'fit', 'Fitting to grid (auto-size)...', 10)
                else:
                    yield from _emit_progress(messages, 'load', 'Parsing mesh...', 5)
                    yield from _emit_progress(messages, 'fit', f'Fitting to {size} core at {max_grid}³ resolution...', 10)

                yield from _emit_progress(messages, 'voxel',
                    f'Voxelizing via {o["voxel_method"].upper()} method ({max_grid}³ grid)...', 20)

                # Start voxelization in background thread
                voxel_thread = threading.Thread(target=run_voxelization, daemon=True)
                voxel_thread.start()

                # Start heartbeat for voxelization
                hb = threading.Thread(target=heartbeat_thread, daemon=True)
                hb.start()

                # Send initial diagnostic
                initial_metrics = _get_metrics()
                diag_msg = f"Started voxelization - metrics available: {_psutil_available} (initial: {initial_metrics['mem_mb']}MB)"
                yield from _emit_progress(messages, 'progress', diag_msg, 20, initial_metrics)

                # Stream heartbeats and log updates while voxelization runs
                last_log_pos = 0
                while voxel_thread.is_alive():
                    # Emit any queued heartbeats
                    while heartbeat_queue:
                        hb_msg = heartbeat_queue.pop(0)
                        data = f"data: {json.dumps(hb_msg)}\n\n"
                        yield data.encode('utf-8')

                    # Check for new log lines with progress info (both debug and normal mode)
                    current_log = log_capture.getvalue()
                    new_content = current_log[last_log_pos:]
                    for line in new_content.split('\n'):
                        if line and any(x in line for x in ['Surface:', 'Interior:', 'SDF:', 'FINAL:']):
                            metrics = _get_metrics()
                            msg = {'stage': 'progress', 'detail': line.strip(), **metrics}
                            data = f"data: {json.dumps(msg)}\n\n"
                            yield data.encode('utf-8')
                    last_log_pos = len(current_log)

                    time_module.sleep(0.5)  # Check queue frequently

                # Wait for thread to finish (with timeout for safety)
                voxel_thread.join(timeout=3600)  # 1 hour timeout for extreme cases
                if voxel_thread.is_alive():
                    yield from _emit_progress(messages, 'error',
                        'Voxelization timeout after 1 hour - process may be stuck', 0)

                stop_heartbeat.set()

                while heartbeat_queue:
                    hb_msg = heartbeat_queue.pop(0)
                    data = f"data: {json.dumps(hb_msg)}\n\n"
                    yield data.encode('utf-8')

                # Check for errors
                if result_container['error']:
                    raise Exception(result_container['error'])

                produced = result_container['produced']
                size = result_container['size']

                yield from _emit_progress(messages, 'voxel', 'Voxelization complete!', 60)

                # Get voxelization stats from logs
                recent_logs = log_capture.getvalue().split('\n')[-15:] if debug else []
                voxel_info = [l for l in recent_logs if 'FINAL:' in l]
                if voxel_info:
                    yield from _emit_progress(messages, 'voxel', voxel_info[-1], 70)

                yield from _emit_progress(messages, 'smooth', 'Building blueprint and finalizing...', 75)

                # Read blueprint file and encode as base64 for download
                with open(produced, 'rb') as f:
                    bp_data = f.read()
                bp_b64 = __import__('base64').b64encode(bp_data).decode('ascii')

                # Get captured logs if debug
                logs = log_capture.getvalue() if debug else None
                metrics = _get_metrics()

                yield f"data: {json.dumps({'stage': 'done', 'percent': 100, 'blueprint': bp_b64, 'filename': f'{stem}_{size}.blueprint', 'logs': logs, **metrics})}\n\n".encode('utf-8')

            finally:
                if debug and old_stdout:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                try:
                    os.remove(obj_path)
                except OSError:
                    pass
        except Exception as ex:
            traceback.print_exc()
            if debug and old_stdout:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            logs = log_capture.getvalue() if debug else str(ex)
            yield f"data: {json.dumps({'stage': 'error', 'error': str(ex), 'logs': logs})}\n\n".encode('utf-8')

    return app.response_class(generate(), mimetype='text/event-stream')


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
                                    smooth=smooth, name=stem, voxelization_method=o['voxel_method'])
            produced = m['files'][0]
            size = m['size']
        else:
            F.obj_to_blueprint(obj_path, out_path, size=size, core_type=core_type,
                               fill_fraction=fill, hollow=hollow, smooth=smooth,
                               name=stem, max_grid=max_grid, min_thickness=min_thickness,
                               rotate_to_z_up=rotate_to_z_up, crease_deg=crease_deg,
                               voxelization_method=o['voxel_method'])
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
