"""Jev 简历初筛 Web MVP（Flask）· JD 版.

- GET  /           -> web/index.html
- POST /api/screen -> {"jd": "<职位描述>", "text": "<简历>"} -> 一次 Jev 调用，8 项评估

判定全部以 JD 为参照：匹配度、技能实证（关键词吹牛检测）、推荐结论均对照当前岗位。

用法:
    python server.py
    打开 http://127.0.0.1:8768
"""
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from typesafe_sdk import TypeSafeClient

BASE = os.path.dirname(os.path.abspath(__file__))

KEY = [l.split("=", 1)[1].strip()
       for l in open(os.path.join(BASE, ".env"), encoding="utf-8")
       if l.startswith("TYPESAFE_API_KEY=")][0]

app = Flask(__name__)
client = TypeSafeClient(api_key=KEY)   # 全局共享：TLS 连接复用
lock = threading.Lock()                # 串行化共享 client 的调用

QUESTIONS = {
    "years": {"type": "score",
              "instructions": "How many years of professional experience does the candidate have, as of today",
              "criteria": ["0-1", "2-3", "4-5", "6-7", "8-9", "10+"]},
    "depth": {"type": "score",
              "instructions": "Rate hands-on engineering depth from what the candidate personally built. Ignore skills keyword lists, titles, and company names.",
              "criteria": ["No evidence of real building",
                           "Small tasks, unclear ownership",
                           "Solid individual contributions",
                           "Owned significant systems end to end",
                           "Designed and delivered complex systems with measurable impact",
                           "Career-defining depth, industry-level work"]},
    "jd_match": {"type": "score",
                 "instructions": "How well does the candidate satisfy the explicit requirements in the JOB DESCRIPTION",
                 "criteria": ["Meets almost none of the requirements",
                              "Meets some peripheral requirements only",
                              "Meets most core requirements with gaps",
                              "Meets all core requirements",
                              "Exceeds requirements across the board"]},
    "skill_evidence": {"type": "noul",
                       "instructions": "The resume's claimed skills that this job requires are backed by concrete project evidence (built, shipped, owned), not just keyword lists"},
    "mentorship": {"type": "noul",
                   "instructions": "The resume demonstrates real mentoring or team leadership experience"},
    "opensource": {"type": "noul",
                   "instructions": "The candidate has verifiable open source contributions"},
    "progression": {"type": "choice",
                    "instructions": "What type of career progression is shown",
                    "criteria": {"steady_growth": "Increasing scope and seniority over time",
                                 "job_hopping": "Many short stints without growth",
                                 "lateral_moves": "Similar roles repeated without progression"}},
    "recommend": {"type": "choice",
                  "instructions": "Hiring recommendation for the role described in the JOB DESCRIPTION",
                  "criteria": {"interview": "Strong fit for the role, advance to interview",
                               "reject": "Clearly not a fit for the role",
                               "human_review": "Mixed or inflated signals, a human should look first"}},
}


def _warmup():
    with lock:
        client.system_one(state="warmup",
                          questions={"ok": {"type": "noul", "instructions": "The state contains text"}})


threading.Thread(target=_warmup, daemon=True).start()  # 启动即预热（首次 TLS ~6s，之后 ~400ms）


@app.get("/")
def index():
    return send_from_directory(os.path.join(BASE, "web"), "index.html")


@app.post("/api/screen")
def screen():
    data = request.get_json(silent=True) or {}
    jd = (data.get("jd") or "").strip()
    text = (data.get("text") or "").strip()
    if not jd:
        return jsonify(error="empty job description"), 400
    if not text:
        return jsonify(error="empty resume text"), 400
    state = f"JOB DESCRIPTION:\n{jd}\n\n=====\n\nRESUME:\n{text}"
    t0 = time.perf_counter()
    try:
        with lock:
            r = client.system_one(state=state, questions=QUESTIONS)
    except Exception as e:
        return jsonify(error=f"jev call failed: {e}"), 502
    a = r.answers
    return jsonify(
        years=a["years"].score,
        depth=a["depth"].score,
        jd_match=a["jd_match"].score,
        skill_evidence=a["skill_evidence"].noul,
        mentorship=a["mentorship"].noul,
        opensource=a["opensource"].noul,
        progression=a["progression"].choice,
        progression_conf=a["progression"].confidence,
        recommend=a["recommend"].choice,
        recommend_conf=a["recommend"].confidence,
        wall_ms=round((time.perf_counter() - t0) * 1000),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8768, threaded=True)
