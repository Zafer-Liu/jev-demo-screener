"""Jev 使用场景演示 ④：简历初筛。

对两份候选简历做结构化初筛（复刻官方 Playground 示例的问题设计）：
- years / depth:  Score 0-5
- mentorship / llm_experience / opensource: Noul
- progression / recommend: Choice

用法: python screener.py
简历 A：真做过 LLM 产品的工程师；简历 B：关键词堆砌型。看 Jev 分不分得清。
"""
import time

from typesafe_sdk import TypeSafeClient

RESUME_A = """Chen Wei, Backend Engineer, 6 years.
- Built and shipped an LLM-powered support triage service (Python, FastAPI, vLLM):
  fine-tuned routing prompts, eval harness with 12k labeled tickets, cut handle time 31%.
- Led a team of 4 for 2 years, ran weekly 1:1s, mentored 2 juniors to promotion.
- Maintainer of an open-source rate-limiter library (2.3k stars); regular contributor to langchain.
- Career: junior -> mid -> senior at same company, then staff engineer at current company."""

RESUME_B = """Zhang San, "AI Expert", 8 years (self-assessed).
- Familiar with: ChatGPT, LLM, AIGC, Prompt Engineering, LangChain, RAG, Agent,
  Transformer, BERT, GPT-4, vector database, fine-tuning, deep learning, machine learning.
- Participated in several projects involving AI (details available upon request).
- Fast learner, passionate about cutting-edge technology, team player.
- Job history: 6 companies in 8 years, titles include AI Engineer / Algorithm Expert / AI Product Director."""

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
    "mentorship": {"type": "noul",
                   "instructions": "The resume demonstrates real mentoring or team leadership experience"},
    "llm_experience": {"type": "noul",
                       "instructions": "The candidate has actually developed LLM products or systems (not just listed keywords)"},
    "opensource": {"type": "noul",
                   "instructions": "The candidate has verifiable open source contributions"},
    "progression": {"type": "choice",
                    "instructions": "What type of career progression is shown",
                    "criteria": {"steady_growth": "Increasing scope and seniority over time",
                                 "job_hopping": "Many short stints without growth",
                                 "lateral_moves": "Similar roles repeated without progression"}},
    "recommend": {"type": "choice",
                  "instructions": "Hiring recommendation for a senior AI product engineer role",
                  "criteria": {"interview": "Strong enough to advance to interview",
                               "reject": "Does not meet the bar",
                               "human_review": "Unclear or inflated signals, a human should look first"}},
}


def main():
    key = [l.split("=", 1)[1].strip() for l in open(".env", encoding="utf-8")
           if l.startswith("TYPESAFE_API_KEY=")][0]
    client = TypeSafeClient(api_key=key)
    client.system_one(state="warmup",
                      questions={"ok": {"type": "noul", "instructions": "The state contains text"}})

    for name, resume in [("A · 实干型", RESUME_A), ("B · 关键词型", RESUME_B)]:
        t0 = time.perf_counter()
        r = client.system_one(state=resume, questions=QUESTIONS)
        ms = (time.perf_counter() - t0) * 1000
        a = r.answers
        print("=" * 66)
        print(f"  简历 {name}   一次调用 · 7 项评估 · {ms:.0f}ms")
        print("=" * 66)
        print(f"  经历年限      {a['years'].score:.1f}/5")
        print(f"  技术深度      {a['depth'].score:.1f}/5")
        print(f"  带人经验      {a['mentorship'].noul:4.0%}")
        print(f"  真做过 LLM    {a['llm_experience'].noul:4.0%}   ← 关键词吹牛检测")
        print(f"  开源贡献      {a['opensource'].noul:4.0%}")
        print(f"  职业轨迹      {a['progression'].choice}  (置信 {a['progression'].confidence:.0%})")
        rec = {"interview": "✅ 推荐面试", "reject": "❌ 不推荐",
               "human_review": "👤 转人工细看"}[a["recommend"].choice]
        print(f"  初筛结论      {rec}  (置信 {a['recommend'].confidence:.0%})\n")
    client.close()


if __name__ == "__main__":
    main()
