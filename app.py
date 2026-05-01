from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from tutorial_engine import TutorialBuildError, build_tutorial_from_url

app = Flask(__name__)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/tutorial")
def create_tutorial():
    payload = request.get_json(silent=True) or {}
    youtube_url = str(payload.get("url", "")).strip()

    if not youtube_url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400

    try:
        tutorial = build_tutorial_from_url(youtube_url)
        return jsonify(tutorial), 200
    except TutorialBuildError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return (
            jsonify(
                {
                    "error": "Couldn't build the tutorial right now. Try a different video URL."
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
