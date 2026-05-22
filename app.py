"""
app.py
Ponto de entrada da API Flask — Monitor de Sincronização de Lojas.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from routes import sync_bp

app = Flask(__name__)

# ─── CORS ────────────────────────────────────────────────────────────────────
# Permite requisições do front-end React em desenvolvimento e produção.
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ─── Blueprints ──────────────────────────────────────────────────────────────
app.register_blueprint(sync_bp)


# ─── Root ────────────────────────────────────────────────────────────────────
@app.route("/")
def root():
    return jsonify({
        "system":  "Monitor de Sincronização de Lojas",
        "version": "1.0.0",
        "endpoints": {
            "health":   "GET /api/health",
            "status":   "GET /api/status",
            "stats":    "GET /api/stats",
            "loja":     "GET /api/loja/<grupo_loja>",
            "charts":   "GET /api/charts?grupo_loja=<grupo_loja>",
        },
    })


# ─── Error handlers ──────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": True, "message": "Rota não encontrada."}), 404


@app.errorhandler(500)
def internal_error(exc):
    return jsonify({"error": True, "message": str(exc)}), 500


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Desenvolvimento: use `python app.py`
    # Produção:        use `waitress-serve --port=5000 app:app`
    app.run(host="0.0.0.0", port=5000, debug=True)
