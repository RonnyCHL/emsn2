#!/usr/bin/env python3
"""
EMSN Reports API - Flask server for serving reports and generating PDFs
"""

import os
import subprocess
from pathlib import Path
from flask import Flask, send_file, request, jsonify, send_from_directory
from flask_cors import CORS
import tempfile

app = Flask(__name__)
CORS(app)

REPORTS_DIR = Path("/home/ronny/emsn2/reports")
WEB_DIR = Path("/home/ronny/emsn2/reports-web")

@app.route('/')
def index():
    """Serve the main index page"""
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    """Serve static files (HTML, CSS, JS, JSON)"""
    return send_from_directory(WEB_DIR, filename)

@app.route('/reports/<path:filename>')
def serve_report(filename):
    """Serve markdown report files"""
    return send_from_directory(REPORTS_DIR, filename)

@app.route('/api/pdf')
def generate_pdf():
    """Generate PDF from markdown report"""
    filename = request.args.get('file')

    if not filename:
        return jsonify({'error': 'No file specified'}), 400

    md_path = REPORTS_DIR / filename

    if not md_path.exists():
        return jsonify({'error': 'Report not found'}), 404

    # Create temporary PDF file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        pdf_path = Path(tmp.name)

    try:
        # Use pandoc to convert markdown to PDF
        # Strip YAML frontmatter first
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        # Write cleaned content to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_md:
            tmp_md.write(content)
            tmp_md_path = Path(tmp_md.name)

        # Convert to PDF with pandoc using XeLaTeX for better Unicode support
        result = subprocess.run([
            'pandoc',
            str(tmp_md_path),
            '-o', str(pdf_path),
            '--pdf-engine=xelatex',
            '-V', 'geometry:margin=2cm',
            '--metadata', 'title=EMSN Rapport'
        ], check=True, capture_output=True, text=True)

        # Clean up temp markdown
        tmp_md_path.unlink()

        # Send PDF file
        pdf_filename = filename.replace('.md', '.pdf')
        response = send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype='application/pdf'
        )

        # Clean up PDF after sending
        @response.call_on_close
        def cleanup():
            try:
                pdf_path.unlink()
            except:
                pass

        return response

    except subprocess.CalledProcessError as e:
        if pdf_path.exists():
            pdf_path.unlink()
        error_msg = f'PDF generation failed: {str(e)}'
        if e.stderr:
            error_msg += f'\nStderr: {e.stderr}'
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        if pdf_path.exists():
            pdf_path.unlink()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=8081, debug=False)
