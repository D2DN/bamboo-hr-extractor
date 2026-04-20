#!/usr/bin/env python3
"""Web UI for bamboo-hr-extractor."""
import json
import queue
import subprocess
import sys
import threading

import os

from flask import Flask, Response, render_template, request, send_file, stream_with_context

app = Flask(__name__)

_current_proc: subprocess.Popen | None = None


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _current_proc
    if _current_proc and _current_proc.poll() is None:
        _current_proc.terminate()
        return {"status": "stopped"}
    return {"status": "no_process"}


@app.route("/api/download")
def api_download():
    filename = request.args.get("filename", "")
    if not filename or not os.path.isfile(filename):
        return {"error": f"File not found: {filename}"}, 404
    return send_file(
        os.path.abspath(filename),
        as_attachment=True,
        download_name=os.path.basename(filename),
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/jobs")
def api_jobs():
    api_key = request.args.get("api_key", "")
    domain = request.args.get("domain", "")
    if not api_key or not domain:
        return {"error": "api_key and domain are required"}, 400

    try:
        from bamboo_extractor.config import Config
        from bamboo_extractor.client import BambooHRClient

        config = Config(api_key=api_key, company_domain=domain)
        client = BambooHRClient(config)
        jobs = client.get_jobs()
        result = []
        for j in jobs:
            t = j.get("title", {})
            label = (t.get("label") if isinstance(t, dict) else t) or f"Job #{j.get('id')}"
            result.append({"id": j.get("id"), "label": label})
        result.sort(key=lambda x: x["label"])
        return {"jobs": result}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.json or {}

    cmd = [sys.executable, "main.py", "extract"]

    def add(flag, value):
        if value:
            cmd.extend([flag, str(value)])

    def add_flag(flag, value):
        if value:
            cmd.append(flag)

    add("--api-key", data.get("api_key"))
    add("--domain", data.get("domain"))
    add("--status", data.get("status"))
    add("--job-id", data.get("job_id"))
    add("--job-title", data.get("job_title"))
    add("--new-since", data.get("new_since"))
    add("--format", data.get("output_format"))
    add("--output", data.get("output_file"))
    add("--resumes-dir", data.get("resumes_dir"))
    add_flag("--demo", data.get("demo"))
    if data.get("enrich") is False:
        cmd.append("--no-enrich")

    def generate():
        global _current_proc
        q: queue.Queue[str | None] = queue.Queue()

        def run():
            global _current_proc
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                _current_proc = proc
                for line in proc.stdout:
                    q.put(line)
                proc.wait()
                q.put(f"\n[Process exited with code {proc.returncode}]\n")
            except Exception as e:
                q.put(f"[ERROR] {e}\n")
            finally:
                _current_proc = None
                q.put(None)

        threading.Thread(target=run, daemon=True).start()

        while True:
            line = q.get()
            if line is None:
                break
            yield f"data: {json.dumps(line)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
